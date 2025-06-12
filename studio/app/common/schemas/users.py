from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field

password_regex = r"^[a-zA-Z0-9!#$%&()*+,-./@_|]{6,255}$"


class Organization(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserSearchOptions(BaseModel):
    email: Optional[str] = Field(Query(default=""))
    name: Optional[str] = Field(Query(default=""))


class UserRole(int, Enum):
    admin = 1
    operator = 20


class User(BaseModel):
    id: int
    uid: str
    name: Optional[str] = None
    email: EmailStr
    organization: Organization
    role_id: Optional[int] = None
    data_usage: Optional[int] = None

    @property
    def is_admin(self) -> bool:
        return self.role_id == UserRole.admin

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(max_length=255, pattern=password_regex)
    name: str
    role_id: int

    model_config = ConfigDict(str_strip_whitespace=True)


class UserUpdate(BaseModel):
    email: Optional[EmailStr]
    name: str
    role_id: int


class SelfUserUpdate(BaseModel):
    email: Optional[EmailStr]
    name: str


class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(max_length=255, pattern=password_regex)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserInfo(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
