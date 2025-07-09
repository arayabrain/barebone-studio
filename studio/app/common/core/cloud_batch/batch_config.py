from pydantic import BaseSettings, Field, root_validator

from studio.app.common.core.logger import AppLogger
from studio.app.dir_path import DIRPATH


class BatchConfig(BaseSettings):
    # Core AWS Batch settings
    USE_AWS_BATCH: bool = Field(default=False, env="USE_AWS_BATCH")
    AWS_BATCH_JOB_DEFINITION: str = Field(default="", env="AWS_BATCH_JOB_DEFINITION")
    AWS_BATCH_JOB_ROLE: str = Field(default="", env="AWS_BATCH_JOB_ROLE")
    AWS_DEFAULT_REGION: str = Field(default="ap-northeast-1", env="AWS_DEFAULT_REGION")
    AWS_BATCH_S3_BUCKET_NAME: str = Field(default="", env="AWS_BATCH_S3_BUCKET_NAME")
    AWS_DEFAULT_PROVIDER: str = Field(default="S3", env="AWS_DEFAULT_PROVIDER")

    # Additional Batch configuration
    # AWS_BATCH_COMPUTE_ENVIRONMENT: str = Field(
    #     default="subscr-optinist-compute-env", env="AWS_BATCH_COMPUTE_ENVIRONMENT"
    # )
    AWS_BATCH_FREE_QUEUE: str = Field(default="", env="AWS_BATCH_FREE_QUEUE")
    AWS_BATCH_PAID_QUEUE: str = Field(default="", env="AWS_BATCH_PAID_QUEUE")

    # ECR configuration
    AWS_ECR_REPOSITORY: str = Field(default="", env="AWS_ECR_REPOSITORY")

    # CloudWatch logs configuration
    AWS_BATCH_LOG_GROUP: str = Field(
        default="/aws/batch/job", env="AWS_BATCH_LOG_GROUP"
    )
    AWS_BATCH_LOG_STREAM_PREFIX: str = Field(
        default="subscr-optinist-for-cloud", env="AWS_BATCH_LOG_STREAM_PREFIX"
    )

    @root_validator
    def validate_aws_config(cls, values):
        if values.get("USE_AWS_BATCH"):
            logger = AppLogger.get_logger()
            required_fields = [
                "AWS_BATCH_S3_BUCKET_NAME",
                "AWS_BATCH_JOB_ROLE",
                "AWS_BATCH_JOB_DEFINITION",
            ]

            # Check for at least one job queue configuration
            queue_fields = ["AWS_BATCH_FREE_QUEUE", "AWS_BATCH_PAID_QUEUE"]
            has_queue = any(values.get(field) for field in queue_fields)

            missing_fields = [
                field for field in required_fields if not values.get(field)
            ]

            if missing_fields:
                logger.warning(
                    f"AWS Batch configuration incomplete. "
                    f"Missing: {', '.join(missing_fields)}. Disabling AWS Batch."
                )
                values["USE_AWS_BATCH"] = False
            elif not has_queue:
                logger.warning(
                    "AWS Batch configuration incomplete. "
                    "Missing job queue configuration "
                    "(AWS_BATCH_FREE_QUEUE or AWS_BATCH_PAID_QUEUE). "
                    "Disabling AWS Batch."
                )
                values["USE_AWS_BATCH"] = False
            else:
                logger.info("AWS Batch configuration validated successfully")
        return values

    class Config:
        env_file = f"{DIRPATH.CONFIG_DIR}/.env"
        env_file_encoding = "utf-8"


BATCH_CONFIG = BatchConfig()
