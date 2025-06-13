from datetime import datetime
from typing import Optional

from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.sql import text
from sqlmodel import Field, SQLModel


class Base(SQLModel):
    id: Optional[int] = Field(
        default=None, sa_type=BIGINT(unsigned=True), primary_key=True
    )


class TimestampMixin(SQLModel):
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={
            "server_default": text("CURRENT_TIMESTAMP"),
            "onupdate": text("CURRENT_TIMESTAMP"),
        },
    )
