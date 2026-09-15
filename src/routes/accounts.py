import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum, ActivationTokenModel
from schemas.accounts import UserRegistrationResponseSchema, UserRegistrationRequestSchema
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



