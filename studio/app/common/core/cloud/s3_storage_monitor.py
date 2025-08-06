"""
S3 Storage Monitoring Utility for Cloud Alerts.
Monitors S3 storage usage and generates alerts when thresholds are exceeded.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import boto3

from studio.app.common.core.cloud.cloud_utils import (
    get_all_active_subscriptions,
    get_db_connection,
    get_user_storage_usage,
    update_user_storage_usage,
)
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.s3_storage_controller import S3StorageController

logger = AppLogger.get_logger()


class S3StorageMonitor:
    """
    Monitors S3 storage usage for users and generates alerts
    when thresholds are exceeded.
    """

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3_controller = S3StorageController(bucket_name)

        # Alert thresholds (percentage of quota)
        self.CRITICAL_THRESHOLD = 90  # 90%
        self.DANGER_THRESHOLD = 100  # 100%

        # Storage quotas by tier (in bytes)
        # These should match the values in your subscription plan features
        self.TIER_QUOTAS = {
            "free": 5 * 1024 * 1024 * 1024,  # 5GB
            "paid": 200 * 1024 * 1024 * 1024,  # 200GB
        }

    async def get_user_s3_storage_size(self, user_id: int) -> int:
        """
        Calculate total storage size for a user's S3 data.

        Args:
            user_id: The user ID to check storage for

        Returns:
            Total storage size in bytes
        """
        total_size = 0

        try:
            # Create sync S3 client for boto3 operations
            s3_client = boto3.client("s3")

            # Check both input and output directories for the user
            # Use the same path structure as S3StorageController
            prefixes = [
                f"app/studio_data/{S3StorageController.S3_INPUT_DIR}/{user_id}/",
                f"app/studio_data/{S3StorageController.S3_OUTPUT_DIR}/{user_id}/",
            ]
            logger.debug(
                f"Checking S3 storage for user {user_id} in bucket {self.bucket_name}"
            )
            logger.debug(f"Scanning prefixes: {prefixes}")

            for prefix in prefixes:
                try:
                    logger.debug(f"Scanning prefix: {prefix}")
                    # Use paginator to handle large number of objects
                    paginator = s3_client.get_paginator("list_objects_v2")
                    page_iterator = paginator.paginate(
                        Bucket=self.bucket_name, Prefix=prefix
                    )

                    prefix_size = 0
                    object_count = 0
                    for page in page_iterator:
                        if "Contents" in page:
                            for obj in page["Contents"]:
                                object_size = obj["Size"]
                                total_size += object_size
                                prefix_size += object_size
                                object_count += 1
                                # logger.debug(f"Found object: {obj['Key']} "
                                #               f"({object_size:,} bytes)")

                    logger.debug(
                        f"Prefix {prefix}: {object_count} objects, "
                        f"{prefix_size:,} bytes"
                    )

                except Exception as e:
                    logger.warning(f"Failed to get size for prefix {prefix}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to calculate S3 storage size for user {user_id}: {e}")
            return 0

        logger.info(
            f"Calculated S3 storage size for user {user_id}: {total_size:,} bytes"
        )
        return total_size

    def calculate_storage_alert_level(self, usage_percentage: float) -> Optional[str]:
        """
        Determine alert level based on usage percentage.

        Args:
            usage_percentage: Storage usage as percentage of quota

        Returns:
            Alert level string or None if no alert needed
        """
        if usage_percentage >= self.DANGER_THRESHOLD:
            return "danger"
        elif usage_percentage >= self.CRITICAL_THRESHOLD:
            return "critical"
        return None

    async def check_user_storage_alerts(self, user_id: int) -> Optional[Dict]:
        """
        Check storage usage for a specific user and return alert info if needed.

        Args:
            user_id: User ID to check

        Returns:
            Dict with alert information or None if no alert needed
        """
        try:
            # Get current S3 usage
            current_s3_usage = await self.get_user_s3_storage_size(user_id)

            # Update database with current usage
            update_success = update_user_storage_usage(user_id, current_s3_usage)
            if not update_success:
                logger.warning(f"Failed to update storage usage for user {user_id}")

            # Get user's storage quota from database or calculate based on subscription
            storage_info = get_user_storage_usage(user_id)

            # If no storage info exists, try to determine quota from user's subscription
            if not storage_info:
                logger.debug(
                    f"No storage usage record found for user {user_id}, "
                    "checking subscription"
                )
                from studio.app.common.core.cloud.cloud_utils import (
                    get_current_user_context,
                )

                user_context = get_current_user_context()
                if user_context:
                    tier = user_context.get("subscription_tier", "free")
                    quota_limit = self.TIER_QUOTAS.get(tier, self.TIER_QUOTAS["free"])
                    logger.info(
                        f"Using tier-based quota for user {user_id} ({tier}): "
                        f"{quota_limit} bytes"
                    )
                else:
                    logger.warning(
                        f"No storage or subscription information "
                        f"found for user {user_id}"
                    )
                    return None
            else:
                quota_limit = storage_info["quota_limit_bytes"]
                if quota_limit <= 0:
                    # Fallback to tier-based quota if database has invalid data
                    from studio.app.common.core.cloud.cloud_utils import (
                        get_current_user_context,
                    )

                    user_context = get_current_user_context()
                    if user_context:
                        tier = user_context.get("subscription_tier", "free")
                        quota_limit = self.TIER_QUOTAS.get(
                            tier, self.TIER_QUOTAS["free"]
                        )
                        logger.warning(
                            f"Invalid quota in database for user {user_id}, "
                            f"using tier-based quota: {quota_limit}"
                        )
                    else:
                        logger.warning(
                            f"Invalid quota limit for user {user_id}: {quota_limit}"
                        )
                        return None

            usage_percentage = (current_s3_usage / quota_limit) * 100
            alert_level = self.calculate_storage_alert_level(usage_percentage)

            if alert_level:
                return {
                    "user_id": user_id,
                    "alert_level": alert_level,
                    "usage_bytes": current_s3_usage,
                    "quota_bytes": quota_limit,
                    "usage_percentage": round(usage_percentage, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to check storage alerts for user {user_id}: {e}")

        return None

    async def check_all_users_storage_alerts(self) -> List[Dict]:
        """
        Check storage usage for all active users and return alerts.

        Returns:
            List of alert dictionaries
        """
        alerts = []

        try:
            # Get all active subscription users
            active_users = get_all_active_subscriptions()

            if not active_users:
                logger.info("No active users found for storage monitoring")
                return alerts

            logger.info(f"Checking storage alerts for {len(active_users)} active users")

            # Check each user's storage
            for user in active_users:
                user_id = user["id"]
                alert = await self.check_user_storage_alerts(user_id)

                if alert:
                    # Add user information to alert
                    alert.update(
                        {
                            "user_name": user["name"],
                            "user_email": user["email"],
                            "subscription_tier": user["tier"],
                            "plan_name": user.get("plan_name", "Unknown"),
                            "subscription_status": user.get("status", "unknown"),
                        }
                    )
                    alerts.append(alert)
                    logger.info(
                        f"Storage alert for user {user['name']} ({user['tier']}): "
                        f"{alert['alert_level']} at {alert['usage_percentage']}%"
                    )

        except Exception as e:
            logger.error(f"Failed to check storage alerts for all users: {e}")

        return alerts

    def format_bytes(self, bytes_size: int) -> str:
        """Format bytes into human readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

    def get_alert_message(self, alert: Dict) -> str:
        """
        Generate human-readable alert message.

        Args:
            alert: Alert dictionary

        Returns:
            Formatted alert message
        """
        usage_formatted = self.format_bytes(alert["usage_bytes"])
        quota_formatted = self.format_bytes(alert["quota_bytes"])
        percentage = alert["usage_percentage"]

        level_messages = {
            "critical": f"⚠️  Storage usage is at {percentage}% "
            f"({usage_formatted} of {quota_formatted}) - approaching limit",
            "danger": f"🚨 Storage quota exceeded at {percentage}% "
            f"({usage_formatted} of {quota_formatted}) - immediate action required",
        }

        return level_messages.get(alert["alert_level"], f"Storage usage: {percentage}%")

    def ensure_user_storage_record(self, user_id: int, tier: str) -> bool:
        """
        Ensure user has a storage usage record with appropriate quota for their tier.

        Args:
            user_id: User ID
            tier: User's subscription tier ('free' or 'paid')

        Returns:
            True if record exists or was created successfully
        """
        try:
            # Check if user already has storage record
            storage_info = get_user_storage_usage(user_id)
            if storage_info:
                return True

            # Create new storage record with tier-based quota
            quota_bytes = self.TIER_QUOTAS.get(tier, self.TIER_QUOTAS["free"])

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Check if user_storage_usage table exists
                cursor.execute("SHOW TABLES LIKE 'user_storage_usage'")
                if not cursor.fetchone():
                    logger.warning(
                        "user_storage_usage table does not exist, "
                        "cannot create storage record"
                    )
                    return False

                # Insert initial storage record
                query = """
                INSERT INTO user_storage_usage
                (user_id, current_usage_bytes, quota_limit_bytes)
                VALUES (%s, 0, %s)
                ON DUPLICATE KEY UPDATE
                    quota_limit_bytes = VALUES(quota_limit_bytes),
                    last_updated = CURRENT_TIMESTAMP
                """
                cursor.execute(query, (user_id, quota_bytes))
                conn.commit()

                logger.info(
                    f"Created storage record for user {user_id} with {tier} "
                    f"tier quota: {quota_bytes} bytes"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to ensure storage record for user {user_id}: {e}")
            return False


async def monitor_storage_and_generate_alerts(bucket_name: str) -> List[Dict]:
    """
    Convenience function to monitor storage and generate alerts.

    Args:
        bucket_name: S3 bucket name to monitor

    Returns:
        List of alert dictionaries
    """
    monitor = S3StorageMonitor(bucket_name)
    return await monitor.check_all_users_storage_alerts()


# Example usage for testing
if __name__ == "__main__":

    async def test_monitor():
        bucket_name = os.environ.get("S3_BUCKET_NAME", "test-bucket")
        alerts = await monitor_storage_and_generate_alerts(bucket_name)

        if alerts:
            print(f"Found {len(alerts)} storage alerts:")
            for alert in alerts:
                monitor = S3StorageMonitor(bucket_name)
                message = monitor.get_alert_message(alert)
                print(f"- {alert['user_name']} ({alert['user_email']}): {message}")
        else:
            print("No storage alerts found")

    asyncio.run(test_monitor())
