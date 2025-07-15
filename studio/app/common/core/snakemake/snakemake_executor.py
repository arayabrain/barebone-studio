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
    SharedFSUsage,
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


def _get_efs_optimized_storage_settings(
    workspace_id: str, unique_id: str
) -> StorageSettings:
    """
    Configure optimized storage settings for EFS with local scratch directories.
    This implements the best practices for shared network filesystems.
    """
    # EFS mount path - should be persistent across batch jobs
    efs_storage = f"file:///mnt/efs/{workspace_id}/{unique_id}/"

    # Local scratch directory - should be fast local storage (e.g., NVMe SSD)
    # This will be used for intermediate files and temporary storage
    local_scratch = "/tmp/snakemake_scratch"

    # Per-job scratch directory to avoid conflicts between concurrent jobs
    job_local_scratch = "/tmp/snakemake_scratch/$JOBID"

    storage_settings = StorageSettings(
        default_storage_provider="fs",  # Use the filesystem storage plugin
        default_storage_prefix=efs_storage,
        # Local scratch for the coordinator/main process
        local_storage_prefix=local_scratch,
        # Per-job local scratch for remote batch jobs
        remote_job_local_storage_prefix=job_local_scratch,
        shared_fs_usage=[SharedFSUsage.SOFTWARE_DEPLOYMENT],
    )

    logger.info(f"EFS storage configured: {efs_storage}")
    logger.info(f"Local scratch directory: {local_scratch}")
    logger.info(f"Remote job scratch directory: {job_local_scratch}")

    return storage_settings


def _prepare_efs_environment(workspace_id: str, unique_id: str):
    """
    Ensure EFS directories exist and local scratch is prepared.
    """
    efs_base_path = Path(f"/mnt/efs/{workspace_id}/{unique_id}")
    local_scratch_path = Path("/tmp/snakemake_scratch")

    try:
        # Create EFS directories if they don't exist
        efs_base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"EFS directory prepared: {efs_base_path}")

        # Create local scratch directory
        local_scratch_path.mkdir(parents=True, exist_ok=True)
        # Set proper permissions for scratch directory
        os.chmod(local_scratch_path, 0o755)

        logger.info(f"Local scratch directory prepared: {local_scratch_path}")

        # Create subdirectories that Snakemake might need
        (efs_base_path / "logs").mkdir(exist_ok=True)
        (efs_base_path / "benchmarks").mkdir(exist_ok=True)
        (efs_base_path / ".snakemake").mkdir(exist_ok=True)

    except Exception as e:
        logger.error(f"Failed to prepare EFS environment: {e}")
        raise


def _get_batch_container_setup_commands() -> List[str]:
    """
    Return setup commands that should be run in batch containers to prepare
    the local scratch environment (EFS-specific commands).
    """
    return [
        # Create local scratch with proper permissions
        "mkdir -p /tmp/snakemake_scratch/$JOBID",
        "chmod 755 /tmp/snakemake_scratch",
        "chmod 755 /tmp/snakemake_scratch/$JOBID",
        # Set environment variables for better performance
        "export TMPDIR=/tmp/snakemake_scratch/$JOBID",
        "export TMP=/tmp/snakemake_scratch/$JOBID",
        # Ensure EFS mount point exists
        "mkdir -p /mnt/efs",
        # Optional: Set rsync options for better EFS performance
        "export SNAKEMAKE_RSYNC_OPTS='-av --inplace --no-sparse'",
    ]


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

        # Configure storage based on availability
        storage_settings = None
        if RemoteStorageController.is_available():
            # Use S3 when available
            s3_prefix = BATCH_CONFIG.AWS_DEFAULT_PROVIDER.lower()
            s3_bucket_name = os.environ.get(
                "S3_DEFAULT_BUCKET_NAME", BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME
            )
            # Use bucket root to match S3StorageController path structure
            # S3StorageController uses: input/{workspace_id}/, etc.
            s3_storage = f"{s3_prefix}://{s3_bucket_name}/"
            storage_settings = StorageSettings(
                default_storage_provider=s3_prefix,
                default_storage_prefix=s3_storage,
            )
            logger.debug(f"Using S3 storage: {s3_storage}")
        else:
            # Use optimized EFS configuration when S3 is not available
            logger.info("S3 not available, configuring optimized EFS storage")
            _prepare_efs_environment(workspace_id, unique_id)
            storage_settings = _get_efs_optimized_storage_settings(
                workspace_id, unique_id
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
                storage_settings=storage_settings,
                resource_settings=ResourceSettings(
                    nodes=10,
                    cores=cores,
                    default_resources=DefaultResources(
                        [
                            "mem_mb=4096",
                            # Add disk space for local scratch
                            "disk_mb=10240"
                            if not RemoteStorageController.is_available()
                            else "mem_mb=4096",
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

                # Prepare environment variables for batch jobs
                envvars = ["USE_AWS_BATCH"]
                if RemoteStorageController.is_available():
                    envvars.append("S3_DEFAULT_BUCKET_NAME")
                else:
                    envvars.extend(["EFS_MOUNT_TARGET", "TMPDIR", "TMP"])

                # Exclude AWS credentials from batch jobs - use IAM roles instead
                envvars.extend(["-AWS_ACCESS_KEY_ID", "-AWS_SECRET_ACCESS_KEY"])

                # Prepare container setup for EFS optimization
                container_setup = []
                if not RemoteStorageController.is_available():
                    container_setup = _get_batch_container_setup_commands()

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
                        envvars=envvars,
                        jobname="optinist-{rulename}-{jobid}",
                        # Add container setup commands for EFS optimization
                        precommand=container_setup if container_setup else None,
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
