from datetime import datetime
from typing import List, Optional

from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.sql.functions import current_timestamp
from sqlmodel import Column, Field, ForeignKey, Relationship, UniqueConstraint

from studio.app.common.models.base import Base, TimestampMixin


class WorkspacesShareUser(Base, table=True):
    __tablename__ = "workspaces_share_users"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="idx_workspace_id_user_id"),
    )

    workspace_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True), ForeignKey("workspaces.id"), nullable=False
        ),
    )
    user_id: int = Field(
        sa_column=Column(BIGINT(unsigned=True), ForeignKey("users.id"), nullable=False),
    )
    created_at: Optional[datetime] = Field(
        sa_column_kwargs={"server_default": current_timestamp()},
    )


class Workspace(Base, TimestampMixin, table=True):
    __tablename__ = "workspaces"

    name: str = Field(max_length=100, nullable=False)
    user_id: int = Field(
        sa_type=BIGINT(unsigned=True), foreign_key="users.id", nullable=False
    )
    deleted: bool = Field(default=False, nullable=False)
    input_data_usage: int = Field(
        default=0,
        sa_type=BIGINT(unsigned=True),
        nullable=False,
        description="data usage in bytes",
    )

    user: Optional["User"] = Relationship(back_populates="workspace")  # noqa: F821
    user_share: List["User"] = Relationship(  # noqa: F821
        back_populates="workspace_share", link_model=WorkspacesShareUser
    )
