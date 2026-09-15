from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
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
