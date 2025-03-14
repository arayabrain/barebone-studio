from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from fastapi import Query
from fastapi_pagination import LimitOffsetPage
from pydantic import BaseModel, Field

from studio.app.common.schemas.group import GroupWithUserCount
from studio.app.common.schemas.users import UserInfo

T = TypeVar("T")


class PageWithHeader(LimitOffsetPage[T], Generic[T]):
    header: Optional["ExpDbExperimentHeader"] = {}


class PublishFlags(str, Enum):
    on = "on"
    off = "off"


class PublishStatus(int, Enum):
    on = 1
    off = 0


class ExpDbExperimentFields(BaseModel):
    brain_area: Optional[str]
    imaging_depth: Optional[str]
    promoter: Optional[str]
    indicator: Optional[str]


class ExpDbExperimentHeader(BaseModel):
    graph_titles: List[str] = []


class ImageInfo(BaseModel):
    urls: List[str]
    thumb_urls: Optional[List[str]]
    params: Optional[dict]

    def __init__(self, urls, params=None, thumb_urls=None):
        if isinstance(urls, str):
            urls = [urls]
        super().__init__(urls=urls, thumb_urls=thumb_urls, params=params)
        if thumb_urls is None:
            self.thumb_urls = [url.replace(".png", ".thumb.png") for url in urls]


class ExpDbExperiment(BaseModel):
    id: int
    experiment_id: str
    fields: ExpDbExperimentFields = None
    attributes: Optional[dict] = {}
    view_attributes: Optional[dict] = {}
    cell_image_urls: List[ImageInfo] = None
    graph_urls: List[ImageInfo] = None
    pca_spatial_components: List[ImageInfo] = []
    pca_time_components: List[ImageInfo] = []
    share_type: int = Field(description="1: default(per users), 2: for organization")
    publish_status: int = Field(description="0: private, 1: public")
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ExpDbExperimentCreate(BaseModel):
    experiment_id: str
    organization_id: int
    attributes: Optional[dict] = {}
    view_attributes: Optional[dict] = {}


class ExpDbExperimentUpdate(BaseModel):
    experiment_id: Optional[str]
    organization_id: Optional[int]
    attributes: Optional[dict]
    view_attributes: Optional[dict]
    share_type: Optional[int]
    publish_status: Optional[int]
    updated_at: Optional[datetime]


class ExpDbExperimentsSearchOptions(BaseModel):
    experiment_id: Optional[str] = Field(
        Query(default="", description="partial match (experiments.experiment_id)")
    )
    brain_area: Optional[List[str]] = Field(Query(default=None))
    imaging_depth: Optional[List[str]] = Field(Query(default=None))
    promoter: Optional[List[str]] = Field(Query(default=None))
    indicator: Optional[List[str]] = Field(Query(default=None))


class ExpDbExperimentShareStatus(BaseModel):
    share_type: int = Field(
        description="0: no share, 1: default(per users), 2: for organization"
    )
    users: Optional[List[UserInfo]]
    groups: Optional[List[GroupWithUserCount]]


class ExpDbExperimentSharePostStatus(BaseModel):
    share_type: int = Field(
        description="0: no share, 1: default(per users), 2: for organization"
    )
    user_ids: Optional[List[int]]
    group_ids: Optional[List[int]]


class ExperimentShareType(int, Enum):
    no_share = 0
    per_user_or_group = 1
    for_org = 2
