import asyncio
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

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
