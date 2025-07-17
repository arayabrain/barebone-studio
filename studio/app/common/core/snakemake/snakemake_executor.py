import asyncio
import os
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import boto3
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


def _test_ecr_image_pull(batch_executor) -> None:
    """
    Test if ECR image can be pulled by checking authentication and permissions.
    """
    try:
        container_image = batch_executor.get_container_image()
        if "ecr" not in container_image:
            logger.debug("Not an ECR image, skipping pull test")
            return

        logger.debug("Testing ECR image pull capabilities...")

        # Extract ECR details
        image_parts = container_image.split("/")[-1]
        repo_name = image_parts.split(":")[0]

        try:
            # Test ECR authentication by getting an authorization token
            ecr_client = batch_executor.ecr_client
            auth_response = ecr_client.get_authorization_token()

            if auth_response.get("authorizationData"):
                auth_data = auth_response["authorizationData"][0]
                proxy_endpoint = auth_data.get("proxyEndpoint")
                expires_at = auth_data.get("expiresAt")

                logger.debug("ECR Authentication: SUCCESS")
                logger.debug(f"  Proxy Endpoint: {proxy_endpoint}")
                logger.debug(f"  Token expires: {expires_at}")

                # Test repository access
                try:
                    ecr_client.get_repository_policy(repositoryName=repo_name)
                    logger.debug("ECR Repository Policy: Accessible")
                except ecr_client.exceptions.RepositoryPolicyNotFoundException:
                    logger.debug(
                        "ECR Repository Policy: No policy set "
                        "(using default permissions)"
                    )
                except Exception as policy_error:
                    logger.warning(
                        f"ECR Repository Policy check failed: {policy_error}"
                    )

            else:
                logger.warning("ECR Authentication: No authorization data received")

        except Exception as auth_error:
            logger.warning(f"ECR Authentication failed: {auth_error}")
            logger.warning("This indicates IAM permission issues for ECR access")

    except Exception as e:
        logger.debug(f"ECR image pull test failed: {e}")


def _check_batch_job_memory_usage(batch_executor, job_queue: str) -> None:
    """
    Check memory usage for currently running batch jobs.
    """
    try:
        logger.debug("Checking memory usage for running jobs...")

        # Get currently running jobs
        running_jobs = batch_executor.batch_client.list_jobs(
            jobQueue=job_queue, jobStatus="RUNNING", maxResults=10
        )

        running_job_list = running_jobs.get("jobList", [])
        if not running_job_list:
            logger.debug("No running jobs to check memory usage for")
            return

        logger.debug(f"Checking memory usage for {len(running_job_list)} running jobs:")

        for job in running_job_list:
            job_id = job["jobId"]
            job_name = job.get("jobName", "Unknown")

            try:
                # Get detailed job information
                job_details = batch_executor.batch_client.describe_jobs(jobs=[job_id])
                if job_details.get("jobs"):
                    job_info = job_details["jobs"][0]

                    # Get memory allocation
                    job_def = job_info.get("jobDefinition", "")
                    container = job_info.get("container", {})

                    # Memory allocation from job definition
                    memory_requested = container.get("memory", "Unknown")
                    vcpus_requested = container.get("vcpus", "Unknown")

                    logger.debug(f" Job {job_name}:")
                    logger.debug(f"Job Definition: {job_def}")
                    logger.debug(
                        f"Allocated: {memory_requested}MB memory, "
                        f"{vcpus_requested} vCPUs"
                    )

                    # Try to get CloudWatch memory metrics if available
                    try:
                        cloudwatch = boto3.client(
                            "cloudwatch", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
                        )

                        # Get memory utilization metrics
                        end_time = datetime.now()
                        start_time = end_time - timedelta(minutes=10)

                        # Check for memory utilization metrics
                        # Note: These require CloudWatch Container Insights
                        try:
                            memory_metrics = cloudwatch.get_metric_statistics(
                                Namespace="AWS/ECS",  # ECS metrics for Batch
                                MetricName="MemoryUtilization",
                                Dimensions=[{"Name": "ServiceName", "Value": job_name}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=300,  # 5-minute periods
                                Statistics=["Average", "Maximum"],
                            )

                            datapoints = memory_metrics.get("Datapoints", [])
                            if datapoints:
                                latest = max(datapoints, key=lambda x: x["Timestamp"])
                                avg_mem = latest.get("Average", 0)
                                max_mem = latest.get("Maximum", 0)
                                logger.debug(
                                    f"Mem Use: {avg_mem:.1f}% avg, {max_mem:.1f}% max"
                                )
                            else:
                                logger.debug(
                                    "No memory metrics available "
                                    "(Container Insights may not be enabled)"
                                )

                        except Exception as metrics_error:
                            logger.debug(
                                f"    Could not get memory metrics: {metrics_error}"
                            )

                    except Exception as cw_error:
                        logger.debug(f"    CloudWatch check failed: {cw_error}")

                    # Check for OOM killer in logs if available
                    log_stream = container.get("logStreamName")
                    if log_stream:
                        try:
                            logs_client = boto3.client(
                                "logs", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
                            )

                            # Get recent logs to check for memory issues
                            log_events = logs_client.get_log_events(
                                logGroupName="/aws/batch/job",
                                logStreamName=log_stream,
                                limit=20,
                                startFromHead=False,
                            )

                            # Look for memory-related errors
                            for event in log_events.get("events", []):
                                message = event["message"].lower()
                                if any(
                                    keyword in message
                                    for keyword in [
                                        "oom",
                                        "out of memory",
                                        "memory",
                                        "killed",
                                        "exit code 137",
                                    ]
                                ):
                                    logger.warning(
                                        "    Memory issue detected: "
                                        f"{event['message'][:100]}..."
                                    )

                        except Exception as log_error:
                            logger.debug(
                                "    Could not check logs for memory issues: "
                                f"{log_error}"
                            )

            except Exception as job_error:
                logger.warning(
                    f"  Could not check memory for job {job_name}: {job_error}"
                )

    except Exception as e:
        logger.debug(f"Memory usage check failed: {e}")


def _debug_batch_environment(batch_executor) -> None:
    """
    Debug AWS Batch environment status and recent job failures.
    Provides immediate visibility into batch environment health.
    """
    try:
        logger.info("=== AWS BATCH ENVIRONMENT DEBUG ===")

        # Get job queue for user
        job_queue = batch_executor.get_job_queue_for_user()
        logger.info(f"Target Job Queue: {job_queue}")

        # 1. Check job queue status
        logger.debug("Checking job queue status...")
        queues = batch_executor.batch_client.describe_job_queues(jobQueues=[job_queue])
        if queues.get("jobQueues"):
            queue = queues["jobQueues"][0]
            queue_state = queue.get("state", "UNKNOWN")
            queue_status = queue.get("status", "UNKNOWN")
            logger.info(f"Job Queue State: {queue_state}, Status: {queue_status}")

            if queue_state != "ENABLED":
                logger.warning(f"Job queue is not enabled: {queue_state}")

            # Check compute environments
            compute_envs = queue.get("computeEnvironmentOrder", [])
            logger.info(f"Compute Environments: {len(compute_envs)}")

            for ce in compute_envs:
                ce_name = ce["computeEnvironment"]
                logger.debug(f"Checking compute environment: {ce_name}")

                try:
                    ce_details = (
                        batch_executor.batch_client.describe_compute_environments(
                            computeEnvironments=[ce_name]
                        )
                    )
                    if ce_details.get("computeEnvironments"):
                        ce_info = ce_details["computeEnvironments"][0]
                        ce_state = ce_info.get("state", "UNKNOWN")
                        ce_status = ce_info.get("status", "UNKNOWN")
                        logger.info(
                            f"  CE {ce_name}: state={ce_state}, status={ce_status}"
                        )

                        # Check resource limits
                        if "computeResources" in ce_info:
                            resources = ce_info["computeResources"]
                            max_vcpus = resources.get("maxvCpus", "N/A")
                            desired_vcpus = resources.get("desiredvCpus", "N/A")
                            logger.info(
                                f"  Resources: max_vCPUs={max_vcpus}, "
                                f"desired_vCPUs={desired_vcpus}"
                            )

                        if ce_state != "ENABLED" or ce_status not in [
                            "VALID",
                            "UPDATING",
                        ]:
                            logger.warning(
                                f"  CE {ce_name} may have issues: "
                                f"{ce_state}/{ce_status}"
                            )
                except Exception as ce_error:
                    logger.warning(
                        f"  Could not get details for CE {ce_name}: {ce_error}"
                    )
        else:
            logger.error(f"Job queue '{job_queue}' not found!")
            return

        # 2. Check current job status
        logger.debug("Checking current job counts...")
        for status in ["RUNNABLE", "STARTING", "RUNNING"]:
            try:
                jobs = batch_executor.batch_client.list_jobs(
                    jobQueue=job_queue, jobStatus=status, maxResults=50
                )
                job_count = len(jobs.get("jobList", []))
                logger.info(f"{status} jobs: {job_count}")

                # Show details for stuck STARTING jobs
                if status == "STARTING" and job_count > 0:
                    logger.warning(f"Found {job_count} jobs stuck in STARTING state:")
                    for job in jobs["jobList"][:3]:  # Show first 3
                        job_name = job.get("jobName", "Unknown")
                        created_at = job.get("createdAt", 0)
                        if created_at:
                            created_time = datetime.fromtimestamp(created_at / 1000)
                            duration = datetime.now() - created_time
                            logger.warning(f"  {job_name}: stuck for {duration}")
            except Exception as status_error:
                logger.warning(f"Could not check {status} jobs: {status_error}")

        # 3. Check recent failed jobs
        logger.debug("Checking recent failed jobs...")
        try:
            failed_jobs = batch_executor.batch_client.list_jobs(
                jobQueue=job_queue, jobStatus="FAILED", maxResults=5
            )

            failed_count = len(failed_jobs.get("jobList", []))
            logger.info(f"Recent failed jobs: {failed_count}")

            if failed_count > 0:
                logger.warning("Recent failure details:")
                for job in failed_jobs["jobList"][:3]:  # Show first 3 failures
                    job_id = job["jobId"]
                    job_name = job.get("jobName", "Unknown")

                    # Get detailed failure info
                    try:
                        job_details = batch_executor.batch_client.describe_jobs(
                            jobs=[job_id]
                        )
                        if job_details.get("jobs"):
                            job_info = job_details["jobs"][0]
                            status_reason = job_info.get("statusReason", "Unknown")
                            container = job_info.get("container", {})
                            exit_code = container.get("exitCode", "N/A")
                            exit_reason = container.get("reason", "Unknown")

                            logger.warning(
                                f"  {job_name}: exit_code={exit_code}, "
                                f"reason='{exit_reason}'"
                            )
                            logger.warning(f"    Status: {status_reason}")
                    except Exception as detail_error:
                        logger.warning(
                            f"  {job_name}: Could not get details - {detail_error}"
                        )
        except Exception as failed_error:
            logger.warning(f"Could not check failed jobs: {failed_error}")

        # 4. Check ECR image accessibility and recent pulls
        logger.debug("Checking ECR image status...")
        try:
            container_image = batch_executor.get_container_image()
            logger.info(f"Container Image: {container_image}")

            if "ecr" in container_image:
                # Extract repository name and tag
                image_parts = container_image.split("/")[-1]
                repo_name = image_parts.split(":")[0]
                image_tag = (
                    image_parts.split(":")[1] if ":" in image_parts else "latest"
                )

                logger.debug(f"ECR Repository: {repo_name}, Tag: {image_tag}")

                try:
                    # Check repository existence and latest push
                    repo_details = batch_executor.ecr_client.describe_repositories(
                        repositoryNames=[repo_name]
                    )
                    if repo_details.get("repositories"):
                        repo = repo_details["repositories"][0]
                        created_at = repo.get("createdAt")
                        registry_id = repo.get("registryId")
                        logger.info(
                            f"ECR Repository: {repo_name} exists "
                            f"(registry: {registry_id})"
                        )

                        # Check image details
                        try:
                            images = batch_executor.ecr_client.describe_images(
                                repositoryName=repo_name,
                                imageIds=[{"imageTag": image_tag}],
                            )
                            if images.get("imageDetails"):
                                image_detail = images["imageDetails"][0]
                                image_size = image_detail.get("imageSizeInBytes", 0)
                                pushed_at = image_detail.get("imagePushedAt")
                                logger.info(
                                    f"Image {image_tag}: {image_size/1024/1024:.1f}MB, "
                                    f"pushed: {pushed_at}"
                                )
                            else:
                                logger.warning(
                                    f"Image tag '{image_tag}' not found in repository"
                                )
                        except Exception as img_error:
                            logger.warning(f"Could not get image details: {img_error}")

                except Exception as ecr_error:
                    logger.warning(f"ECR check failed: {ecr_error}")
                    # This might indicate permission issues

        except Exception as container_error:
            logger.warning(f"Container image check failed: {container_error}")

        # Test ECR image pull capabilities
        _test_ecr_image_pull(batch_executor)

        # 5. Check CloudWatch metrics for compute environment instances
        logger.debug("Checking compute environment metrics...")
        try:
            cloudwatch = boto3.client(
                "cloudwatch", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
            )

            # Get compute environment names
            for ce in compute_envs:
                ce_name = ce["computeEnvironment"]
                logger.debug(f"Checking metrics for CE: {ce_name}")

                try:
                    # Get EC2 instances in the compute environment
                    # Note: This is approximate,
                    # AWS Batch doesn't directly expose instance metrics
                    end_time = datetime.now()
                    start_time = end_time - timedelta(minutes=30)

                    # Check for common CloudWatch metrics that might indicate issues
                    metrics_to_check = [
                        "AWS/Batch",  # Batch service metrics
                        "AWS/EC2",  # EC2 instance metrics
                    ]

                    for namespace in metrics_to_check:
                        try:
                            # List available metrics
                            metrics = cloudwatch.list_metrics(
                                Namespace=namespace,
                                Dimensions=[{"Name": "JobQueue", "Value": job_queue}],
                            )

                            if metrics.get("Metrics"):
                                logger.info(
                                    f"Found {len(metrics['Metrics'])} "
                                    f"CloudWatch metrics for {namespace}"
                                    f" at start_time={start_time}, end_time={end_time}"
                                )

                                # Check specific useful metrics
                                for metric in metrics["Metrics"][:3]:  # First 3 metrics
                                    metric_name = metric["MetricName"]
                                    logger.debug(f"  Available metric: {metric_name}")

                        except Exception as metric_error:
                            logger.debug(
                                f"Could not check {namespace} metrics: {metric_error}"
                            )

                except Exception as ce_metric_error:
                    logger.debug(
                        f"Could not get metrics for CE {ce_name}: {ce_metric_error}"
                    )

        except Exception as cw_error:
            logger.debug(f"CloudWatch metrics check failed: {cw_error}")

        # 6. Check for recent container startup logs
        logger.debug("Checking recent container logs for startup issues...")
        try:
            logs_client = boto3.client(
                "logs", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
            )

            # Look for recent log streams in the batch log group
            log_group = "/aws/batch/job"
            try:
                log_streams = logs_client.describe_log_streams(
                    logGroupName=log_group,
                    orderBy="LastEventTime",
                    descending=True,
                    limit=5,
                )

                recent_streams = len(log_streams.get("logStreams", []))
                logger.info(f"Recent log streams in {log_group}: {recent_streams}")

                # Check the most recent log stream for container startup issues
                if log_streams.get("logStreams"):
                    latest_stream = log_streams["logStreams"][0]
                    stream_name = latest_stream["logStreamName"]
                    last_event = latest_stream.get("lastEventTime", 0)

                    if last_event:
                        last_event_time = datetime.fromtimestamp(last_event / 1000)
                        time_ago = datetime.now() - last_event_time
                        logger.info(
                            f"Latest log stream: {stream_name} ({time_ago} ago)"
                        )

                        # Get recent log events to check for container issues
                        try:
                            log_events = logs_client.get_log_events(
                                logGroupName=log_group,
                                logStreamName=stream_name,
                                limit=10,
                                startFromHead=False,  # Get most recent
                            )

                            events = log_events.get("events", [])
                            if events:
                                logger.debug("Recent container log messages:")
                                for event in events[-3:]:  # Last 3 messages
                                    message = event["message"]
                                    # Look for common container startup issues
                                    if any(
                                        keyword in message.lower()
                                        for keyword in [
                                            "error",
                                            "failed",
                                            "timeout",
                                            "permission",
                                            "denied",
                                            "pull",
                                        ]
                                    ):
                                        logger.warning(
                                            f"  Issue found: {message[:100]}..."
                                        )
                                    else:
                                        logger.debug(f"  {message[:80]}...")
                        except Exception as events_error:
                            logger.debug(f"Could not get log events: {events_error}")

            except logs_client.exceptions.ResourceNotFoundException:
                logger.warning(
                    f"Log group {log_group} not found - no container logs available"
                )
            except Exception as logs_error:
                logger.debug(f"Could not check log streams: {logs_error}")

        except Exception as log_check_error:
            logger.debug(f"Container log check failed: {log_check_error}")

        # 7. Check memory usage for running jobs
        logger.debug("Checking memory usage for running jobs...")
        _check_batch_job_memory_usage(batch_executor, job_queue)

        logger.info("=== END BATCH ENVIRONMENT DEBUG ===")

    except Exception as e:
        logger.error(f"Batch environment debug failed: {e}")
        # Don't let debug failure break the main execution


def _validate_batch_configuration(batch_executor) -> bool:
    """
    Validate AWS Batch configuration before execution.
    Returns True if configuration is valid, False otherwise.
    """
    try:
        logger.info("Validating AWS Batch configuration...")

        # Check if we can access the batch service
        job_queue = batch_executor.get_job_queue_for_user()

        # Test batch client connectivity
        logger.debug("Testing AWS Batch client connectivity...")
        queues = batch_executor.batch_client.describe_job_queues(jobQueues=[job_queue])

        if not queues.get("jobQueues"):
            logger.error(f"Job queue '{job_queue}' not found or inaccessible")
            return False

        queue_info = queues["jobQueues"][0]
        queue_state = queue_info.get("state", "UNKNOWN")
        logger.info(f"Job queue '{job_queue}' state: {queue_state}")

        if queue_state != "ENABLED":
            logger.error(
                f"Job queue '{job_queue}' is not enabled (state: {queue_state})"
            )
            return False

        # Check compute environment status
        compute_envs = queue_info.get("computeEnvironmentOrder", [])
        for ce in compute_envs:
            ce_name = ce.get("computeEnvironment")
            logger.debug(f"Checking compute environment: {ce_name}")

            ce_details = batch_executor.batch_client.describe_compute_environments(
                computeEnvironments=[ce_name]
            )

            if ce_details.get("computeEnvironments"):
                ce_state = ce_details["computeEnvironments"][0].get("state", "UNKNOWN")
                ce_status = ce_details["computeEnvironments"][0].get(
                    "status", "UNKNOWN"
                )
                logger.info(
                    f"Compute environment '{ce_name}' - state: {ce_state}, "
                    f"status: {ce_status}"
                )

                if ce_state != "ENABLED" or ce_status not in ["VALID", "UPDATING"]:
                    logger.warning(f"Compute environment '{ce_name}' may have issues")

        # Check container image accessibility
        container_image = batch_executor.get_container_image()
        logger.info(f"Container image: {container_image}")

        # Try to describe the ECR repository if using ECR
        if "ecr" in container_image:
            try:
                repo_name = container_image.split("/")[-1].split(":")[0]
                logger.debug(f"Checking ECR repository: {repo_name}")
                batch_executor.ecr_client.describe_repositories(
                    repositoryNames=[repo_name]
                )
                logger.debug("ECR repository accessible")
            except Exception as ecr_error:
                logger.warning(f"ECR repository check failed: {ecr_error}")

        logger.info("AWS Batch configuration validation completed successfully")
        return True

    except Exception as e:
        logger.error(f"AWS Batch configuration validation failed: {e}")
        return False


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

        # Debug AWS Batch environment status for immediate visibility
        logger.info("Debugging AWS Batch environment...")
        _debug_batch_environment(batch_executor)

        # Validate AWS Batch configuration before proceeding
        logger.info("Validating AWS Batch configuration...")
        if not _validate_batch_configuration(batch_executor):
            logger.error(
                "AWS Batch configuration validation failed - aborting execution"
            )
            return False

        # Prepare workspace for batch execution
        logger.debug("Prepare batch workspace")
        batch_executor.prepare_batch_workspace()

        # cores = getattr(params, "cores", 2)
        cores = 2  # Set consistent cores for debugging
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
                    default_resources=DefaultResources(["mem_mb=4096"]),
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

                # Temporarily remove AWS credentials from environment for batch jobs
                # Forces batch jobs to use IAM roles instead of hardcoded credentials
                aws_access_key = os.environ.pop("AWS_ACCESS_KEY_ID", None)
                aws_secret_key = os.environ.pop("AWS_SECRET_ACCESS_KEY", None)

                try:
                    # Prepare environment variables for batch jobs
                    envvars = ["USE_AWS_BATCH"]
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
                    container_setup = []
                    if not RemoteStorageController.is_available():
                        container_setup = _get_batch_container_setup_commands()

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
                    logger.debug(f"Container Setup Commands: {container_setup}")

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

                    logger.debug("=== AWS BATCH EXECUTION DEBUG ===")

                    # Store start time for monitoring
                    execution_start_time = time.time()
                    logger.info(f"Starting DAG execution at {execution_start_time}")

                    try:
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
                                task_timeout=1800,  # Increase timeout to 30 minutes
                            ),
                            remote_execution_settings=RemoteExecutionSettings(
                                container_image=batch_executor.get_container_image(),
                                envvars=envvars,
                                jobname="optinist-{rulename}-{jobid}",
                                # Add container setup commands for EFS optimization
                                precommand=container_setup if container_setup else None,
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
                            recent_jobs = batch_executor.get_recent_failed_jobs(limit=3)
                            if recent_jobs:
                                logger.error(
                                    f"Found {len(recent_jobs)} recent failed jobs"
                                )

                                for i, job_id in enumerate(recent_jobs):
                                    logger.error(f"Failed job {i+1}: {job_id}")

                                    # Get detailed job information
                                    job_details = (
                                        batch_executor.batch_client.describe_jobs(
                                            jobs=[job_id]
                                        )
                                    )
                                    if job_details and job_details.get("jobs"):
                                        job = job_details["jobs"][0]
                                        logger.error(f"  Status: {job.get('status')}")
                                        logger.error(
                                            f"Status Reason:{job.get('statusReason')}"
                                        )
                                        logger.error(f"Created: {job.get('createdAt')}")
                                        logger.error(f"Started: {job.get('startedAt')}")
                                        logger.error(f"Stopped: {job.get('stoppedAt')}")

                                        # Container details
                                        container = job.get("container", {})
                                        logger.error(
                                            f"Exit Code: {container.get('exitCode')}"
                                        )
                                        logger.error(
                                            f"Exit Reason: {container.get('reason')}"
                                        )
                                        logger.error(
                                            f"Log Stream: "
                                            f"{container.get('logStreamName')}"
                                        )

                                        # Attempts details
                                        attempts = job.get("attempts", [])
                                        logger.error(f"  Attempts: {len(attempts)}")
                                        if attempts:
                                            latest_attempt = attempts[-1]
                                            logger.error(
                                                f"Latest attempt started: "
                                                f"{latest_attempt.get('startedAt')}"
                                            )
                                            logger.error(
                                                f"Latest attempt stopped: "
                                                f"{latest_attempt.get('stoppedAt')}"
                                            )
                                            logger.error(
                                                f"Latest attempt reason: "
                                                f"{latest_attempt.get('statusReason')}"
                                            )

                                        # Job definition details
                                        job_def = job.get("jobDefinition")
                                        if job_def:
                                            logger.error(f"  Job Definition: {job_def}")

                                        # Platform capabilities
                                        platform_caps = job.get(
                                            "platformCapabilities", []
                                        )
                                        logger.error(
                                            f"  Platform Capabilities: {platform_caps}"
                                        )

                                        # Get logs if available
                                        log_stream = container.get("logStreamName")
                                        if log_stream:
                                            try:
                                                job_logs = batch_executor.get_job_logs(
                                                    job_id
                                                )
                                                if job_logs:
                                                    # Only show last few lines
                                                    log_lines = job_logs.split("\n")[
                                                        -10:
                                                    ]
                                                    logger.error("Recent log lines:")
                                                    for line in log_lines:
                                                        if line.strip():
                                                            logger.error(f"{line}")
                                            except Exception as log_error:
                                                logger.error(
                                                    f"  Could not retrieve logs: "
                                                    f"{log_error}"
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
            except Exception as e:
                result = False
                logger.error(f"AWS Batch workflow execution failed: {e}")
                logger.error(f"Exception details: {str(e)}")
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
            finally:
                smk_logger.extract_errors_from_snakemake_log(smk_workdir)
                # Sync results back from batch execution
                # batch_executor.sync_batch_results()

                if not result:
                    logger.error(
                        "AWS Batch execution failed - attempting to retrieve job logs"
                    )
                    try:
                        # Get recent failed jobs and their logs
                        recent_jobs = batch_executor.get_recent_failed_jobs()
                        for job_id in recent_jobs[:3]:  # Only check last 3 failed jobs
                            job_logs = batch_executor.get_job_logs(job_id)
                            if job_logs:
                                logger.error(f"Batch Job {job_id} logs:\n{job_logs}")
                    except Exception as log_error:
                        logger.error(f"Failed to retrieve batch job logs: {log_error}")

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
