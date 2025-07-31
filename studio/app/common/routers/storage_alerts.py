"""
Storage Alerts API Router.
Provides endpoints for checking and managing S3 storage alerts.
"""
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from studio.app.common.core.auth.auth_dependencies import (
    get_current_user,
    get_user_remote_bucket_name,
)
from studio.app.common.core.cloud.s3_storage_monitor import (
    S3StorageMonitor,
    monitor_storage_and_generate_alerts,
)
from studio.app.common.core.logger import AppLogger
from studio.app.common.db.database import get_db
from studio.app.common.schemas.users import User

router = APIRouter(prefix="/storage-alerts", tags=["storage-alerts"])
logger = AppLogger.get_logger()


@router.get("/me", response_model=Dict)
async def get_my_storage_alert(
    current_user: User = Depends(get_current_user),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    """
    Get storage alert information for the current user.

    Returns:
        Dict containing user's storage usage and alert information
    """
    try:
        if not remote_bucket_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No S3 bucket configured for user",
            )

        monitor = S3StorageMonitor(remote_bucket_name)
        alert = await monitor.check_user_storage_alerts(current_user.id)

        if alert:
            # Add user information
            alert.update(
                {
                    "user_name": current_user.name,
                    "user_email": current_user.email,
                    "message": monitor.get_alert_message(alert),
                }
            )
            return {"has_alert": True, "alert": alert}
        else:
            # No alert, but still return current usage info
            current_usage = await monitor.get_user_s3_storage_size(current_user.id)

            return {
                "has_alert": False,
                "current_usage_bytes": current_usage,
                "current_usage_formatted": monitor.format_bytes(current_usage),
                "alert": None,
            }

    except Exception as e:
        logger.error(f"Failed to get storage alert for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve storage alert information",
        )


@router.get("/usage", response_model=Dict)
async def get_my_storage_usage(
    current_user: User = Depends(get_current_user),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    """
    Get detailed storage usage information for the current user.

    Returns:
        Dict containing detailed storage usage statistics
    """
    try:
        if not remote_bucket_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No S3 bucket configured for user",
            )

        monitor = S3StorageMonitor(remote_bucket_name)

        # Get current S3 usage
        current_usage = await monitor.get_user_s3_storage_size(current_user.id)

        # Get quota information from database
        from studio.app.common.core.cloud.cloud_utils import get_user_storage_usage

        storage_info = get_user_storage_usage(current_user.id)

        if not storage_info:
            return {
                "usage_bytes": current_usage,
                "usage_formatted": monitor.format_bytes(current_usage),
                "quota_bytes": None,
                "quota_formatted": None,
                "usage_percentage": None,
                "alert_level": None,
            }

        quota_limit = storage_info["quota_limit_bytes"]
        usage_percentage = (current_usage / quota_limit * 100) if quota_limit > 0 else 0
        alert_level = monitor.calculate_storage_alert_level(usage_percentage)

        return {
            "usage_bytes": current_usage,
            "usage_formatted": monitor.format_bytes(current_usage),
            "quota_bytes": quota_limit,
            "quota_formatted": monitor.format_bytes(quota_limit),
            "usage_percentage": round(usage_percentage, 2),
            "alert_level": alert_level,
            "thresholds": {
                "critical": monitor.CRITICAL_THRESHOLD,
                "danger": monitor.DANGER_THRESHOLD,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get storage usage for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve storage usage information",
        )


@router.get("/all", response_model=List[Dict])
async def get_all_storage_alerts(
    current_user: User = Depends(get_current_user),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
    db: Session = Depends(get_db),
):
    """
    Get storage alerts for all users (admin only).

    Returns:
        List of storage alert dictionaries
    """
    try:
        # Check if user is admin (you may need to adjust this based on your auth system)
        if not hasattr(current_user, "is_admin") or not current_user.is_admin:
            # Alternative check - you can adapt this based on your user model
            if current_user.id != 1:  # Assuming user ID 1 is admin
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required",
                )

        if not remote_bucket_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No S3 bucket configured",
            )

        alerts = await monitor_storage_and_generate_alerts(remote_bucket_name)

        # Add formatted messages to alerts
        if alerts:
            monitor = S3StorageMonitor(remote_bucket_name)
            for alert in alerts:
                alert["message"] = monitor.get_alert_message(alert)

        return alerts

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get all storage alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve storage alerts",
        )


@router.post("/refresh", response_model=Dict)
async def refresh_storage_usage(
    current_user: User = Depends(get_current_user),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    """
    Refresh storage usage calculation for the current user.

    Returns:
        Dict with updated storage information
    """
    try:
        if not remote_bucket_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No S3 bucket configured for user",
            )

        monitor = S3StorageMonitor(remote_bucket_name)

        # Recalculate current usage
        current_usage = await monitor.get_user_s3_storage_size(current_user.id)

        # Update database
        from studio.app.common.core.cloud.cloud_utils import update_user_storage_usage

        success = update_user_storage_usage(current_user.id, current_usage)

        if not success:
            logger.warning(
                f"Failed to update storage usage in database for user {current_user.id}"
            )

        return {
            "success": True,
            "updated_usage_bytes": current_usage,
            "updated_usage_formatted": monitor.format_bytes(current_usage),
            "database_updated": success,
        }

    except Exception as e:
        logger.error(f"Failed to refresh storage usage for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh storage usage",
        )
