import asyncio
import os
import time
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
from studio.app.common.core.cloud_batch.batch_utils import BatchDebug, BatchUtils
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

        dag_api = workflow_api.dag(
            dag_settings=DAGSettings(
                forceall=forceall,
            )
        )

        logger.info("DAG created successfully")
        logger.info("Starting workflow execution...")

        snakemake_result = False

        try:
            dag_api.execute_workflow()

            snakemake_result = True
            logger.info("snakemake_execute succeeded.")
        except Exception as e:
            snakemake_result = False
            logger.error(f"snakemake_execute failed: {e}")

            # Logging errors via SmkStatusLogger to notify
            #   the monitoring process (WorkflowMonitor) of the error occurrence
            smk_logger.logger.error(e)

    if snakemake_result:
        logger.info("snakemake_execute succeeded.")
    else:
        logger.error("snakemake_execute failed..")

    smk_logger.clean_up()

    # Post-processing
    _post_process_workflow(workspace_id, unique_id, snakemake_result)

    return snakemake_result


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

        # Debug AWS Batch environment status for immediate visibility
        logger.info("Debugging AWS Batch environment...")
        BatchDebug.debug_batch_environment(batch_executor)

        # Validate AWS Batch configuration before proceeding
        logger.info("Validating AWS Batch configuration...")
        if not BatchDebug.validate_batch_configuration(batch_executor):
            logger.error(
                "AWS Batch configuration validation failed - aborting execution"
            )
            return False

        # Prepare workspace for batch execution
        logger.debug("Prepare batch workspace")
        batch_executor.prepare_batch_workspace()

        cores = 2  # Set consistent cores for debugging
        # Configure storage based on availability
        storage_settings = None
        if RemoteStorageController.is_available():
            # Use S3 when available
            s3_prefix = BATCH_CONFIG.AWS_DEFAULT_PROVIDER.lower()
            s3_bucket_name = os.environ.get(
                "S3_DEFAULT_BUCKET_NAME", BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME
            )
            # Fix double slash issue by removing trailing slash from  prefix
            # Snakemake adds leading slash to paths,
            # so s3://bucket + /path = s3://bucket/path
            # With trailing slash:
            # s3://bucket/ + /path = s3://bucket//path (double slash)
            s3_storage = f"{s3_prefix}://{s3_bucket_name}"
            storage_settings = StorageSettings(
                default_storage_provider=s3_prefix,
                default_storage_prefix=s3_storage,
            )
            logger.debug(f"Using S3 storage: {s3_storage}")
            logger.debug(
                f"S3 storage breakdown: provider='{s3_prefix}', "
                f"bucket='{s3_bucket_name}', full_prefix='{s3_storage}'"
            )
        else:
            # Use optimized EFS configuration when S3 is not available
            logger.info("S3 not available, configuring optimized EFS storage")
            BatchDebug.prepare_efs_environment(workspace_id, unique_id)
            storage_settings = BatchDebug.get_efs_optimized_storage_settings(
                workspace_id, unique_id
            )
        # Set working directory to studio_data to eliminate /app prefix in S3 paths
        # When Snakemake constructs relative paths to be relative to /app/studio_data
        # Expected: s3://bucket/ + output/workspace/id = s3://bucket/output/workspace/id
        batch_workdir = Path("/app/studio_data")
        config_source = join_filepath([smk_workdir, DIRPATH.SNAKEMAKE_CONFIG_YML])
        config_dest = join_filepath([str(batch_workdir), DIRPATH.SNAKEMAKE_CONFIG_YML])

        # Copy config file to batch workdir
        import shutil

        if os.path.exists(config_source):
            shutil.copy2(config_source, config_dest)
            logger.debug(f"Copied config from {config_source} to {config_dest}")

            # Also ensure config is uploaded to S3 for batch job access
            if RemoteStorageController.is_available():
                try:
                    # Upload just the snakemake.yaml config file to S3
                    # using proper async interface
                    # According to RemoteStorageController docs, target_files
                    # list specifies specific files
                    remote_controller = RemoteStorageController(
                        BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME
                    )

                    # Use asyncio to run the async upload method
                    # This uploads only the snakemake.yaml file,
                    # not the entire experiment
                    import asyncio

                    try:
                        # Try to get the current event loop
                        asyncio.get_running_loop()
                        logger.warning(
                            "Cannot upload config in async context - skipping"
                        )
                        logger.debug("Config will be available via S3 storage plugin")
                    except RuntimeError:
                        # No running loop, safe to create a new one
                        asyncio.run(
                            remote_controller.upload_experiment(
                                workspace_id,
                                unique_id,
                                target_files=[DIRPATH.SNAKEMAKE_CONFIG_YML],
                            )
                        )
                        logger.debug(
                            f"Uploaded config file to S3 for "
                            f"workspace {workspace_id}/{unique_id}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to upload config to S3 (not critical): {e}")
                    logger.debug("Snakemake will access config via S3 storage plugin")
        else:
            logger.error(f"Config file not found at {config_source}")
            return False

        # Use context manager for proper cleanup
        with SnakemakeApi(
            OutputSettings(
                verbose=True,
                show_failed_logs=True,
            ),
        ) as snakemake_api:
            workflow_api = snakemake_api.workflow(
                snakefile=Path(DIRPATH.SNAKEMAKE_FILEPATH),
                workdir=batch_workdir,
                storage_settings=storage_settings,
                resource_settings=ResourceSettings(
                    nodes=10,
                    cores=cores,
                    default_resources=DefaultResources(["mem_mb=4096"]),
                ),
                deployment_settings=DeploymentSettings(
                    deployment_method={DeploymentMethod.CONDA},
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

                # Temporarily remove AWS credentials from environment for batch jobs
                # Forces batch jobs to use IAM roles instead of hardcoded credentials
                aws_access_key = os.environ.pop("AWS_ACCESS_KEY_ID", None)
                aws_secret_key = os.environ.pop("AWS_SECRET_ACCESS_KEY", None)

                try:
                    # Prepare environment variables for batch jobs
                    envvars = ["USE_AWS_BATCH", "OPTINIST_DIR"]
                    if RemoteStorageController.is_available():
                        envvars.extend(
                            [
                                "S3_DEFAULT_BUCKET_NAME",
                                "AWS_DEFAULT_REGION",
                                "PYTHONPATH",
                            ]
                        )
                        logger.info("Using S3 storage for batch jobs")
                    else:
                        envvars.extend(["EFS_MOUNT_TARGET", "TMPDIR", "TMP"])

                    # Prepare container setup for EFS optimization
                    contain_setup = []
                    if not RemoteStorageController.is_available():
                        contain_setup = BatchDebug.get_batch_contain_setup_commands()

                    logger.debug("=== AWS BATCH EXECUTION DEBUG ===")
                    logger.debug(f"Job Queue: {selected_job_queue}")
                    logger.debug(f"Job Role: {BATCH_CONFIG.AWS_BATCH_JOB_ROLE}")
                    logger.debug(
                        f"Container Image: {batch_executor.get_container_image()}"
                    )
                    logger.debug(f"Environment Variables: {envvars}")
                    logger.debug(
                        f"S3 Available: {RemoteStorageController.is_available()}"
                    )
                    logger.debug(f"Container Setup Commands: {contain_setup}")

                    # Enhanced debugging - Check AWS configuration
                    logger.debug(f"AWS Region: {BATCH_CONFIG.AWS_DEFAULT_REGION}")
                    logger.debug(f"S3 Bucket: {BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME}")
                    logger.debug(
                        f"Job Definition: {BATCH_CONFIG.AWS_BATCH_JOB_DEFINITION}"
                    )

                    # Check current environment variables that will be passed
                    for env_var in envvars:
                        value = os.environ.get(env_var, "NOT_SET")
                        logger.debug(f"Env {env_var}: {value}")

                    # Check AWS credentials (without logging the actual values)
                    aws_key_exists = "AWS_ACCESS_KEY_ID" in os.environ
                    aws_secret_exists = "AWS_SECRET_ACCESS_KEY" in os.environ
                    logger.debug(f"AWS_ACCESS_KEY_ID exists: {aws_key_exists}")
                    logger.debug(f"AWS_SECRET_ACCESS_KEY exists: {aws_secret_exists}")

                    # Check resource settings
                    logger.debug(f"Resource settings - nodes: 10, cores: {cores}")
                    logger.debug("Default resources: mem_mb=4096")

                    logger.debug("=== CONTAINER COMMAND DEBUG ===")
                    logger.debug(
                        f"Container Image: {batch_executor.get_container_image()}"
                    )
                    logger.debug(f"Precommand Setup: {contain_setup}")
                    logger.debug(
                        "Note: Using script-based Snakemake rules with ENTRYPOINT fix"
                    )
                    logger.debug(
                        "If 'Shell command: None' persists, check container ENTRYPOINT"
                    )
                    logger.debug("=== END CONTAINER COMMAND DEBUG ===")

                    # Debug S3 storage configuration - critical for file latency issues
                    logger.debug("=== S3 STORAGE DEBUG ===")
                    logger.debug(f"S3 Storage Prefix: {s3_storage}")
                    logger.debug(f"S3 Bucket: {s3_bucket_name}")
                    logger.debug(f"S3 Provider: {s3_prefix}")
                    logger.debug("Increased latency_wait to 300s for S3 consistency")
                    logger.debug("=== END S3 STORAGE DEBUG ===")

                    logger.debug("=== AWS BATCH EXECUTION DEBUG ===")

                    # Store start time for monitoring
                    execution_start_time = time.time()
                    logger.info(f"Starting DAG execution at {execution_start_time}")

                    # Start job monitoring before execution
                    logger.info("Starting enhanced job monitoring...")
                    batch_executor.start_job_monitoring()

                    try:
                        dag_api.execute_workflow(
                            executor="aws-batch",
                            execution_settings=ExecutionSettings(
                                retries=3,
                                keep_going=False,
                                latency_wait=300,
                            ),
                            executor_settings=ExecutorSettings(
                                region=BATCH_CONFIG.AWS_DEFAULT_REGION,
                                job_queue=selected_job_queue,
                                job_role=BATCH_CONFIG.AWS_BATCH_JOB_ROLE,
                                task_timeout=1800,  # Increase timeout to 30 minutes
                            ),
                            remote_execution_settings=RemoteExecutionSettings(
                                container_image=batch_executor.get_container_image(),
                                envvars=envvars,
                                jobname="optinist-{rulename}-{jobid}",
                                # Add container setup commands for EFS optimization
                                precommand=contain_setup if contain_setup else None,
                            ),
                        )

                        execution_duration = time.time() - execution_start_time
                        logger.info(
                            f"DAG execution completed in {execution_duration:.2f}s"
                        )

                    except Exception as exec_error:
                        execution_duration = time.time() - execution_start_time
                        logger.error(
                            f"DAG execution failed after {execution_duration:.2f}s"
                        )
                        logger.error(f"Execution error: {exec_error}")

                        # Try to get more detailed job information
                        try:
                            recent_failed = batch_executor.get_recent_failed_jobs(
                                limit=3, include_context=True
                            )
                            if recent_failed:
                                logger.error(
                                    f"Found {len(recent_failed)} recent failed jobs "
                                    "with detailed context"
                                )

                                for i, job_context in enumerate(recent_failed):
                                    job_id = job_context.get("job_id", "Unknown")
                                    logger.error(f"Failed job {i+1}: {job_id}")

                                    # Show quick failure summary
                                    exit_code = job_context.get("exit_code")
                                    exit_reason = job_context.get(
                                        "exit_reason", "Unknown"
                                    )
                                    logger.error(
                                        f"  Exit Code: {exit_code},  "
                                        f"Reason: {exit_reason}"
                                    )

                            try:
                                succeeded_jobs = batch_executor.batch_client.list_jobs(
                                    jobQueue=batch_executor.get_job_queue_for_user(),
                                    jobStatus="SUCCEEDED",
                                    maxResults=5,
                                )
                                if succeeded_jobs.get("jobList"):
                                    logger.info(
                                        f"Found {len(succeeded_jobs['jobList'])} "
                                        "recent SUCCEEDED jobs:"
                                    )
                                    for job in succeeded_jobs["jobList"][:3]:
                                        logger.info(
                                            f"  SUCCESS: {job['jobName']} "
                                            f"({job['jobId']})"
                                        )
                                else:
                                    logger.warning("No recent SUCCEEDED jobs found")
                            except Exception as e:
                                logger.warning(f"Could not check succeeded jobs: {e}")

                            # Show failure analysis summary for each failed job
                            for job_context in recent_failed:
                                failure_analysis = job_context.get(
                                    "failure_analysis", {}
                                )
                                if failure_analysis.get("likely_causes"):
                                    logger.error(
                                        f"  Likely Cause: "
                                        f"{failure_analysis['likely_causes'][0]}"
                                    )
                                if failure_analysis.get("recommendations"):
                                    logger.error(
                                        f"  Recommendation: "
                                        f"{failure_analysis['recommendations'][0]}"
                                    )

                                # Enhanced context already provides detailed info
                                # Show sample log errors if available
                                logs = job_context.get("logs", {})
                                if logs and logs.get("error_patterns"):
                                    logger.error("  Error Patterns:")
                                    for pattern in logs["error_patterns"][
                                        :2
                                    ]:  # First 2 patterns
                                        logger.error(
                                            f"    - {pattern['pattern']}: "
                                            f"{pattern['message'][:80]}..."
                                        )

                                # Show monitoring insights if available
                                mon_cntx = job_context.get("monitoring_context", {})
                                if mon_cntx and mon_cntx.get("monitoring_duration"):
                                    duration = mon_cntx["monitoring_duration"]
                                    logger.error(f"  Monitored for: {duration}")

                                    if mon_cntx.get("log_snapshots"):
                                        logger.error(
                                            f"{len(mon_cntx['log_snapshots'])} "
                                            "log snapshots during monitoring"
                                        )
                        except Exception as detail_error:
                            logger.error(f"Failed to get job details: {detail_error}")

                        raise exec_error
                    result = True
                    logger.info("AWS Batch workflow execution succeeded.")
                finally:
                    # Restore AWS credentials to environment
                    if aws_access_key is not None:
                        os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key
                    if aws_secret_key is not None:
                        os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_key

                    try:
                        if os.path.exists(config_dest):
                            os.remove(config_dest)
                            logger.debug(f"Cleaned up copied config: {config_dest}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup config {config_dest}: {e}")
            except Exception as e:
                result = False
                logger.error(f"AWS Batch workflow execution failed: {e}")
                logger.error(f"Exception details: {str(e)}")
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
            finally:
                # Stop job monitoring
                logger.info("Stopping enhanced job monitoring...")
                batch_executor.stop_job_monitoring()

                smk_logger.extract_errors_from_snakemake_log(smk_workdir)
                # Sync results back from batch execution
                # batch_executor.sync_batch_results()

                if not result:
                    logger.error(
                        "AWS Batch execution failed - "
                        "attempting to retrieve enhanced job logs"
                    )
                    try:
                        # Get recent failed jobs with enhanced context
                        recent_jobs = batch_executor.get_recent_failed_jobs(
                            limit=3, include_context=True
                        )

                        if recent_jobs:
                            logger.error(
                                f"Found {len(recent_jobs)} recent "
                                "failed jobs with enhanced context:"
                            )

                            for i, job_context in enumerate(recent_jobs, 1):
                                logger.error(f"\n=== FAILED JOB {i} ANALYSIS ===")
                                logger.error(f"Job ID: {job_context.get('job_id')}")
                                logger.error(f"Job Name: {job_context.get('job_name')}")
                                logger.error(
                                    f"Exit Code: {job_context.get('exit_code')}"
                                )
                                logger.error(
                                    f"Exit Reason: {job_context.get('exit_reason')}"
                                )
                                logger.error(
                                    f"Status Reason: {job_context.get('status_reason')}"
                                )

                                # Show failure analysis
                                failure_analysis = job_context.get(
                                    "failure_analysis", {}
                                )
                                if failure_analysis:
                                    logger.error("Likely Causes:")
                                    for cause in failure_analysis.get(
                                        "likely_causes", []
                                    ):
                                        logger.error(f"  - {cause}")

                                    logger.error("Recommendations:")
                                    for rec in failure_analysis.get(
                                        "recommendations", []
                                    ):
                                        logger.error(f"  - {rec}")

                                # Show monitoring context if available
                                mon_cntx = job_context.get("monitoring_context", {})
                                if mon_cntx and mon_cntx.get("log_snapshots"):
                                    logger.error(
                                        f"Monitoring captured "
                                        f"{len(mon_cntx['log_snapshots'])} "
                                        "log snapshots"
                                    )

                                # Show key log errors
                                logs = job_context.get("logs", {})
                                if logs and logs.get("error_patterns"):
                                    logger.error("Error Patterns Found:")
                                    for pattern in logs["error_patterns"][
                                        :3
                                    ]:  # First 3 patterns
                                        logger.error(
                                            f"  - {pattern['pattern']}: "
                                            f"{pattern['message'][:100]}..."
                                        )

                                logger.error("=== END JOB ANALYSIS ===\n")
                        else:
                            logger.error(
                                "No recent failed jobs found "
                                "(they may have been cleaned up)"
                            )

                    except Exception as log_error:
                        logger.error(
                            f"Failed to retrieve enhanced batch job logs: {log_error}"
                        )

    except Exception as e:
        logger.error(f"Failed to setup AWS Batch execution: {e}")
        snakemake_result = False
    finally:
        smk_logger.clean_up()

    # Post-processing (same for both local and batch)
    _post_process_workflow(workspace_id, unique_id, snakemake_result)

    return snakemake_result


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
