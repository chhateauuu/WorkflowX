# server/models.py

from beanie import Document
from fastapi_users.db import BeanieBaseUser
from fastapi_users.schemas import BaseUserCreate, BaseUserUpdate
from pydantic import EmailStr, Field
from typing import Optional


# Main user document (stored in MongoDB)
class User(BeanieBaseUser, Document):
    name: Optional[str] = Field(default=None)

# Schema for registering new users
class UserCreate(BaseUserCreate):
    name: Optional[str] = Field(default=None)

# Schema for updating users
class UserUpdate(BaseUserUpdate):
    name: Optional[str] = Field(default=None)

# Optional alias
UserDB = User
