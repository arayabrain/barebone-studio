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
        logger.info("Load BatchExecutor")
        batch_executor = BatchUtils(workspace_id, unique_id)

        # Debug AWS Batch environment status for immediate visibility
        # logger.info("Debugging AWS Batch environment...")
        # BatchDebug.debug_batch_environment(batch_executor)

        # Validate AWS Batch configuration before proceeding
        # logger.info("Validating AWS Batch configuration...")
        # if not BatchDebug.validate_batch_configuration(batch_executor):
        #     logger.error(
        #         "AWS Batch configuration validation failed - aborting execution"
        #     )
        #     return False

        # Prepare workspace for batch execution
        logger.info("Prepare batch workspace")
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
            # Configure S3 storage mapping
            # Snakemake local paths: /app/studio_data/output/1/958d5ef3/file.pkl
            # Should map to S3: s3://bucket/app/studio_data/output/1/958d5ef3/file.pkl
            # But we're seeing: s3://bucket//app/studio_data/... (double slash)
            # Tried 1:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}" ...
            # + local_storage_prefix=Path(DIRPATH.DATA_DIR),
            # resulted in exit at STARTING with no files found:
            # s3://subscr-optinist-app-storage//app/studio_data/output/1/...
            # 8b445935/input_zdax4o54o0/sample_mouse2p_behavior.pkl
            # + batch_workdir = Path("/app")
            # Tried 2:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}/app/studio_data"
            # + local_storage_prefix=Path(DIRPATH.DATA_DIR),
            # + batch_workdir = Path("/app")
            # resulted in exit at STARTING with no files found:
            # /app/studio_data/s3/subscr-optinist-app-storage/...
            # app/studio_data/app/studio_data/input/1
            # Tried 3:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}" # no local_storage_prefix
            # + batch_workdir = Path("/app")
            # resulted in exit at STARTING with no files found:
            # s3://subscr-optinist-app-storage//app/studio_data/...
            # output/1/c75c5320/input_zdax4o54o0/sample_mouse2p_behavior.pkl
            # Tried 4:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}"
            # + local_storage_prefix=Path(DIRPATH.DATA_DIR),
            # + batch_workdir = Path(DIRPATH.DATA_DIR)
            # resulted in:
            # s3://subscr-optinist-app-storage//app/studio_data/...
            # output/1/9196bec2/input_zdax4o54o0/sample_mouse2p_behavior.pkl
            # And also /app/studio_data/s3/subscr-optinist-app-storage/app/...
            # studio_data/output/1/9196bec2/input_ab1mmvt2ky/sample_mouse2p_image.pkl
            # So next will try:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}"
            # + batch_workdir = Path("/app") # Keep Snakefile accessible
            # + NO local_storage_prefix # Avoid duplication
            # Tried 5:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}"
            # + shared_fs_usage=[], retrieve_storage=True, keep_storage_local=False
            # + Upload snakemake.yaml config to S3 for batch jobs to find
            # This should fix the "Invalid config yaml file" error
            # Tried 6:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}" (no trailing slash)
            # + local_storage_prefix=Path("/app") (/app instead of /app/studio_data)
            # Result: Still double slash, Snakemake creating /app/s3/ paths
            # Tried 7:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}"
            # + remote_job_local_storage_prefix for AWS Batch jobs
            # + No local_storage_prefix to avoid local S3 mount paths
            # Result: Still double slash s3://bucket//app/studio_data/...
            # Tried 8:
            # Empty default_storage_prefix to bypass Snakemake's path construction
            # + frozenset() for shared_fs_usage (not list)
            # + Let S3 plugin handle full path construction
            # Result: ERROR - S3 plugin requires valid --default-storage-prefix
            # with s3:// scheme
            # Tried 9:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}/app/studio_data"
            # + default_storage_prefix includes full /app/studio_data path
            # + local_storage_prefix=Path(DIRPATH.DATA_DIR) strips /app/studio_data
            # + remote_job_local_storage_prefix="/tmp/snakemake_scratch"
            # Result: Triple duplication
            # /app/studio_data/s3/.../app/studio_data/app/studio_data/
            # Tried 10:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}" (no path in prefix)
            # + local_storage_prefix=Path(DIRPATH.DATA_DIR) strips /app/studio_data
            # + remote_job_local_storage_prefix="/tmp/snakemake_scratch" for batch jobs
            # + frozenset() for shared_fs_usage
            # Similar to Tried 1 but adds remote_job_local_storage_prefix
            # Result: SAME as # 1 - Double slash s3://bucket//app/studio_data/output/...
            # Jobs submit but still path construction issue + S3 mount paths
            # Tried 11:
            # s3_storage = f"{s3_prefix}://{s3_bucket_name}" (no path in prefix)
            # + local_storage_prefix=Path("/tmp/snakemake_storage") (different from
            #    container data dir)
            # + remote_job_local_storage_prefix=Path("/tmp/snakemake_storage")
            #    (same as local)
            # + Avoid path conflicts with actual container working directory
            # Result: Better local storage (/tmp/snakemake_storage/s3/...) but STILL
            # double slash s3://bucket//app/studio_data/...
            # Tried 12:
            # + Modified SmkUtils to generate relative paths for S3 mode
            # + s3_storage includes full app/studio_data path prefix
            # + SmkUtils strips /app/studio_data from absolute paths in S3 mode
            # + Relative paths: "output/1/abc/file.pkl" + prefix
            # + Expected result: s3://bucket/app/studio_data/output/1/abc/file.pkl
            # And workdir=Path(smk_workdir)
            # Result: MissingInputException - path duplication still occurring.
            # /tmp/snakemake_storage/s3/subscr-optinist-app-storage/...
            # app/studio_data/app/studio_data/output/...
            # Tried 13:
            # + s3_storage = f"{s3_prefix}://{s3_bucket_name}" (no path in prefix)
            # + Let Snakemake combine the bucket URI with the full
            # relative path from the rule
            # + Expected result: s3://bucket/app/studio_data/output/1/abc/file.pkl
            # Result: MissingInputException - path duplication still occurring.
            # /tmp/snakemake_storage/s3/subscr-optinist-app-storage/app/studio_data/output/
            #  Tried 14:
            # + Change workdir to /app/studio_data
            # + Keep s3_storage as bucket URI only
            # + Expected result: Snakemake resolves paths correctly from the new workdir
            s3_storage = f"{s3_prefix}://{s3_bucket_name}"
            storage_settings = StorageSettings(
                default_storage_provider=s3_prefix,
                default_storage_prefix=s3_storage,
                local_storage_prefix=Path("/tmp/snakemake_storage"),
                remote_job_local_storage_prefix=Path("/tmp/snakemake_storage"),
                shared_fs_usage=frozenset(),
                retrieve_storage=True,
                keep_storage_local=False,
            )
            logger.debug(f"Using S3 storage: {s3_storage}")
            logger.debug(
                f"S3 storage breakdown: provider='{s3_prefix}', "
                f"bucket='{s3_bucket_name}', full_prefix='{s3_storage}'"
            )
            logger.debug("Local storage prefix: /tmp/snakemake_storage")
            logger.debug(
                f"Example: {DIRPATH.DATA_DIR}/output/1/abc/file.pkl -> "
                f"app/studio_data/output/1/abc/file.pkl -> "
                f"{s3_storage}/app/studio_data/output/1/abc/file.pkl"
            )
        else:
            # Use optimized EFS configuration when S3 is not available
            logger.info("S3 not available, configuring optimized EFS storage")
            BatchDebug.prepare_efs_environment(workspace_id, unique_id)
            storage_settings = BatchDebug.get_efs_optimized_storage_settings(
                workspace_id, unique_id
            )

        smk_config = join_filepath([smk_workdir, DIRPATH.SNAKEMAKE_CONFIG_YML])

        # Upload config file to S3 so batch jobs can find it
        if os.path.exists(smk_config):
            if RemoteStorageController.is_available():
                try:
                    # Construct S3 path relative to smk_workdir structure
                    # smk_workdir = DIRPATH.OUTPUT_DIR/workspace_id/unique_id
                    # So S3 path should be:
                    # app/studio_data/output/workspace_id/unique_id/snakemake.yaml
                    s3_config_path = join_filepath(
                        [
                            DIRPATH.OUTPUT_DIR,
                            workspace_id,
                            unique_id,
                            DIRPATH.SNAKEMAKE_CONFIG_YML,
                        ]
                    )

                    # Upload using boto3 S3 client directly
                    import boto3

                    s3_client = boto3.client("s3")
                    # Remove leading slash for S3 key
                    s3_key = s3_config_path.lstrip("/")
                    s3_client.upload_file(
                        smk_config, BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME, s3_key
                    )
                    logger.info(
                        f"Uploaded config to S3: "
                        f"s3://{BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME}/{s3_key}"
                    )
                except Exception as e:
                    logger.error(f"Failed to upload config to S3: {e}")
                    return False
            else:
                logger.warning(
                    "S3 not available - config may not be accessible to batch jobs"
                )
        else:
            logger.error(f"Config file not found at {smk_config}")
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
                workdir=Path(DIRPATH.DATA_DIR),
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
            logger.info("DAG settings created")

            try:
                dag_api = workflow_api.dag(
                    dag_settings=dag_settings,
                )
                logger.info("DAG created successfully")
            except Exception as e:
                logger.error(f"Failed to create DAG: {e}")
                raise e

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

                    # logger.debug("=== AWS BATCH EXECUTION DEBUG ===")
                    # logger.debug(f"Job Queue: {selected_job_queue}")
                    # logger.debug(f"Job Role: {BATCH_CONFIG.AWS_BATCH_JOB_ROLE}")
                    # logger.debug(
                    #     f"Container Image: {batch_executor.get_container_image()}"
                    # )
                    # logger.debug(f"Environment Variables: {envvars}")
                    # logger.debug(
                    #     f"S3 Available: {RemoteStorageController.is_available()}"
                    # )
                    # logger.debug(f"Container Setup Commands: {contain_setup}")

                    # # Enhanced debugging - Check AWS configuration
                    # logger.debug(f"AWS Region: {BATCH_CONFIG.AWS_DEFAULT_REGION}")
                    # logger.debug(
                    #     f"S3 Bucket: {BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME}"
                    # )
                    # logger.debug(
                    #     f"Job Definition: {BATCH_CONFIG.AWS_BATCH_JOB_DEFINITION}"
                    # )

                    # Check current environment variables that will be passed
                    for env_var in envvars:
                        value = os.environ.get(env_var, "NOT_SET")
                        logger.debug(f"Env {env_var}: {value}")

                    # Check AWS credentials (without logging the actual values)
                    # aws_key_exists = "AWS_ACCESS_KEY_ID" in os.environ
                    # aws_secret_exists = "AWS_SECRET_ACCESS_KEY" in os.environ
                    # logger.debug(f"AWS_ACCESS_KEY_ID exists: {aws_key_exists}")
                    # logger.debug(f"AWS_SECRET_ACCESS_KEY exists: {aws_secret_exists}")

                    # Check resource settings
                    # logger.debug(f"Resource settings - nodes: 10, cores: {cores}")
                    # logger.debug("Default resources: mem_mb=4096")

                    # logger.debug("=== CONTAINER COMMAND DEBUG ===")
                    # logger.debug(
                    #     f"Container Image: {batch_executor.get_container_image()}"
                    # )
                    # logger.debug(f"Precommand Setup: {contain_setup}")
                    # logger.debug(
                    #     "Note: Using script-based Snakemake rules with ENTRYPOINT fix"
                    # )
                    # logger.debug(
                    #     "If 'Shell command: None', check container ENTRYPOINT"
                    # )
                    # logger.debug("=== END CONTAINER COMMAND DEBUG ===")

                    # Debug S3 storage configuration - critical for file latency issues
                    # logger.debug("=== S3 STORAGE DEBUG ===")
                    # logger.debug(f"S3 Storage Prefix: {s3_storage}")
                    # logger.debug(f"S3 Bucket: {s3_bucket_name}")
                    # logger.debug(f"S3 Provider: {s3_prefix}")
                    # logger.debug("Increased latency_wait to 300s for S3 consistency")
                    # logger.debug("=== END S3 STORAGE DEBUG ===")

                    # logger.debug("=== AWS BATCH EXECUTION DEBUG ===")

                    # Store start time for monitoring
                    execution_start_time = time.time()
                    logger.info(f"Starting DAG execution at {execution_start_time}")

                    # Start job monitoring before execution
                    logger.info("Starting enhanced job monitoring...")
                    batch_executor.start_job_monitoring()

                    snakemake_result = False

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
                    snakemake_result = True
                    logger.info("AWS Batch workflow execution succeeded.")
                finally:
                    # Restore AWS credentials to environment
                    if aws_access_key is not None:
                        os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key
                    if aws_secret_key is not None:
                        os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_key

            except Exception as e:
                snakemake_result = False
                logger.error(f"AWS Batch workflow execution failed: {e}")
                logger.error(f"Exception details: {str(e)}")
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
            finally:
                # Stop job monitoring
                logger.info("Stopping enhanced job monitoring...")
                batch_executor.stop_job_monitoring()

                smk_logger.extract_errors_from_snakemake_log(smk_workdir)

                if not snakemake_result:
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

    # Post-processing (download results and run workflow observation)
    _post_process_workflow(workspace_id, unique_id, snakemake_result)

    return snakemake_result


def _post_process_workflow(workspace_id: str, unique_id: str, result: bool = False):
    # Download experiment results from S3 if using remote storage and batch mode
    from studio.app.common.core.cloud_batch.batch_config import BATCH_CONFIG

    if result and BATCH_CONFIG.USE_AWS_BATCH and RemoteStorageController.is_available():
        try:
            logger.info("Downloading experiment results from S3 for post-processing")
            remote_controller = RemoteStorageController(
                BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME
            )
            try:
                # Check if we're already in an event loop
                asyncio.get_running_loop()
                logger.warning(
                    "Cannot download experiment results in async context - "
                    "post-processing may fail"
                )
            except RuntimeError:
                # No running loop, safe to create a new one
                asyncio.run(
                    remote_controller.download_experiment(workspace_id, unique_id)
                )
                logger.info(
                    f"Downloaded experiment results for {workspace_id}/{unique_id}"
                )
        except Exception as e:
            logger.error(f"Failed to download experiment results from S3: {e}")
            logger.warning("Post-processing may fail due to missing local files")

    # Update workflow processing results
    try:
        # Check if we're already in an event loop
        asyncio.get_running_loop()
        logger.warning("Cannot run workflow observation in async context - skipping")
    except RuntimeError:
        # No running loop, safe to create a new one
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
