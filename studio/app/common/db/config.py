from typing import Any, Optional

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings

from studio.app.dir_path import DIRPATH


class DatabaseConfig(BaseSettings):
    """Configuration for db"""

    MYSQL_ROOT_PASSWORD: str = Field(default="", env="MYSQL_ROOT_PASSWORD")
    MYSQL_SERVER: str = Field(default="db", env="MYSQL_SERVER")
    MYSQL_USER: Optional[str] = Field(default=None, env="MYSQL_USER")
    MYSQL_PASSWORD: Optional[str] = Field(default=None, env="MYSQL_PASSWORD")
    MYSQL_DATABASE: Optional[str] = Field(default=None, env="MYSQL_DATABASE")
    DATABASE_URL: Optional[str] = Field(default=None)
    POOL_SIZE: int = Field(default=100)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v

        data = info.data
        user = data.get("MYSQL_USER")
        password = data.get("MYSQL_PASSWORD")
        server = data.get("MYSQL_SERVER")
        database = data.get("MYSQL_DATABASE")

        if None in (user, password, server, database):
            return None

        return f"mysql+pymysql://{user}:{password}@{server}/{database}?charset=utf8mb4"

    class Config:
        env_file = f"{DIRPATH.CONFIG_DIR}/.env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"


DATABASE_CONFIG = DatabaseConfig()
