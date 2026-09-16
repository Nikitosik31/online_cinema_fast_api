from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from security.jwt_token import decode_token

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_postgresql_db),
):
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload["sub"] = int(payload["sub"])

    db_user = select(UserModel).where(UserModel.id == payload["sub"])
    user = await db.scalar(db_user)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    group = await db.scalar(
        select(UserGroupModel).where(
            UserGroupModel.id == current_user.group_id
        )
    )
    if group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=403, detail="You are not an administrator"
        )
    return current_user
