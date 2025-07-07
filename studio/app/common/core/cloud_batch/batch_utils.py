import asyncio
import os
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from studio.app.common.core.cloud_batch.batch_config import BATCH_CONFIG
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.s3_storage_controller import S3StorageController
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.models.user import User
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


class BatchUtils:
    """
    Manages AWS Batch operations for workspace execution.
    """

    def __init__(self, workspace_id: str, unique_id: str):
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.batch_client = boto3.client(
            "batch", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
        )
        self.ecr_client = boto3.client(
            "ecr", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
        )
        self.s3_client = boto3.client("s3", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION)

        # Get current user info for tier-based queue selection
        self.current_user = self._get_current_user()

    def _get_current_user(self) -> Optional[User]:
        """
        Get current user from session or context.
        This would be properly implemented based on your auth system.
        """
        try:
            # This is a placeholder - you'll need to implement proper user retrieval
            # based on your authentication system
            return None
        except Exception:
            logger.warning("Could not retrieve current user, using default settings")
            return None

    def get_job_queue_for_user(self) -> str:
        """
        Determine which AWS Batch job queue to use based on user tier.
        """
        if self.current_user and hasattr(self.current_user, "subscription_tier"):
            if self.current_user.subscription_tier == "paid":
                return BATCH_CONFIG.AWS_BATCH_PAID_QUEUE

        # Default to free tier queue
        return BATCH_CONFIG.AWS_BATCH_FREE_QUEUE

    def get_container_image(self) -> str:
        """
        Get the ECR container image URL for the current deployment.
        """
        try:
            # Get ECR repository URI from terraform outputs or environment
            repository_uri = BATCH_CONFIG.AWS_ECR_REPOSITORY
            return repository_uri
        except Exception as e:
            logger.error(f"Failed to get ECR repository URI: {e}")
            # Fallback to configured value
            return "optinist-for-cloud:latest"

    def prepare_batch_workspace(self):
        """
        Prepare the workspace for AWS Batch execution.
        """
        logger.debug(
            f"Preparing batch workspace for {self.workspace_id}/{self.unique_id}"
        )

        # Upload input files to S3
        self._upload_workspace_to_s3()

        # Create batch-specific configuration file
        batch_config_path = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                self.workspace_id,
                self.unique_id,
                ".batch_config.json",
            ]
        )

        import json

        batch_config = {
            "workspace_id": self.workspace_id,
            "unique_id": self.unique_id,
            "job_queue": self.get_job_queue_for_user(),
            "s3_bucket": BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME,
            "s3_prefix": f"snakemake-tmp/{self.workspace_id}/{self.unique_id}",
        }

        os.makedirs(os.path.dirname(batch_config_path), exist_ok=True)
        with open(batch_config_path, "w") as f:
            json.dump(batch_config, f)

        logger.info(f"Prepared batch workspace with config: {batch_config}")

    def _upload_workspace_to_s3(self):
        """Upload workspace files to S3 before batch execution."""

        s3_controller = S3StorageController()

        # Upload workspace data to S3
        workspace_path = join_filepath(
            [DIRPATH.OUTPUT_DIR, self.workspace_id, self.unique_id]
        )

        logger.info(f"Uploading workspace files to S3: {workspace_path}")
        asyncio.run(s3_controller.upload_experiment(self.workspace_id, self.unique_id))
        logger.info("Workspace upload completed")

    def sync_batch_results(self):
        """
        Sync results from AWS Batch execution back to local storage.
        This is a placeholder for S3 sync operations that will be implemented later.
        """
        logger.info("Syncing batch results (placeholder for S3 sync)")
        # TODO: Implement S3 to local sync when S3 storage is added
        pass

    def monitor_batch_jobs(self, job_ids: list) -> Dict[str, str]:
        """
        Monitor the status of submitted AWS Batch jobs.

        Args:
            job_ids: List of AWS Batch job IDs to monitor

        Returns:
            Dictionary mapping job IDs to their statuses
        """
        job_statuses = {}

        try:
            response = self.batch_client.describe_jobs(jobs=job_ids)

            for job in response["jobs"]:
                job_id = job["jobId"]
                status = job["status"]
                job_statuses[job_id] = status

                if status == "FAILED":
                    reason = job.get("statusReason", "Unknown reason")
                    logger.error(f"Batch job {job_id} failed: {reason}")

        except ClientError as e:
            logger.error(f"Failed to describe batch jobs: {e}")

        return job_statuses

    def wait_for_jobs_completion(self, job_ids: list, timeout: int = 3600) -> bool:
        """
        Wait for all batch jobs to complete.

        Args:
            job_ids: List of AWS Batch job IDs to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if all jobs completed successfully, False otherwise
        """
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                logger.error(f"Timeout waiting for batch jobs after {timeout} seconds")
                return False

            job_statuses = self.monitor_batch_jobs(job_ids)

            # Check if all jobs are in terminal state
            terminal_states = {"SUCCEEDED", "FAILED"}
            all_complete = all(
                status in terminal_states for status in job_statuses.values()
            )

            if all_complete:
                # Check if all succeeded
                all_succeeded = all(
                    status == "SUCCEEDED" for status in job_statuses.values()
                )
                return all_succeeded

            # Wait before checking again
            time.sleep(30)

    def get_job_logs(self, job_id: str) -> Optional[str]:
        """
        Retrieve CloudWatch logs for a specific batch job.

        Args:
            job_id: AWS Batch job ID

        Returns:
            Log content as string or None if not found
        """
        try:
            # Get job details to find log stream
            response = self.batch_client.describe_jobs(jobs=[job_id])
            if not response["jobs"]:
                return None

            job = response["jobs"][0]
            log_stream_name = job.get("container", {}).get("logStreamName")

            if not log_stream_name:
                return None

            # Retrieve logs from CloudWatch
            logs_client = boto3.client(
                "logs", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
            )
            log_group = "/aws/batch/job"

            response = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream_name,
                startFromHead=True,
            )

            # Combine all log messages
            log_messages = [event["message"] for event in response["events"]]
            return "\n".join(log_messages)

        except ClientError as e:
            logger.error(f"Failed to retrieve logs for job {job_id}: {e}")
            return None

    @staticmethod
    def get_batch_environment_info() -> Dict[str, str]:
        """
        Get AWS Batch environment information from environment variables.
        """
        return {
            "job_id": os.environ.get("AWS_BATCH_JOB_ID", ""),
            "job_queue": os.environ.get("AWS_BATCH_JOB_QUEUE", ""),
            "compute_environment": os.environ.get("AWS_BATCH_CE_NAME", ""),
            "job_attempt": os.environ.get("AWS_BATCH_JOB_ATTEMPT", ""),
            "array_index": os.environ.get("AWS_BATCH_JOB_ARRAY_INDEX", ""),
        }

    @staticmethod
    def is_batch_execution() -> bool:
        """
        Check if code is running inside an AWS Batch job.
        """
        return bool(os.environ.get("AWS_BATCH_JOB_ID"))

    @staticmethod
    def get_job_resources() -> Dict[str, int]:
        """
        Get allocated resources for the current batch job.
        """
        # These would be set by the batch job definition
        return {
            "vcpus": int(os.environ.get("AWS_BATCH_JOB_VCPUS", "2")),
            "memory": int(os.environ.get("AWS_BATCH_JOB_MEMORY", "4096")),
        }

    @staticmethod
    def tag_batch_job(job_id: str, tags: Dict[str, str]) -> bool:
        """
        Add tags to an AWS Batch job for tracking and billing.
        """
        try:
            client = boto3.client("batch", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION)

            # Get job ARN first
            response = client.describe_jobs(jobs=[job_id])
            if not response["jobs"]:
                logger.error(f"Job {job_id} not found")
                return False

            job_arn = response["jobs"][0]["jobArn"]

            # Tag the job
            client.tag_resource(resourceArn=job_arn, tags=tags)

            logger.info(f"Tagged job {job_id} with {tags}")
            return True

        except ClientError as e:
            logger.error(f"Failed to tag job {job_id}: {e}")
            return False

    @staticmethod
    def get_tier_resource_limits(tier: str) -> Dict[str, Any]:
        """
        Get resource limits based on subscription tier.
        """
        limits = {
            "free": {
                "max_vcpus": 2,
                "max_memory_mb": 4096,
                "max_runtime_minutes": 60,
                "max_parallel_jobs": 2,
                "priority": 1,
            },
            "paid": {
                "max_vcpus": 8,
                "max_memory_mb": 16384,
                "max_runtime_minutes": 360,
                "max_parallel_jobs": 10,
                "priority": 10,
            },
        }

        return limits.get(tier, limits["free"])

    @staticmethod
    def validate_job_resources(requested: Dict[str, int], tier: str) -> Dict[str, int]:
        """
        Validate and adjust requested resources based on tier limits.
        """
        limits = BatchUtils.get_tier_resource_limits(tier)

        logger.debug(f"Validating resources for tier: {tier}")
        logger.debug(f"Requested resources: {requested}")

        validated = {
            "vcpus": min(requested.get("vcpus", 2), limits["max_vcpus"]),
            "memory": min(requested.get("memory", 4096), limits["max_memory_mb"]),
            "runtime": min(requested.get("runtime", 60), limits["max_runtime_minutes"]),
        }

        # Log if resources were adjusted
        for key, value in validated.items():
            if requested.get(key, value) != value:
                logger.warning(
                    f"Changed {key} from {requested.get(key)} to {value} as {tier} tier"
                )

        return validated

    @staticmethod
    def create_batch_job_name(workspace_id: str, unique_id: str, node_id: str) -> str:
        """
        Create a standardized batch job name.
        """
        # AWS Batch job names have restrictions
        # Must be up to 128 characters, alphanumeric and hyphens
        job_name = f"optinist-{workspace_id}-{unique_id}-{node_id}"
        # Truncate if too long and ensure it's valid
        job_name = job_name[:128]
        # Replace any invalid characters
        job_name = "".join(c if c.isalnum() or c == "-" else "-" for c in job_name)

        return job_name

    @staticmethod
    def parse_snakemake_resources(resources: Dict[str, Any]) -> Dict[str, int]:
        """
        Parse Snakemake resource requirements into AWS Batch format.
        """
        # Convert Snakemake resource specifications to Batch format
        batch_resources = {
            "vcpus": resources.get("cpus", resources.get("threads", 2)),
            "memory": resources.get("mem_mb", 4096),
            "runtime": resources.get("runtime", 60),  # in minutes
        }

        # Handle special resource requirements
        if "gpu" in resources and resources["gpu"] > 0:
            batch_resources["gpu"] = resources["gpu"]

        return batch_resources
