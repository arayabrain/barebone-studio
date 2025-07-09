import asyncio
import os
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List

from snakemake.api import (
    DAGSettings,
    DefaultResources,
    DeploymentMethod,
    DeploymentSettings,
    ExecutionSettings,
    OutputSettings,
    RemoteExecutionSettings,
    ResourceSettings,
    SnakemakeApi,
    StorageSettings,
)
from snakemake_executor_plugin_aws_batch import ExecutorSettings

from studio.app.common.core.cloud_batch.batch_config import BATCH_CONFIG
from studio.app.common.core.cloud_batch.batch_utils import BatchUtils
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.smk import ForceRun, SmkParam
from studio.app.common.core.snakemake.smk_status_logger import SmkStatusLogger
from studio.app.common.core.storage.remote_storage_controller import (
    RemoteStorageController,
    RemoteSyncAction,
    RemoteSyncLockFileUtil,
    RemoteSyncStatusFileUtil,
)
from studio.app.common.core.utils.filepath_creater import get_pickle_file, join_filepath
from studio.app.common.core.workflow.workflow import Edge, Node
from studio.app.common.core.workflow.workflow_result import WorkflowResult
from studio.app.common.core.workspace.workspace_data_capacity_services import (
    WorkspaceDataCapacityService,
)
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


def snakemake_execute(workspace_id: str, unique_id: str, params: SmkParam):
    """
    Main entry point for Snakemake execution.
    Determines whether to use local or AWS Batch execution based on configuration.
    """
    if BATCH_CONFIG.USE_AWS_BATCH:
        logger.info("Starting AWS Batch execution mode")
        return _snakemake_execute_batch(workspace_id, unique_id, params)
    else:
        logger.info("Starting local execution mode")
        with ProcessPoolExecutor(max_workers=1) as executor:
            logger.info("start snakemake running process.")

            future = executor.submit(
                _snakemake_execute_process, workspace_id, unique_id, params
            )
            future_result = future.result()

            logger.info("finish snakemake running process. result: %s", future_result)

            return future_result


def _snakemake_execute_process(
    workspace_id: str, unique_id: str, params: SmkParam
) -> bool:
    """
    Local Snakemake execution process.
    """
    # ------------------------------------------------------------
    # Snakemake execution process
    # ------------------------------------------------------------

    smk_logger = SmkStatusLogger(workspace_id, unique_id)
    smk_workdir = join_filepath(
        [
            DIRPATH.OUTPUT_DIR,
            workspace_id,
            unique_id,
        ]
    )

    # Use context manager for proper cleanup
    cores = getattr(params, "cores", 1)

    deployment_methods = []
    if getattr(params, "use_conda", True):
        deployment_methods.append(DeploymentMethod.CONDA)

    # Use context manager for proper cleanup
    with SnakemakeApi(
        OutputSettings(
            verbose=True,
            show_failed_logs=True,
        ),
    ) as snakemake_api:
        workflow_api = snakemake_api.workflow(
            snakefile=Path(DIRPATH.SNAKEMAKE_FILEPATH),
            workdir=Path(smk_workdir),
            storage_settings=StorageSettings(),
            resource_settings=ResourceSettings(cores=cores),
            deployment_settings=DeploymentSettings(
                deployment_method=deployment_methods,
                conda_frontend="conda",
                conda_prefix=DIRPATH.SNAKEMAKE_CONDA_ENV_DIR,
            ),
        )
        logger.info("Workflow API created successfully")
        logger.info("Creating DAG...")

        forceall = getattr(params, "forceall", False)

        dag_settings = DAGSettings(
            forceall=forceall,
        )

        dag_api = workflow_api.dag(
            dag_settings=dag_settings,
        )
        logger.info("DAG created successfully")
        logger.info("Starting workflow execution...")

        try:
            dag_api.execute_workflow()
            result = True
            logger.info("snakemake_execute succeeded.")
        except Exception as e:
            result = False
            logger.error(f"snakemake_execute failed: {e}")
        finally:
            smk_logger.extract_errors_from_snakemake_log(smk_workdir)

    smk_logger.clean_up()

    # Post-processing
    _post_process_workflow(workspace_id, unique_id, result)

    return result


def _snakemake_execute_batch(
    workspace_id: str, unique_id: str, params: SmkParam
) -> bool:
    """
    Execute Snakemake workflow using AWS Batch executor.
    """
    smk_logger = SmkStatusLogger(workspace_id, unique_id)
    smk_workdir = join_filepath(
        [
            DIRPATH.OUTPUT_DIR,
            workspace_id,
            unique_id,
        ]
    )

    try:
        # Initialize BatchExecutor for AWS Batch specific operations
        logger.debug("Load BatchExecutor")
        batch_executor = BatchUtils(workspace_id, unique_id)

        # Prepare workspace for batch execution
        logger.debug("Prepare batch workspace")
        batch_executor.prepare_batch_workspace()

        cores = getattr(params, "cores", 1)
        deployment_methods = []
        if getattr(params, "use_conda", True):
            logger.debug("Use conda deployment method")
            deployment_methods.append(DeploymentMethod.CONDA)

        s3_prefix = BATCH_CONFIG.AWS_DEFAULT_PROVIDER.lower()
        s3_storage = (
            f"{s3_prefix}://{BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME}"
            f"/snakemake/{workspace_id}/{unique_id}/"
        )

        # Use context manager for proper cleanup
        with SnakemakeApi(
            OutputSettings(
                verbose=True,
                show_failed_logs=True,
            ),
        ) as snakemake_api:
            workflow_api = snakemake_api.workflow(
                snakefile=Path(DIRPATH.SNAKEMAKE_FILEPATH),
                workdir=Path(smk_workdir),
                storage_settings=StorageSettings(
                    default_storage_provider=s3_prefix,
                    default_storage_prefix=s3_storage,
                ),
                resource_settings=ResourceSettings(
                    nodes=10,
                    cores=cores,
                    default_resources=DefaultResources(
                        [
                            "mem_mb=4096",
                        ]
                    ),
                ),
                deployment_settings=DeploymentSettings(
                    deployment_method=deployment_methods,
                    conda_frontend="conda",
                    conda_prefix=DIRPATH.SNAKEMAKE_CONDA_ENV_DIR,
                ),
            )

            logger.info("Workflow API created successfully for AWS Batch")
            logger.info("Creating DAG...")

            forceall = getattr(params, "forceall", False)

            dag_settings = DAGSettings(
                forceall=forceall,
            )
            logger.debug("DAG settings created")

            try:
                dag_api = workflow_api.dag(
                    dag_settings=dag_settings,
                )
                logger.info("DAG created successfully")
            except Exception as e:
                logger.error(f"Failed to create DAG: {e}")

            logger.info("Starting workflow execution on AWS Batch...")
            try:
                # Execute workflow - Snakemake will handle job submission to AWS Batch
                # Get user-appropriate job queue (free or paid tier)
                selected_job_queue = batch_executor.get_job_queue_for_user()
                logger.info(f"Using AWS Batch job queue: {selected_job_queue}")

                dag_api.execute_workflow(
                    executor="aws-batch",
                    execution_settings=ExecutionSettings(
                        retries=3,
                        keep_going=False,
                    ),
                    executor_settings=ExecutorSettings(
                        region=BATCH_CONFIG.AWS_DEFAULT_REGION,
                        job_queue=selected_job_queue,
                        job_role=BATCH_CONFIG.AWS_BATCH_JOB_ROLE,
                    ),
                    remote_execution_settings=RemoteExecutionSettings(
                        container_image=batch_executor.get_container_image(),
                        envvars=["USE_AWS_BATCH", "S3_DEFAULT_BUCKET_NAME"],
                        jobname="optinist-{rulename}-{jobid}",
                    ),
                )
                result = True
                logger.info("AWS Batch workflow execution succeeded.")
            except Exception as e:
                result = False
                logger.error(f"AWS Batch workflow execution failed: {e}")
            finally:
                smk_logger.extract_errors_from_snakemake_log(smk_workdir)
                # Sync results back from batch execution
                # batch_executor.sync_batch_results()

    except Exception as e:
        logger.error(f"Failed to setup AWS Batch execution: {e}")
        result = False
    finally:
        smk_logger.clean_up()

    # Post-processing (same for both local and batch)
    _post_process_workflow(workspace_id, unique_id, result)

    return result


def _post_process_workflow(workspace_id: str, unique_id: str, result: bool = False):
    # Update workflow processing results
    asyncio.run(WorkflowResult(workspace_id, unique_id).observe_overall())

    # Data usage calculation
    WorkspaceDataCapacityService.update_experiment_data_usage(workspace_id, unique_id)

    # result error handling
    if not result:
        # Operate remote storage.
        if RemoteStorageController.is_available():
            # force delete sync lock file
            RemoteSyncLockFileUtil.delete_sync_lock_file(workspace_id, unique_id)

            remote_bucket_name = RemoteSyncStatusFileUtil.get_remote_bucket_name(
                workspace_id, unique_id
            )

            # force update sync status file
            RemoteSyncStatusFileUtil.create_sync_status_file_for_error(
                remote_bucket_name,
                workspace_id,
                unique_id,
                RemoteSyncAction.UPLOAD,
            )

    return result


def delete_dependencies(
    workspace_id: str,
    unique_id: str,
    smk_params: SmkParam,
    nodeDict: Dict[str, Node],
    edgeDict: Dict[str, Edge],
):
    queue = deque()

    for param in smk_params.forcerun:
        queue.append(param.nodeId)

    while True:
        # terminate condition
        if len(queue) == 0:
            break

        # delete pickle
        node_id = queue.pop()
        algo_name = nodeDict[node_id].data.label

        pickle_filepath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                get_pickle_file(
                    workspace_id=workspace_id,
                    unique_id=unique_id,
                    node_id=node_id,
                    algo_name=algo_name,
                ),
            ]
        )
        # logger.debug(pickle_filepath)

        if os.path.exists(pickle_filepath):
            os.remove(pickle_filepath)

        # 全てのedgeを見て、node_idがsourceならtargetをqueueに追加する
        for edge in edgeDict.values():
            if node_id == edge.source:
                queue.append(edge.target)


def delete_procs_dependencies(
    workspace_id: str,
    unique_id: str,
    forceRunList: List[ForceRun],
):
    """
    Delete procs (ExptConfig.procs) dependencies
    """

    for proc in forceRunList:
        # delete pickle
        pickle_filepath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                get_pickle_file(
                    workspace_id=workspace_id,
                    unique_id=unique_id,
                    node_id=proc.nodeId,
                    algo_name=proc.name,
                ),
            ]
        )

        if os.path.exists(pickle_filepath):
            os.remove(pickle_filepath)
