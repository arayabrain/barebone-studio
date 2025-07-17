#!/usr/bin/env python3
"""
Standalone AWS Batch debug script for manual troubleshooting.

NOTE: The main debug functionality has been integrated into _snakemake_execute_batch()
in snakemake_executor.py. This standalone script is kept for manual debugging only.

Usage: python debug_batch_jobs.py
"""

import os
from datetime import datetime

import boto3


def debug_batch_jobs():
    """Debug recent batch job failures with essential information only."""

    # Configuration from environment
    region = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
    job_queue = "subscr-optinist-free-queue"

    print("=== AWS Batch Manual Debug ===")
    print(f"Region: {region}")
    print(f"Job Queue: {job_queue}")
    print()

    # Initialize clients
    batch_client = boto3.client("batch", region_name=region)
    logs_client = boto3.client("logs", region_name=region)

    try:
        # 1. Quick job queue status
        print("1. Job Queue Status:")
        queues = batch_client.describe_job_queues(jobQueues=[job_queue])
        if queues.get("jobQueues"):
            queue = queues["jobQueues"][0]
            print(f"   State: {queue.get('state')}, Status: {queue.get('status')}")

            # Compute environments summary
            compute_envs = queue.get("computeEnvironmentOrder", [])
            print(f"   Compute Environments: {len(compute_envs)}")
            for ce in compute_envs:
                ce_name = ce["computeEnvironment"].split("/")[-1]  # Just the name
                print(f"     - {ce_name}")
        else:
            print("   ERROR: Job queue not found!")
            return
        print()

        # 2. Current job counts
        print("2. Current Job Status:")
        for status in ["RUNNABLE", "STARTING", "RUNNING", "FAILED"]:
            try:
                jobs = batch_client.list_jobs(
                    jobQueue=job_queue, jobStatus=status, maxResults=10
                )
                job_count = len(jobs.get("jobList", []))
                print(f"   {status}: {job_count} jobs")

                # Show stuck STARTING jobs
                if status == "STARTING" and job_count > 0:
                    for job in jobs["jobList"][:2]:
                        created_at = job.get("createdAt", 0)
                        if created_at:
                            created_time = datetime.fromtimestamp(created_at / 1000)
                            duration = datetime.now() - created_time
                            print(f"     {job['jobName']}: stuck for {duration}")
            except Exception as e:
                print(f"   {status}: Error checking - {e}")
        print()

        # 3. Recent failures (simplified)
        print("3. Recent Failed Jobs (last 3):")
        try:
            failed_jobs = batch_client.list_jobs(
                jobQueue=job_queue, jobStatus="FAILED", maxResults=3
            )

            for job in failed_jobs.get("jobList", []):
                job_id = job["jobId"]
                job_name = job["jobName"]

                # Get basic failure info
                job_details = batch_client.describe_jobs(jobs=[job_id])
                if job_details.get("jobs"):
                    job_info = job_details["jobs"][0]
                    status_reason = job_info.get("statusReason", "Unknown")
                    exit_code = job_info.get("container", {}).get("exitCode", "N/A")

                    print(f"   {job_name}: exit_code={exit_code}")
                    print(f"     Reason: {status_reason}")

                    # Quick log check for common issues
                    log_stream = job_info.get("container", {}).get("logStreamName")
                    if log_stream:
                        try:
                            log_events = logs_client.get_log_events(
                                logGroupName="/aws/batch/job",
                                logStreamName=log_stream,
                                limit=5,
                            )
                            # Look for key error patterns
                            for event in log_events.get("events", []):
                                message = event["message"].lower()
                                if any(
                                    keyword in message
                                    for keyword in [
                                        "error",
                                        "failed",
                                        "permission",
                                        "denied",
                                        "timeout",
                                        "oom",
                                    ]
                                ):
                                    print(f"     Issue: {event['message'][:80]}...")
                                    break
                        except Exception:
                            print("     (Could not access logs)")
                    print()
        except Exception as e:
            print(f"   Error checking failed jobs: {e}")

    except Exception as e:
        print(f"Error during debugging: {e}")


if __name__ == "__main__":
    debug_batch_jobs()
