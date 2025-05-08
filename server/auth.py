# server/auth.py

import os
from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users.db import BeanieUserDatabase

from models import User, UserCreate, UserUpdate, UserDB
from database import db
from fastapi import Depends
from fastapi_users.manager import BaseUserManager, UserManagerDependency
from fastapi_users import UUIDIDMixin
from typing import Optional


SECRET = os.getenv("SECRET")

# 1. Bearer transport (token passed via Authorization header)
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# 2. JWT Strategy
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

# 3. Authentication backend combining transport + strategy
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# 4. User DB adapter
user_db = BeanieUserDatabase(UserDB, db.get_collection("users"))

class UserManager(UUIDIDMixin, BaseUserManager[UserDB, str]):
    user_db_model = UserDB
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: UserDB, request=None):
        print(f"User {user.id} has registered.")

# Dependency to be injected by FastAPI
async def get_user_manager(user_db=Depends(lambda: user_db)):
    yield UserManager(user_db)

# 5. FastAPIUsers instance
fastapi_users = FastAPIUsers[User, str](get_user_manager, [auth_backend])


# 6. Routes
router = APIRouter()

router.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
router.include_router(
    fastapi_users.get_register_router(User, UserCreate), prefix="/auth", tags=["auth"]
)

router.include_router(
    fastapi_users.get_users_router(User, UserUpdate), prefix="/users", tags=["users"]
)
