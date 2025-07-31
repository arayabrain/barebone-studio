"""
Cloud utilities initialization.
"""
from studio.app.common.core.logger import AppLogger

logger = AppLogger.get_logger()


def initialize_cloud_services():
    """Initialize cloud services and test connectivity."""
    try:
        from studio.app.common.core.cloud.cloud_utils import initialize_cloud_utils

        logger.info("Initializing cloud services...")
        success = initialize_cloud_utils()

        if success:
            logger.info("Cloud services initialized successfully")
        else:
            logger.error("Cloud services initialization failed")

        return success

    except Exception as e:
        logger.error(f"Failed to initialize cloud services: {e}")
        return False
