from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

password_regex = r"^(?=.*\d)(?=.*[!#$%&()*+,-./@_|])(?=.*[a-zA-Z]).{6,255}$"


class UserRole(int, Enum):
    admin = 1
    data_manager = 10
    operator = 20
    guest_operator = 30


class User(BaseModel):
    id: int
    uid: str
    name: Optional[str]
    email: EmailStr
    organization_id: int
    role_id: int

    @property
    def is_admin(self) -> bool:
        return self.role_id == UserRole.admin

    @property
    def is_admin_data(self) -> bool:
        return self.is_admin or self.role_id == UserRole.data_manager

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(max_length=255, regex=password_regex)
    name: str
    role_id: int

    class Config:
        anystr_strip_whitespace = True


class UserUpdate(BaseModel):
    email: Optional[EmailStr]
    name: str
    role_id: int


class SelfUserUpdate(BaseModel):
    email: Optional[EmailStr]
    name: str


class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(max_length=255, regex=password_regex)

    class Config:
        anystr_strip_whitespace = True


class UserInfo(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
