import asyncio
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from snakemake.api import SharedFSUsage, StorageSettings

from studio.app.common.core.cloud_batch.batch_config import BATCH_CONFIG
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.s3_storage_controller import S3StorageController
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.models.user import User
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


class JobMonitoringThread(threading.Thread):
    """
    Background thread to monitor AWS Batch job health and capture logs before failure.
    """

    def __init__(self, batch_client, logs_client, monitoring_interval=10):
        super().__init__(daemon=True)
        self.batch_client = batch_client
        self.logs_client = logs_client
        self.monitoring_interval = monitoring_interval
        self.monitoring_active = False
        self.active_jobs = set()
        self.job_metadata_cache = {}
        self.job_logs_cache = {}
        self.job_start_times = {}
        self._lock = threading.Lock()

    def add_job(self, job_id: str, job_name: str = None):
        """Add a job to monitoring."""
        with self._lock:
            self.active_jobs.add(job_id)
            self.job_start_times[job_id] = datetime.now()
            logger.debug(f"Added job {job_id} to monitoring")

    def remove_job(self, job_id: str):
        """Remove a job from monitoring."""
        with self._lock:
            self.active_jobs.discard(job_id)
            self.job_start_times.pop(job_id, None)
            # Keep cached data for failure analysis
            logger.debug(f"Removed job {job_id} from active monitoring")

    def start_monitoring(self):
        """Start the monitoring thread."""
        self.monitoring_active = True
        self.start()
        logger.info("Job monitoring thread started")

    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self.monitoring_active = False
        logger.info("Job monitoring thread stopped")

    def run(self):
        """Main monitoring loop."""
        logger.info("Job monitoring thread running")
        while self.monitoring_active:
            try:
                self._monitor_jobs()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in job monitoring thread: {e}")
                time.sleep(self.monitoring_interval)

    def _monitor_jobs(self):
        """Monitor all active jobs for signs of distress."""
        if not self.active_jobs:
            return

        jobs_to_check = list(self.active_jobs)
        logger.debug(f"Monitoring {len(jobs_to_check)} active jobs")

        try:
            # Batch describe jobs call for efficiency
            response = self.batch_client.describe_jobs(jobs=jobs_to_check)

            for job in response.get("jobs", []):
                job_id = job["jobId"]

                # Store job metadata for failure analysis
                self._store_job_metadata(job_id, job)

                # Check if job is at risk of failure
                if self._is_job_at_risk(job):
                    logger.warning(f"Job {job_id} showing signs of distress")
                    self._capture_job_logs_preemptively(job_id, job)

        except Exception as e:
            logger.error(f"Failed to monitor jobs: {e}")

    def _is_job_at_risk(self, job: Dict) -> bool:
        """Detect early warning signs of job failure."""
        job_status = job.get("jobStatus", "")

        # Check for concerning patterns
        risk_indicators = [
            self._is_job_stuck(job),
            self._has_memory_pressure(job),
            self._has_concerning_status(job_status),
            self._is_long_running_without_progress(job),
        ]

        return any(risk_indicators)

    def _is_job_stuck(self, job: Dict) -> bool:
        """Check if job appears stuck."""
        job_status = job.get("jobStatus", "")
        started_at = job.get("startedAt")

        if job_status == "RUNNING" and started_at:
            # Convert timestamp to datetime
            start_time = datetime.fromtimestamp(started_at / 1000)
            running_duration = datetime.now() - start_time

            # Consider stuck if running > 20 minutes without completion
            if running_duration > timedelta(minutes=20):
                logger.warning(
                    f"Job {job['jobId']} has been running for {running_duration}"
                )
                return True

        return False

    def _has_memory_pressure(self, job: Dict) -> bool:
        """Check if job is experiencing memory pressure."""
        # This would require CloudWatch metrics integration
        # For now, we'll look for memory-related patterns in logs
        job_id = job["jobId"]

        try:
            # Get recent logs to check for memory issues
            container = job.get("container", {})
            log_stream = container.get("logStreamName")

            if log_stream:
                recent_logs = self._get_recent_logs(log_stream, limit=10)
                if recent_logs:
                    log_text = "\n".join(
                        [event.get("message", "") for event in recent_logs]
                    )
                    memory_keywords = [
                        "out of memory",
                        "oom",
                        "memory error",
                        "allocation failed",
                    ]

                    for keyword in memory_keywords:
                        if keyword.lower() in log_text.lower():
                            return True

        except Exception as e:
            logger.debug(f"Could not check memory pressure for job {job_id}: {e}")

        return False

    def _has_concerning_status(self, job_status: str) -> bool:
        """Check if job status indicates potential issues."""
        concerning_statuses = ["PENDING", "RUNNABLE"]  # Stuck in queue
        return job_status in concerning_statuses

    def _is_long_running_without_progress(self, job: Dict) -> bool:
        """Check if job has been running unusually long."""
        job_id = job["jobId"]
        start_time = self.job_start_times.get(job_id)

        if start_time:
            duration = datetime.now() - start_time
            # Consider long-running if > 30 minutes
            return duration > timedelta(minutes=30)

        return False

    def _capture_job_logs_preemptively(self, job_id: str, job: Dict):
        """Capture CloudWatch logs for jobs that might be about to fail."""
        try:
            container = job.get("container", {})
            log_stream = container.get("logStreamName")

            if log_stream:
                # Get recent logs
                logs = self._get_recent_logs(log_stream, limit=50)

                if logs:
                    # Store logs with timestamp for failure analysis
                    self._store_job_logs_snapshot(job_id, logs)
                    logger.info(f"Captured preemptive logs for job {job_id}")

        except Exception as e:
            logger.warning(f"Failed to capture preemptive logs for {job_id}: {e}")

    def _get_recent_logs(self, log_stream_name: str, limit: int = 50) -> List[Dict]:
        """Get recent log events from CloudWatch."""
        try:
            log_group = "/aws/batch/job"

            response = self.logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream_name,
                limit=limit,
                startFromHead=False,  # Get most recent logs
            )

            return response.get("events", [])

        except Exception as e:
            logger.debug(f"Could not get recent logs for {log_stream_name}: {e}")
            return []

    def _store_job_metadata(self, job_id: str, job: Dict):
        """Store job metadata for failure analysis."""
        with self._lock:
            self.job_metadata_cache[job_id] = {
                "timestamp": datetime.now(),
                "job_data": job,
                "status": job.get("jobStatus"),
                "status_reason": job.get("statusReason", ""),
                "started_at": job.get("startedAt"),
                "stopped_at": job.get("stoppedAt"),
            }

    def _store_job_logs_snapshot(self, job_id: str, logs: List[Dict]):
        """Store log snapshot for failure analysis."""
        with self._lock:
            if job_id not in self.job_logs_cache:
                self.job_logs_cache[job_id] = []

            self.job_logs_cache[job_id].append(
                {"timestamp": datetime.now(), "logs": logs}
            )

            # Keep only last 5 snapshots per job
            self.job_logs_cache[job_id] = self.job_logs_cache[job_id][-5:]

    def get_job_failure_context(self, job_id: str) -> Dict:
        """Get stored failure context for a job."""
        with self._lock:
            return {
                "metadata": self.job_metadata_cache.get(job_id, {}),
                "log_snapshots": self.job_logs_cache.get(job_id, []),
                "monitoring_duration": self._get_monitoring_duration(job_id),
            }

    def _get_monitoring_duration(self, job_id: str) -> Optional[timedelta]:
        """Get how long a job was monitored."""
        start_time = self.job_start_times.get(job_id)
        if start_time:
            return datetime.now() - start_time
        return None

    def clear_job_data(self, job_id: str):
        """Clear cached data for a job."""
        with self._lock:
            self.job_metadata_cache.pop(job_id, None)
            self.job_logs_cache.pop(job_id, None)
            self.job_start_times.pop(job_id, None)


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
        self.logs_client = boto3.client(
            "logs", region_name=BATCH_CONFIG.AWS_DEFAULT_REGION
        )

        # Get current user info for tier-based queue selection
        self.current_user = self._get_current_user()

        # Initialize job monitoring thread
        self.job_monitor = JobMonitoringThread(
            batch_client=self.batch_client,
            logs_client=self.logs_client,
            monitoring_interval=10,
        )
        self.monitoring_enabled = True

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
        Tries multiple methods to get user information with fallbacks.
        """
        try:
            # First try: use the current_user from class initialization
            if self.current_user and hasattr(self.current_user, "subscription_tier"):
                tier = self.current_user.subscription_tier
                user_name = getattr(self.current_user, "name", "unknown")

                if tier == "paid":
                    logger.info(f"Using paid tier queue for user: {user_name}")
                    return BATCH_CONFIG.AWS_BATCH_PAID_QUEUE
                else:
                    logger.info(f"Using free tier queue for user: {user_name}")
                    return BATCH_CONFIG.AWS_BATCH_FREE_QUEUE

            # Second try: get user context from database
            from studio.app.common.core.cloud.cloud_utils import (
                get_current_user_context,
            )

            current_user = get_current_user_context()

            if current_user and isinstance(current_user, dict):
                tier = current_user.get("subscription_tier", "free")
                user_name = current_user.get("name", "unknown")

                if tier == "paid":
                    logger.info(f"Using paid tier queue for user: {user_name}")
                    return BATCH_CONFIG.AWS_BATCH_PAID_QUEUE
                else:
                    logger.info(f"Using free tier queue for user: {user_name}")
                    return BATCH_CONFIG.AWS_BATCH_FREE_QUEUE

        except Exception as e:
            logger.warning(f"Failed to determine user tier: {e}")

        # Default to free tier queue
        logger.info("Defaulting to free tier queue")
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
        # self._upload_workspace_to_s3()

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
            "s3_prefix": "subscr-optinist/",
        }

        os.makedirs(os.path.dirname(batch_config_path), exist_ok=True)
        with open(batch_config_path, "w") as f:
            json.dump(batch_config, f)

        logger.info(f"Prepared batch workspace with config: {batch_config}")

    def _upload_workspace_to_s3(self):
        """Upload workspace files to S3 before batch execution."""

        s3_controller = S3StorageController(
            bucket_name=BATCH_CONFIG.AWS_BATCH_S3_BUCKET_NAME
        )

        # Upload workspace data to S3
        workspace_path = join_filepath(
            [DIRPATH.OUTPUT_DIR, self.workspace_id, self.unique_id]
        )

        logger.info(f"Uploading workspace files to S3: {workspace_path}")
        asyncio.run(s3_controller.upload_experiment(self.workspace_id, self.unique_id))
        logger.info("Workspace upload completed")

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

    def get_recent_failed_jobs(
        self, limit: int = 5, include_context: bool = True
    ) -> List[Dict]:
        """
        Get recent failed batch jobs with detailed context for debugging.

        Args:
            limit: Maximum number of failed jobs to return
            include_context: Whether to include detailed failure context

        Returns:
            List of dictionaries containing job IDs and failure context
        """
        try:
            # List jobs in FAILED state
            response = self.batch_client.list_jobs(
                jobQueue=self.get_job_queue_for_user(),
                jobStatus="FAILED",
                maxResults=limit,
            )

            failed_jobs = []
            for job in response.get("jobList", []):
                job_id = job["jobId"]

                if include_context:
                    # Get detailed job information before cleanup
                    job_context = self._get_enhanced_job_failure_context(job_id, job)
                    failed_jobs.append(job_context)
                else:
                    # Legacy behavior - return just job IDs
                    failed_jobs.append(job_id)

            logger.info(f"Found {len(failed_jobs)} recent failed jobs")
            return failed_jobs

        except ClientError as e:
            logger.error(f"Failed to list recent failed jobs: {e}")
            return []

    def _get_enhanced_job_failure_context(self, job_id: str, job_summary: Dict) -> Dict:
        """
        Get enhanced failure context for a specific job.

        Args:
            job_id: AWS Batch job ID
            job_summary: Basic job information from list_jobs

        Returns:
            Dictionary with comprehensive failure context
        """
        failure_context = {
            "job_id": job_id,
            "job_name": job_summary.get("jobName", "Unknown"),
            "created_at": job_summary.get("createdAt"),
            "started_at": job_summary.get("startedAt"),
            "stopped_at": job_summary.get("stoppedAt"),
            "job_details": None,
            "logs": None,
            "monitoring_context": None,
            "failure_analysis": None,
        }

        try:
            # Get detailed job information
            job_details_response = self.batch_client.describe_jobs(jobs=[job_id])
            if job_details_response.get("jobs"):
                job_details = job_details_response["jobs"][0]
                failure_context["job_details"] = job_details

                # Extract key failure information
                container = job_details.get("container", {})
                failure_context.update(
                    {
                        "exit_code": container.get("exitCode"),
                        "exit_reason": container.get("reason", "Unknown"),
                        "status_reason": job_details.get("statusReason", "Unknown"),
                        "log_stream_name": container.get("logStreamName"),
                        "job_definition": job_details.get("jobDefinition"),
                        "platform_capabilities": job_details.get(
                            "platformCapabilities", []
                        ),
                    }
                )

                # Get logs if available
                log_stream = container.get("logStreamName")
                if log_stream:
                    failure_context["logs"] = self._get_job_logs_with_context(
                        job_id, log_stream
                    )

            # Get monitoring context if available
            if hasattr(self, "job_monitor"):
                monitoring_context = self.job_monitor.get_job_failure_context(job_id)
                if monitoring_context.get("metadata") or monitoring_context.get(
                    "log_snapshots"
                ):
                    failure_context["monitoring_context"] = monitoring_context

            # Analyze failure patterns
            failure_context["failure_analysis"] = self._analyze_job_failure(
                failure_context
            )

        except Exception as e:
            logger.error(f"Failed to get enhanced context for job {job_id}: {e}")
            failure_context["context_error"] = str(e)

        return failure_context

    def _get_job_logs_with_context(
        self, job_id: str, log_stream_name: str, limit: int = 100
    ) -> Dict:
        """
        Get job logs with additional context for failure analysis.

        Returns:
            Dictionary containing logs and analysis
        """
        try:
            log_group = "/aws/batch/job"

            # Get recent log events
            response = self.logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream_name,
                limit=limit,
                startFromHead=False,
            )

            events = response.get("events", [])

            return {
                "log_events": events,
                "log_stream_name": log_stream_name,
                "total_events": len(events),
                "last_event_time": events[-1].get("timestamp") if events else None,
                "error_patterns": self._identify_error_patterns_in_logs(events),
                "log_summary": self._summarize_logs(events),
            }

        except Exception as e:
            logger.warning(f"Failed to get logs for job {job_id}: {e}")
            return {"error": str(e), "log_stream_name": log_stream_name}

    def _identify_error_patterns_in_logs(self, events: List[Dict]) -> List[Dict]:
        """
        Identify common error patterns in log events.
        """
        error_patterns = []

        # Common error patterns to look for
        patterns = [
            {
                "name": "OutOfMemory",
                "keywords": ["out of memory", "oom", "memory error", "kill", "137"],
            },
            {
                "name": "FileNotFound",
                "keywords": ["no such file", "file not found", "does not exist"],
            },
            {
                "name": "PermissionDenied",
                "keywords": ["permission denied", "access denied", "forbidden"],
            },
            {
                "name": "NetworkError",
                "keywords": ["connection refused", "timeout", "network", "dns"],
            },
            {
                "name": "PythonError",
                "keywords": ["traceback", "error:", "exception:", "failed"],
            },
            {
                "name": "ContainerError",
                "keywords": ["container", "docker", "pull", "image"],
            },
            {"name": "S3Error", "keywords": ["s3", "bucket", "aws", "boto"]},
        ]

        for event in events:
            message = event.get("message", "").lower()
            timestamp = event.get("timestamp")

            for pattern in patterns:
                if any(keyword in message for keyword in pattern["keywords"]):
                    error_patterns.append(
                        {
                            "pattern": pattern["name"],
                            "message": event.get("message", ""),
                            "timestamp": timestamp,
                            "matched_keywords": [
                                kw for kw in pattern["keywords"] if kw in message
                            ],
                        }
                    )

        return error_patterns

    def _summarize_logs(self, events: List[Dict]) -> Dict:
        """
        Create a summary of log events for quick analysis.
        """
        if not events:
            return {"total_events": 0}

        # Extract key statistics
        messages = [event.get("message", "") for event in events]
        error_count = sum(
            1
            for msg in messages
            if any(word in msg.lower() for word in ["error", "failed", "exception"])
        )
        warning_count = sum(1 for msg in messages if "warning" in msg.lower())

        return {
            "total_events": len(events),
            "error_count": error_count,
            "warning_count": warning_count,
            "first_event_time": events[0].get("timestamp") if events else None,
            "last_event_time": events[-1].get("timestamp") if events else None,
            "sample_messages": {
                "first": events[0].get("message", "") if events else "",
                "last": events[-1].get("message", "") if events else "",
                "errors": [msg for msg in messages if "error" in msg.lower()][
                    :3
                ],  # First 3 errors
            },
        }

    def _analyze_job_failure(self, failure_context: Dict) -> Dict:
        """
        Analyze failure context to determine likely causes.
        """
        analysis = {"likely_causes": [], "recommendations": [], "severity": "unknown"}

        exit_code = failure_context.get("exit_code")
        exit_reason = failure_context.get("exit_reason", "").lower()
        logs = failure_context.get("logs", {})
        error_patterns = logs.get("error_patterns", []) if logs else []

        # Analyze exit code
        if exit_code == 137:
            analysis["likely_causes"].append("Job killed (likely OOM or timeout)")
            analysis["recommendations"].append(
                "Increase memory allocation or optimize memory usage"
            )
            analysis["severity"] = "high"
        elif exit_code == 125:
            analysis["likely_causes"].append("Container startup failure")
            analysis["recommendations"].append(
                "Check container image and configuration"
            )
            analysis["severity"] = "high"
        elif exit_code and exit_code != 0:
            analysis["likely_causes"].append(
                f"Application error (exit code {exit_code})"
            )
            analysis["recommendations"].append(
                "Check application logs for specific errors"
            )
            analysis["severity"] = "medium"

        # Analyze exit reason
        if exit_reason:
            if "essential container exited" in exit_reason:
                analysis["likely_causes"].append("Essential container failed")
                analysis["recommendations"].append(
                    "Check container health and startup configuration"
                )
                if analysis["severity"] == "unknown":
                    analysis["severity"] = "high"
            elif "host ec2" in exit_reason and "terminated" in exit_reason:
                analysis["likely_causes"].append("EC2 instance terminated unexpectedly")
                analysis["recommendations"].append(
                    "Check spot instance interruption or capacity issues"
                )
                if analysis["severity"] == "unknown":
                    analysis["severity"] = "medium"
            elif "task stopped by user" in exit_reason:
                analysis["likely_causes"].append("Job manually stopped")
                analysis["recommendations"].append("Job was cancelled by user")
                if analysis["severity"] == "unknown":
                    analysis["severity"] = "low"
            elif "resourcesnotavailable" in exit_reason.replace(" ", ""):
                analysis["likely_causes"].append("Insufficient resources available")
                analysis["recommendations"].append(
                    "Retry job or use different compute environment"
                )
                if analysis["severity"] == "unknown":
                    analysis["severity"] = "medium"
            elif "timeout" in exit_reason:
                analysis["likely_causes"].append("Job execution timeout")
                analysis["recommendations"].append(
                    "Increase job timeout or optimize execution time"
                )
                if analysis["severity"] == "unknown":
                    analysis["severity"] = "medium"
            elif exit_reason and analysis["severity"] == "unknown":
                analysis["likely_causes"].append(f"AWS Batch reason: {exit_reason}")
                analysis["recommendations"].append("Check AWS Batch documentation")
                analysis["severity"] = "medium"

        # Analyze error patterns
        pattern_counts = {}
        for pattern in error_patterns:
            pattern_name = pattern["pattern"]
            pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1

        if pattern_counts:
            most_common = max(pattern_counts.items(), key=lambda x: x[1])
            analysis["likely_causes"].append(
                f"Frequent {most_common[0]} errors ({most_common[1]} occurrences)"
            )

            # Add specific recommendations based on patterns
            if "OutOfMemory" in pattern_counts:
                analysis["recommendations"].append("Increase job memory limits")
            if "FileNotFound" in pattern_counts:
                analysis["recommendations"].append(
                    "Check input file paths and S3 permissions"
                )
            if "NetworkError" in pattern_counts:
                analysis["recommendations"].append(
                    "Check network connectivity and VPC configuration"
                )

        # Analyze execution time
        started_at = failure_context.get("started_at")
        stopped_at = failure_context.get("stopped_at")
        if started_at and stopped_at:
            duration = (stopped_at - started_at) / 1000  # Convert to seconds
            if duration < 60:
                analysis["likely_causes"].append("Job failed quickly (< 1 minute)")
                analysis["recommendations"].append(
                    "Check job initialization and dependencies"
                )
            elif duration > 3600:  # > 1 hour
                analysis["likely_causes"].append("Long-running job failure")
                analysis["recommendations"].append(
                    "Consider breaking into smaller tasks or increasing timeout"
                )

        return analysis

    def start_job_monitoring(self):
        """Start the job monitoring thread."""
        if self.monitoring_enabled and hasattr(self, "job_monitor"):
            try:
                if not self.job_monitor.monitoring_active:
                    self.job_monitor.start_monitoring()
                    logger.info("Job monitoring started")
            except Exception as e:
                logger.error(f"Failed to start job monitoring: {e}")

    def stop_job_monitoring(self):
        """Stop the job monitoring thread."""
        if hasattr(self, "job_monitor") and self.job_monitor.monitoring_active:
            try:
                self.job_monitor.stop_monitoring()
                logger.info("Job monitoring stopped")
            except Exception as e:
                logger.error(f"Failed to stop job monitoring: {e}")

    def add_job_to_monitoring(self, job_id: str, job_name: str = None):
        """Add a job to the monitoring system."""
        if self.monitoring_enabled and hasattr(self, "job_monitor"):
            try:
                self.job_monitor.add_job(job_id, job_name)
                logger.debug(f"Added job {job_id} to monitoring")
            except Exception as e:
                logger.error(f"Failed to add job {job_id} to monitoring: {e}")

    def remove_job_from_monitoring(self, job_id: str):
        """Remove a job from the monitoring system."""
        if hasattr(self, "job_monitor"):
            try:
                self.job_monitor.remove_job(job_id)
                logger.debug(f"Removed job {job_id} from monitoring")
            except Exception as e:
                logger.error(f"Failed to remove job {job_id} from monitoring: {e}")

    def get_monitoring_context_for_job(self, job_id: str) -> Dict:
        """Get monitoring context for a specific job."""
        if hasattr(self, "job_monitor"):
            try:
                return self.job_monitor.get_job_failure_context(job_id)
            except Exception as e:
                logger.error(f"Failed to get monitoring context for job {job_id}: {e}")
        return {}

    def clear_job_monitoring_data(self, job_id: str):
        """Clear monitoring data for a specific job."""
        if hasattr(self, "job_monitor"):
            try:
                self.job_monitor.clear_job_data(job_id)
                logger.debug(f"Cleared monitoring data for job {job_id}")
            except Exception as e:
                logger.error(f"Failed to clear monitoring data for job {job_id}: {e}")


class BatchDebug:
    def get_efs_optimized_storage_settings(
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

    def prepare_efs_environment(workspace_id: str, unique_id: str):
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

    def get_batch_container_setup_commands() -> List[str]:
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

    @staticmethod
    def validate_batch_configuration(batch_executor) -> bool:
        """
        Validate AWS Batch configuration to ensure it's ready for execution.
        """
        try:
            logger.info("Validating AWS Batch configuration...")
            job_queue = batch_executor.get_job_queue_for_user()
            queues = batch_executor.batch_client.describe_job_queues(
                jobQueues=[job_queue]
            )
            if not queues.get("jobQueues"):
                logger.error(f"Job queue '{job_queue}' not found.")
                return False

            queue = queues["jobQueues"][0]
            if queue.get("state") != "ENABLED":
                logger.error(
                    f"Job queue '{job_queue}' is not enabled "
                    f"(state: {queue.get('state')})."
                )
                return False

            if queue.get("status") != "VALID":
                logger.error(
                    f"Job queue '{job_queue}' is not valid "
                    f"(status: {queue.get('status')})."
                )
                return False

            compute_envs = queue.get("computeEnvironmentOrder", [])
            if not compute_envs:
                logger.error(
                    f"No compute environments found for job queue '{job_queue}'."
                )
                return False

            for ce_order in compute_envs:
                ce_name = ce_order["computeEnvironment"]
                ce_details = batch_executor.batch_client.describe_compute_environments(
                    computeEnvironments=[ce_name]
                )
                if not ce_details.get("computeEnvironments"):
                    logger.error(f"Compute environment '{ce_name}' not found.")
                    return False

                ce_info = ce_details["computeEnvironments"][0]
                if ce_info.get("state") != "ENABLED":
                    logger.error(
                        f"Compute environment '{ce_name}' is not enabled "
                        f"(state: {ce_info.get('state')})."
                    )
                    return False
                if ce_info.get("status") not in ["VALID", "UPDATING"]:
                    logger.error(
                        f"Compute environment '{ce_name}' is not valid "
                        f"(status: {ce_info.get('status')})."
                    )
                    return False

            logger.info("AWS Batch configuration validation successful.")
            return True

        except Exception as e:
            logger.error(f"AWS Batch configuration validation failed: {e}")
            return False

    def test_ecr_image_pull(batch_executor) -> None:
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
                            "ECR Repository Policy check failed: " f"{policy_error}"
                        )

                else:
                    logger.warning("ECR Authentication: No authorization data received")

            except Exception as auth_error:
                logger.warning(f"ECR Authentication failed: {auth_error}")
                logger.warning("This indicates IAM permission issues for ECR access")

        except Exception as e:
            logger.debug(f"ECR image pull test failed: {e}")

    def check_batch_job_memory_usage(batch_executor, job_queue: str) -> None:
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

            logger.debug(
                f"Checking memory usage for {len(running_job_list)} running jobs:"
            )

            for job in running_job_list:
                job_id = job["jobId"]
                job_name = job.get("jobName", "Unknown")

                try:
                    # Get detailed job information
                    job_details = batch_executor.batch_client.describe_jobs(
                        jobs=[job_id]
                    )
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
                                "cloudwatch",
                                region_name=BATCH_CONFIG.AWS_DEFAULT_REGION,
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
                                    Dimensions=[
                                        {"Name": "ServiceName", "Value": job_name}
                                    ],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=300,  # 5-minute periods
                                    Statistics=["Average", "Maximum"],
                                )

                                datapoints = memory_metrics.get("Datapoints", [])
                                if datapoints:
                                    latest = max(
                                        datapoints, key=lambda x: x["Timestamp"]
                                    )
                                    avg_mem = latest.get("Average", 0)
                                    max_mem = latest.get("Maximum", 0)
                                    logger.debug(
                                        f"Mem Use: {avg_mem:.1f}% avg, "
                                        f"{max_mem:.1f}% max"
                                    )
                                else:
                                    logger.debug(
                                        "No memory metrics available "
                                        "(Container Insights may not be enabled)"
                                    )

                            except Exception as metrics_error:
                                logger.debug(
                                    "    Could not get memory metrics: "
                                    f"{metrics_error}"
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

    def debug_batch_environment(batch_executor) -> None:
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
            queues = batch_executor.batch_client.describe_job_queues(
                jobQueues=[job_queue]
            )
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
                                    "  CE {ce_name} may have issues: "
                                    f"{ce_state}/{ce_status}"
                                )
                    except Exception as ce_error:
                        logger.warning(
                            "  Could not get details for CE " f"{ce_name}: {ce_error}"
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
                        logger.warning(
                            f"Found {job_count} jobs stuck in STARTING state:"
                        )
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
                    for job in failed_jobs["jobList"][:3]:
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
                                f"  {job_name}: Could not get details - "
                                f"{detail_error}"
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
                            repo.get("createdAt")
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
                                        f"Image {image_tag}: "
                                        f"{image_size/1024/1024:.1f}MB, "
                                        f"pushed: {pushed_at}"
                                    )
                                else:
                                    logger.warning(
                                        f"Image tag '{image_tag}' not found "
                                        "in repository"
                                    )
                            except Exception as img_error:
                                logger.warning(
                                    "Could not get image details: " f"{img_error}"
                                )

                    except Exception as ecr_error:
                        logger.warning(f"ECR check failed: {ecr_error}")
                        # This might indicate permission issues

            except Exception as container_error:
                logger.warning(f"Container image check failed: {container_error}")

            # 5. Check CloudWatch metrics for compute environment instances
            logger.debug("Checking compute environment metrics...")
            try:
                cloudwatch = boto3.client(
                    "cloudwatch",
                    region_name=BATCH_CONFIG.AWS_DEFAULT_REGION,
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

                        # Check for common CloudWatch metrics
                        metrics_to_check = [
                            "AWS/Batch",  # Batch service metrics
                            "AWS/EC2",  # EC2 instance metrics
                        ]

                        for namespace in metrics_to_check:
                            try:
                                # List available metrics
                                metrics = cloudwatch.list_metrics(
                                    Namespace=namespace,
                                    Dimensions=[
                                        {"Name": "JobQueue", "Value": job_queue}
                                    ],
                                )

                                if metrics.get("Metrics"):
                                    logger.info(
                                        f"Found {len(metrics['Metrics'])} "
                                        "CloudWatch metrics for "
                                        f"{namespace}"
                                        f" at start_time={start_time}, "
                                        f"end_time={end_time}"
                                    )

                                    # Check specific useful metrics
                                    for metric in metrics["Metrics"][:3]:
                                        metric_name = metric["MetricName"]
                                        logger.debug(
                                            "  Available metric: " f"{metric_name}"
                                        )

                            except Exception as metric_error:
                                logger.debug(
                                    "Could not check "
                                    f"{namespace} metrics: {metric_error}"
                                )

                    except Exception as ce_metric_error:
                        logger.debug(
                            "Could not get metrics for CE "
                            f"{ce_name}: {ce_metric_error}"
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
                    logger.info(
                        f"Recent log streams in {log_group}: " f"{recent_streams}"
                    )

                    # Check most recent log stream for container issues
                    if log_streams.get("logStreams"):
                        latest_stream = log_streams["logStreams"][0]
                        stream_name = latest_stream["logStreamName"]
                        last_event = latest_stream.get("lastEventTime", 0)

                        if last_event:
                            last_event_time = datetime.fromtimestamp(last_event / 1000)
                            time_ago = datetime.now() - last_event_time
                            logger.info(
                                "Latest log stream: " f"{stream_name} ({time_ago} ago)"
                            )

                            # Get recent log events to check for issues
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
                                    for event in events[-3:]:
                                        message = event["message"]
                                        # Look for common startup issues
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
                                                "  Issue found: " f"{message[:100]}..."
                                            )
                                        else:
                                            logger.debug(f"  {message[:80]}...")
                            except Exception as events_error:
                                logger.debug(
                                    "Could not get log events: " f"{events_error}"
                                )

                except logs_client.exceptions.ResourceNotFoundException:
                    logger.warning(
                        f"Log group {log_group} not found - "
                        "no container logs available"
                    )
                except Exception as logs_error:
                    logger.debug(f"Could not check log streams: {logs_error}")

            except Exception as log_check_error:
                logger.debug(f"Container log check failed: {log_check_error}")

            # 7. Check memory usage for running jobs
            logger.debug("Checking memory usage for running jobs...")

            logger.info("=== END BATCH ENVIRONMENT DEBUG ===")

        except Exception as e:
            logger.error(f"Batch environment debug failed: {e}")
            # Don't let debug failure break the main execution
