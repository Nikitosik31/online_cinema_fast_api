import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from database.database import get_postgresql_db
from database.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    RefreshTokenModel,
    PasswordResetTokenModel,
)
from notifications.email import send_email
from schemas.accounts import (
    UserRegistrationResponseSchema,
    UserRegistrationRequestSchema,
    MessageResponseSchema,
    UserActivationRequestSchema,
    UserLoginResponseSchema,
    UserLoginRequestSchema,
    UserLogoutRequestSchema,
    TokenRefreshResponseSchema,
    TokenRefreshRequestSchema,
    UserChangePasswordRequestSchema,
    UserResetPasswordRequestSchema,
    UserPasswordResetConfirmRequestSchema,
    UserActivationResendRequestSchema,
)
from security import passwords
from security.dependencies import get_current_user
from security.jwt_token import create_access_token

router = APIRouter()


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserRegistrationRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    smtm = select(UserModel).where(UserModel.email == user_data.email)
    existing_user = await db.scalar(smtm)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists.",
        )

    user_group = await db.scalar(
        select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
    )
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

    await send_email(
        to=user.email,
        subject="Activation link",
        body=f"Click the link to activate your account: "
        f"http://localhost:8000/activate/?token="
        f"{activation_token.token}",
    )

    return UserRegistrationResponseSchema(
        id=user.id,
        email=user.email,
    )


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def activate_user(
    activation_data: UserActivationRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_token = await db.scalar(
        select(ActivationTokenModel).where(
            ActivationTokenModel.token == activation_data.token
        )
    )
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activation token {activation_data.token} does not exist.",
        )

    if db_token.expires_at < datetime.datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Activation token {activation_data.token} expired.",
        )

    db_user = await db.scalar(
        select(UserModel).where(UserModel.id == db_token.user_id)
    )
    db_user.is_active = True

    await db.delete(db_token)
    await db.commit()
    return MessageResponseSchema(
        message="Account activated successfully.",
    )


@router.post(
    "/activate/resend/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def activate_resend_user(
    activation_data: UserActivationResendRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    smtm = select(UserModel).where(UserModel.email == activation_data.email)
    existing_user = await db.scalar(smtm)
    if not existing_user or existing_user.is_active:
        return MessageResponseSchema(
            message="Activation token resent.",
        )

    token = await db.scalar(
        select(ActivationTokenModel).where(
            ActivationTokenModel.user_id == existing_user.id
        )
    )
    if token:
        await db.delete(token)
        await db.commit()

    new_token = ActivationTokenModel(
        user_id=existing_user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.datetime.now() + datetime.timedelta(days=1),
    )
    db.add(new_token)
    await db.commit()

    await send_email(
        to=existing_user.email,
        subject="Activation link",
        body=f"Click the link to activate your account: "
        f"http://localhost:8000/activate/?token="
        f"{new_token.token}",
    )

    return MessageResponseSchema(message="Activation token resent.")


@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def user_login(
    user_data: UserLoginRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_user = await db.scalar(
        select(UserModel).where(UserModel.email == user_data.email)
    )
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not passwords.verify_password(
        user_data.password, db_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not activated.",
        )

    access_token = create_access_token({"sub": str(db_user.id)})

    refresh_token_str = secrets.token_urlsafe(32)

    refresh_token = RefreshTokenModel(
        user_id=db_user.id,
        token=refresh_token_str,
        expires_at=datetime.datetime.now() + datetime.timedelta(days=7),
    )

    db.add(refresh_token)
    await db.commit()

    return UserLoginResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token_str,
    )


@router.post(
    "/logout/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def logout_user(
    user_data: UserLogoutRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_refresh_token = await db.scalar(
        select(RefreshTokenModel).where(
            RefreshTokenModel.token == user_data.refresh_token
        )
    )
    if not db_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Refresh token does not exist.",
        )

    await db.delete(db_refresh_token)
    await db.commit()
    return MessageResponseSchema(
        message="Successfully logged out.",
    )


@router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def refresh_token(
    user_data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_refresh_token = await db.scalar(
        select(RefreshTokenModel).where(
            RefreshTokenModel.token == user_data.refresh_token
        )
    )
    if not db_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token does not exist.",
        )

    if db_refresh_token.expires_at < datetime.datetime.now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired.",
        )

    db_user = select(
        UserModel,
    ).where(UserModel.id == db_refresh_token.user_id)

    user = await db.scalar(db_user)

    access_token = create_access_token({"sub": str(user.id)})

    return TokenRefreshResponseSchema(
        access_token=access_token,
    )


@router.post(
    "/change_password/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def change_password(
    user_data: UserChangePasswordRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    if not passwords.verify_password(
        user_data.old_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is not correct.",
        )

    new_hashed_password = passwords.hash_password(user_data.new_password)

    current_user.hashed_password = new_hashed_password
    await db.commit()
    return MessageResponseSchema(
        message="Successfully changed password.",
    )


@router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    user_data: UserResetPasswordRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    stmt = select(UserModel).where(UserModel.email == user_data.email)
    user = await db.scalar(stmt)
    if not user or not user.is_active:
        return MessageResponseSchema(
            message="If this email is registered, a password reset link has been sent.",
        )

    reset_token = PasswordResetTokenModel(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.datetime.now() + datetime.timedelta(hours=2),
    )

    db.add(reset_token)
    await db.commit()

    await send_email(
        to=user.email,
        subject="Password reset",
        body=f"Click the link to reset your password: "
        f"http://localhost:8000/password-reset/confirm/?token="
        f"{reset_token.token}",
    )

    return MessageResponseSchema(
        message="If this email is registered, a password reset link has been sent.",
    )


@router.post(
    "/password-reset/confirm/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def confirm_reset_token(
    user_data: UserPasswordResetConfirmRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    stmt = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.token == user_data.token
    )
    reset_token = await db.scalar(stmt)

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password reset token does not exist.",
        )
    if reset_token.expires_at < datetime.datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token expired.",
        )

    user = await db.scalar(
        select(UserModel).where(UserModel.id == reset_token.user_id)
    )

    new_hashed_password = passwords.hash_password(user_data.new_password)
    user.hashed_password = new_hashed_password

    await db.delete(reset_token)
    await db.commit()
    return MessageResponseSchema(
        message="Password has been reset successfully.",
    )
