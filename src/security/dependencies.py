"""FastAPI dependencies for authentication and role checks."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import get_settings
from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from exceptions.security import TokenExpiredError, InvalidTokenError
from security.token_manager import JWTAuthManager
from security.jwt_interfaces import JWTAuthManagerInterface

security_scheme = HTTPBearer()


async def get_jwt_token_manager(
    settings: BaseSettings = Depends(get_settings),
) -> JWTAuthManagerInterface:
    """
    Create the JWT manager configured with the application secret key.

    Args:
        settings (BaseSettings): Application settings (injected).

    Returns:
        JWTAuthManagerInterface: A manager that signs tokens with HS256.
    """

    return JWTAuthManager(
        secret_key_access=settings.jwt_secret_key, algorithm="HS256"
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_postgresql_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_token_manager),
):
    """
    Identify the user who sent the request.

    Reads the access token from the `Authorization: Bearer <token>` header,
    decodes it, and loads the user whose id is stored in the token's `sub`
    claim. Use it as a dependency on every endpoint that requires login.

    Args:
        credentials (HTTPAuthorizationCredentials): The Bearer credentials.
        db (AsyncSession): Database session (injected).
        jwt_manager (JWTAuthManagerInterface): Token manager (injected).

    Returns:
        UserModel: The authenticated user.

    Raises:
        HTTPException: 401 if the header is missing, the token is expired or
            invalid, or the user no longer exists.
    """

    try:
        payload = jwt_manager.decode_access_token(credentials.credentials)
    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

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
    """
    Allow only administrators.

    Args:
        db (AsyncSession): Database session (injected).
        current_user (UserModel): The authenticated user (injected).

    Returns:
        UserModel: The same user, if they are in the admin group.

    Raises:
        HTTPException: 401 if not authenticated, 403 if the user is not an administrator.
    """
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


async def require_moderator(
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Allow moderators and administrators.

    Administrators inherit moderator permissions, so both groups pass.

    Args:
        db (AsyncSession): Database session (injected).
        current_user (UserModel): The authenticated user (injected).

    Returns:
        UserModel: The same user, if they are a moderator or an administrator.

    Raises:
        HTTPException: 401 if not authenticated, 403 if the user has neither role.
    """

    group = await db.scalar(
        select(UserGroupModel).where(
            UserGroupModel.id == current_user.group_id
        )
    )
    if group.name not in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN):
        raise HTTPException(status_code=403, detail="You are not a moderator")
    return current_user
