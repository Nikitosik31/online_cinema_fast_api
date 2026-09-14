from datetime import datetime

from enum import StrEnum
from typing import Optional

from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base

class UserGroupEnum(StrEnum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(StrEnum):
    MAN = "man"
    WOMAN = "woman"


class UserGroupModel(Base):
    __tablename__ = "user_groups"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[UserGroupEnum] = mapped_column(Enum(UserGroupEnum), unique=True)

    users: Mapped[list["UserModel"]] = relationship(back_populates="group")


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id"))

    group: Mapped[UserGroupModel] = relationship("UserGroupModel", back_populates="users")
    user_profile: Mapped["UserProfileModel"] = relationship("UserProfileModel", back_populates="user")
    activation_token: Mapped["ActivationTokenModel"] = relationship("ActivationTokenModel", back_populates="user")
    password_reset_token: Mapped["PasswordResetTokenModel"] = relationship("PasswordResetTokenModel", back_populates="user")
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship("RefreshTokenModel", back_populates="user")


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    first_name: Mapped[Optional[str]] = mapped_column()
    last_name: Mapped[Optional[str]] = mapped_column()
    avatar: Mapped[Optional[str]] = mapped_column()
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum))
    date_of_birth: Mapped[Optional[datetime]] = mapped_column()
    info: Mapped[Optional[str]] = mapped_column()

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="user_profile")


class ActivationTokenModel(Base):
    __tablename__ = "activation_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    token: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column()

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="activation_token")


class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    token: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column()

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="password_reset_token")


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column()

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="refresh_tokens")






