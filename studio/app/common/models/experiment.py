from sqlalchemy.dialects.mysql import BIGINT
from sqlmodel import Column, Field, ForeignKey, String

from studio.app.common.models.base import Base, TimestampMixin


class ExperimentRecord(Base, TimestampMixin, table=True):
    __tablename__ = "experiment_records"

    workspace_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True), ForeignKey("workspaces.id"), nullable=False
        ),
    )
    uid: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    data_usage: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True), nullable=False, comment="data usage in bytes"
        ),
        default=0,
    )
