import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum, ActivationTokenModel
from schemas.accounts import UserRegistrationResponseSchema, UserRegistrationRequestSchema, MessageResponseSchema, \
    UserActivationRequestSchema
from security import passwords

router = APIRouter()

@router.post("/register/", response_model=UserRegistrationResponseSchema, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegistrationRequestSchema, db: AsyncSession = Depends(get_postgresql_db)):
    smtm = select(UserModel).where(UserModel.email == user_data.email)
    existing_user = await db.scalar(smtm)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists."
        )

    user_group = await db.scalar(select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER))
    hashed_password = passwords.hash_password(user_data.password)


    user = UserModel(
        email=user_data.email,
        hashed_password=hashed_password,
        group=user_group,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)


    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now() + datetime.timedelta(hours=24)

    activation_token = ActivationTokenModel(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(activation_token)
    await db.commit()

    return UserRegistrationResponseSchema(
        id=user.id,
        email=user.email,
    )

@router.post("/activate/", response_model=MessageResponseSchema, status_code=status.HTTP_200_OK)
async def activate_user(activation_data: UserActivationRequestSchema, db: AsyncSession = Depends(get_postgresql_db)):
    db_token = await db.scalar(select(ActivationTokenModel).where(ActivationTokenModel.token == activation_data.token))
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activation token {activation_data.token} does not exist."
        )

    if db_token.expires_at < datetime.datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Activation token {activation_data.token} expired."
        )

    db_user = await db.scalar(select(UserModel).where(UserModel.id == db_token.user_id))
    db_user.is_active = True

    await db.delete(db_token)
    await db.commit()
    return MessageResponseSchema(
        message="Account activated successfully.",
    )

