from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from studio.app.common.schemas.users import UserInfo


class Workspace(BaseModel):
    id: Optional[int] = None
    name: str
    user: Optional[UserInfo] = None
    shared_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    data_usage: Optional[int] = None
    canDelete: Optional[bool] = None

    class Config:
        from_attributes = True


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceUpdate(WorkspaceCreate):
    pass


class WorkspaceSharePostStatus(BaseModel):
    user_ids: Optional[List[int]]


class WorkspaceShareStatus(BaseModel):
    users: Optional[List[UserInfo]]
