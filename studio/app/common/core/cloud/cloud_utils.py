"""
Cloud utilities for user context and subscription management.
"""
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

import pymysql

from studio.app.common.core.auth.auth_dependencies import get_current_user

# from studio.app.common.core.cloud_batch.batch_config import BATCH_CONFIG
from studio.app.common.core.logger import AppLogger

logger = AppLogger.get_logger()


# Database connection configuration from environment
def _parse_mysql_server():
    """Parse MYSQL_SERVER environment variable to extract host and port."""
    mysql_server = os.environ.get("MYSQL_SERVER", "localhost:3306")
    if ":" in mysql_server:
        host, port_str = mysql_server.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            logger.warning(
                f"Invalid port in MYSQL_SERVER: {port_str}, using default 3306"
            )
            port = 3306
    else:
        host = mysql_server
        port = 3306
    return host, port


_db_host, _db_port = _parse_mysql_server()

DB_CONFIG = {
    "host": _db_host,
    "port": _db_port,
    "user": os.environ.get("MYSQL_USER", "studio_db_user"),
    "password": os.environ.get("MYSQL_PASSWORD", "studio_db_password"),
    "database": os.environ.get("MYSQL_DATABASE", "studio"),
    "charset": "utf8mb4",
    "connect_timeout": 10,
    "read_timeout": 30,
    "write_timeout": 30,
}


@contextmanager
def get_db_connection():
    """Get database connection with proper error handling and cleanup."""
    connection = None
    try:
        logger.debug(f"Connecting to database: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        connection = pymysql.connect(**DB_CONFIG)
        yield connection
    except pymysql.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        raise
    finally:
        if connection:
            connection.close()


def _get_fallback_users(cursor) -> list:
    """
    Get fallback user list (admin user) when subscription tables don't exist.
    """
    try:
        # Get admin user (ID 1) as fallback
        query = """
        SELECT
            id,
            name,
            email,
            'Free' as plan_name,
            0 as plan_price,
            'active' as status,
            created_at,
            'free' as tier
        FROM users
        WHERE id = 1 AND active = 1
        """

        cursor.execute(query)
        result = cursor.fetchone()

        if result:
            logger.info("Using admin user as fallback for subscription monitoring")
            return [result]
        else:
            logger.warning("Admin user (ID 1) not found")
            return []

    except Exception as e:
        logger.error(f"Failed to get fallback users: {e}")
        return []


def _get_fallback_storage_quota(user_id: int) -> Dict[str, Any]:
    """
    Get fallback storage quota when storage usage table doesn't exist.
    Tries to determine quota based on user's subscription tier.
    """
    try:
        # Try to get user's subscription tier to determine appropriate quota
        user_context = get_current_user_context()
        if user_context and user_context.get("id") == user_id:
            tier = user_context.get("subscription_tier", "free")
            plan_name = user_context.get("subscription_plan_name", "Free")

            # Set quotas based on subscription tier
            if tier == "paid":
                default_quota_bytes = 100 * 1024 * 1024 * 1024  # 100GB for paid tier
                logger.info(
                    f"Using paid tier quota for user {user_id} ({plan_name}): 100GB"
                )
            else:
                default_quota_bytes = 5 * 1024 * 1024 * 1024  # 5GB for free tier
                logger.info(
                    f"Using free tier quota for user {user_id} ({plan_name}): 5GB"
                )
        else:
            # Fallback to free tier if we can't determine subscription
            default_quota_bytes = 5 * 1024 * 1024 * 1024  # 5GB
            logger.warning(
                f"Could not determine subscription for user {user_id}, "
                "using free tier quota: 5GB"
            )

    except Exception as e:
        logger.warning(
            f"Error determining subscription quota for user {user_id}: {e}, "
            "using free tier"
        )
        default_quota_bytes = 5 * 1024 * 1024 * 1024  # 5GB fallback

    return {
        "user_id": user_id,
        "current_usage_bytes": 0,  # Unknown, will be calculated from S3
        "quota_limit_bytes": default_quota_bytes,
        "usage_percentage": 0.0,
        "last_updated": None,
    }


def get_current_user_context() -> Optional[Dict[str, Any]]:
    """
    Get current user context including subscription tier from database.
    Returns user info with subscription details or None if not found.
    """
    try:
        # Try to get current user from request context
        user_id = None
        try:
            # This will work in API request context
            current_user = get_current_user()
            if hasattr(current_user, "id"):
                user_id = current_user.id
            else:
                logger.debug("Current user object has no 'id' attribute")
        except Exception as e:
            # No request context available (e.g., background tasks, CLI)
            logger.debug(f"No request context for current user: {e}")

        # Fall back to admin user if no current user available
        if user_id is None:
            user_id = 1  # Admin user from main.tf startup script
            logger.debug("Using admin user (id=1) as fallback")

        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # Query user with subscription information
            query = """
            SELECT
                u.id,
                u.uid,
                u.name,
                u.email,
                u.active,
                u.attributes,
                COALESCE(sp.name, 'Free') as subscription_plan_name,
                COALESCE(sp.price, 0) as subscription_price,
                CASE
                    WHEN su.expiration IS NOT NULL
                    AND su.expiration > NOW() THEN 'active'
                    ELSE 'expired'
                END as subscription_status,
                CASE
                    WHEN sp.name = 'Premium' THEN 'paid'
                    ELSE 'free'
                END as subscription_tier
            FROM users u
            LEFT JOIN subscription_users su ON u.id = su.user_id
                AND su.expiration > NOW()
            LEFT JOIN subscription_plans sp ON su.plan_id = sp.id
            WHERE u.id = %s AND u.active = 1
            """

            cursor.execute(query, (user_id,))
            result = cursor.fetchone()

            if result:
                logger.info(
                    f"Retrieved user context: {result['name']} ({result['email']}) "
                    f"- Tier: {result['subscription_tier']}"
                )
                return result
            else:
                logger.warning(f"User {user_id} not found or inactive")
                return None

    except Exception as e:
        logger.error(f"Failed to get user context: {e}")
        return None


def get_user_subscription_details(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed subscription information for a specific user.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            query = """
            SELECT
                u.id as user_id,
                u.name,
                u.email,
                sp.id as plan_id,
                sp.name as plan_name,
                sp.price as plan_price,
                su.expiration,
                CASE
                    WHEN su.expiration > NOW() THEN 'active'
                    ELSE 'expired'
                END as status,
                su.created_at as subscription_start,
                su.updated_at as subscription_updated,
                uas.current_usage_bytes,
                uas.quota_limit_bytes,
                uas.last_updated as usage_last_updated
            FROM users u
            LEFT JOIN subscription_users su ON u.id = su.user_id
                AND su.expiration > NOW()
            LEFT JOIN subscription_plans sp ON su.plan_id = sp.id
            LEFT JOIN user_storage_usage uas ON u.id = uas.user_id
            WHERE u.id = %s AND u.active = 1
            """

            cursor.execute(query, (user_id,))
            result = cursor.fetchone()

            if result:
                logger.debug(f"Retrieved subscription details for user {user_id}")
                return result
            else:
                logger.warning(f"No subscription details found for user {user_id}")
                return None

    except Exception as e:
        logger.error(f"Failed to get subscription details for user {user_id}: {e}")
        return None


def get_all_active_subscriptions() -> list:
    """
    Get all active subscription users for monitoring and reporting.
    Falls back to admin user if subscription tables don't exist.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # First check if subscription tables exist
            cursor.execute("SHOW TABLES LIKE 'subscription_%'")
            subscription_tables = cursor.fetchall()

            if (
                len(subscription_tables) < 2
            ):  # Need both subscription_users and subscription_plan
                logger.warning(
                    "Subscription tables not found, falling back to admin user"
                )
                return _get_fallback_users(cursor)

            query = """
            SELECT
                u.id,
                u.name,
                u.email,
                sp.name as plan_name,
                sp.price as plan_price,
                CASE
                    WHEN su.expiration > NOW() THEN 'active'
                    ELSE 'expired'
                END as status,
                su.created_at,
                CASE
                    WHEN sp.name = 'Free' THEN 'free'
                    WHEN sp.name = 'Premium' THEN 'paid'
                    ELSE 'free'
                END as tier
            FROM users u
            JOIN subscription_users su ON u.id = su.user_id
            JOIN subscription_plans sp ON su.plan_id = sp.id
            WHERE u.active = 1 AND su.expiration > NOW()
            ORDER BY sp.price DESC, u.name
            """

            cursor.execute(query)
            results = cursor.fetchall()

            logger.info(f"Retrieved {len(results)} active subscriptions")
            return results

    except Exception as e:
        logger.warning(
            f"Failed to get active subscriptions: {e}, falling back to admin user"
        )
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                return _get_fallback_users(cursor)
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            return []


def get_user_storage_usage(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get storage usage information for a user.
    Falls back to default quota if storage table doesn't exist.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # Check if storage usage table exists
            cursor.execute("SHOW TABLES LIKE 'user_storage_usage'")
            table_exists = cursor.fetchone()

            if not table_exists:
                logger.warning(
                    "user_storage_usage table not found, using default quota"
                )
                return _get_fallback_storage_quota(user_id)

            query = """
            SELECT
                user_id,
                current_usage_bytes,
                quota_limit_bytes,
                ROUND((current_usage_bytes / quota_limit_bytes) * 100, 2)
                    as usage_percentage,
                last_updated
            FROM user_storage_usage
            WHERE user_id = %s
            """

            cursor.execute(query, (user_id,))
            result = cursor.fetchone()

            if result:
                logger.info(
                    f"Retrieved storage usage for user {user_id}: "
                    f"current_usage={result.get('current_usage_bytes')}, "
                    f"quota_limit={result.get('quota_limit_bytes')}, "
                    f"usage_percentage={result.get('usage_percentage')}%"
                )
                return result
            else:
                logger.warning(
                    f"No storage usage data found for user {user_id}, using defaults"
                )
                return _get_fallback_storage_quota(user_id)

    except Exception as e:
        logger.warning(
            f"Failed to get storage usage for user {user_id}: {e}, using defaults"
        )
        return _get_fallback_storage_quota(user_id)


def update_user_storage_usage(user_id: int, new_usage_bytes: int) -> bool:
    """
    Update storage usage for a user.
    Returns True if successful or if table doesn't exist (fallback scenario).
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if storage usage table exists
            cursor.execute("SHOW TABLES LIKE 'user_storage_usage'")
            table_exists = cursor.fetchone()

            if not table_exists:
                logger.warning(
                    "user_storage_usage table not found, skipping storage update"
                )
                return True  # Return True since we're in fallback mode

            query = """
            INSERT INTO user_storage_usage (user_id, current_usage_bytes)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                current_usage_bytes = VALUES(current_usage_bytes),
                last_updated = CURRENT_TIMESTAMP
            """

            cursor.execute(query, (user_id, new_usage_bytes))
            conn.commit()

            logger.info(
                f"Updated storage usage for user {user_id}: {new_usage_bytes} bytes"
            )
            return True

    except Exception as e:
        logger.warning(f"Failed to update storage usage for user {user_id}: {e}")
        return False


def test_database_connection() -> bool:
    """
    Test database connectivity and print connection details.
    """
    try:
        logger.info("Testing database connection...")
        logger.info(
            f"Database config: {DB_CONFIG['host']}:{DB_CONFIG['port']} "
            f"/ {DB_CONFIG['database']}"
        )

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION(), DATABASE(), USER()")
            result = cursor.fetchone()

            logger.info("Database connection successful!")
            logger.info(f"MySQL Version: {result[0]}")
            logger.info(f"Current Database: {result[1]}")
            logger.info(f"Current User: {result[2]}")

            # Test subscription tables exist
            cursor.execute("SHOW TABLES LIKE 'subscription_%'")
            tables = cursor.fetchall()
            logger.info(f"Subscription tables found: {[t[0] for t in tables]}")

            return True

    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def print_admin_user_details():
    """
    Print details of the admin user for debugging.
    """
    try:
        logger.info("=== ADMIN USER DETAILS ===")

        # Get user context
        user_context = get_current_user_context()
        if user_context:
            logger.info(f"User ID: {user_context['id']}")
            logger.info(f"Name: {user_context['name']}")
            logger.info(f"Email: {user_context['email']}")
            logger.info(f"UID: {user_context['uid']}")
            logger.info(f"Subscription Plan: {user_context['subscription_plan_name']}")
            logger.info(f"Subscription Tier: {user_context['subscription_tier']}")
            logger.info(f"Subscription Status: {user_context['subscription_status']}")
            logger.info(f"Plan Price: {user_context['subscription_price']} cents")
        else:
            logger.error("Failed to retrieve admin user context")

        # Get subscription details
        subscription_details = get_user_subscription_details(1)
        if subscription_details:
            logger.info(
                f"Storage Usage: {subscription_details['current_usage_bytes']} bytes"
            )
            logger.info(
                f"Storage Quota: {subscription_details['quota_limit_bytes']} bytes"
            )

        # Get all active subscriptions
        active_subs = get_all_active_subscriptions()
        logger.info(f"Total active subscriptions: {len(active_subs)}")

        logger.info("=== END ADMIN USER DETAILS ===")

    except Exception as e:
        logger.error(f"Failed to print admin user details: {e}")


# Test function to be called during initialization
def initialize_cloud_utils():
    """
    Initialize cloud utils and test connectivity.
    """
    logger.info("Initializing cloud utilities...")

    # Test database connection
    if test_database_connection():
        logger.info("Database connection test passed")

        # Print admin user details
        print_admin_user_details()

        logger.info("Cloud utilities initialized successfully")
        return True
    else:
        logger.error("Cloud utilities initialization failed")
        return False


# if __name__ == "__main__":
#     # For testing purposes
#     initialize_cloud_utils()
