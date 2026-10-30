"""Database engine, session factory and startup data seeding."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from config.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """
    Declarative base class for all ORM models.

    `AsyncAttrs` adds awaitable access to attributes that are not loaded yet
    (`await obj.awaitable_attrs.some_relation`).
    """

    pass


engine = create_async_engine(get_settings().postgres_url)

AsyncPostgresqlSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_postgresql_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session for one request.

    The session is opened before the endpoint runs and closed automatically
    afterwords. Changes are not saved unless the endpoint calls `commit()`.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """

    async with AsyncPostgresqlSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_postgresql_db_contextmanager() -> (
    AsyncGenerator[AsyncSession, None]
):
    """
    Provide a database session outside of FastAPI request handling.

    Same as `get_postgresql_db`, but usable with `async with` in code that
    has no dependency injection, for example Celery tasks.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    async with AsyncPostgresqlSessionLocal() as session:
        yield session


async def seed_db() -> None:
    """
    Insert the reference data the application needs to work.

    Creates the user groups (user, moderator, admin) and the movie
    certifications from their enums when they do not exist yet. It is safe
    to call on every startup: existing rows are skipped. Tables must already
    exist (apply the Alembic migrations first). Model imports are done
    inside the function to avoid circular imports.
    """
    from database.models.accounts import UserGroupEnum, UserGroupModel
    from database.models.movies import CertificationEnum, CertificationModel

    async with AsyncPostgresqlSessionLocal() as session:
        for group_enum in UserGroupEnum:
            existing_group = await session.scalar(
                select(UserGroupModel).where(UserGroupModel.name == group_enum)
            )
            if not existing_group:
                group = UserGroupModel(name=group_enum)
                session.add(group)
                await session.commit()

        for certification in CertificationEnum:
            existing_certification = await session.scalar(
                select(CertificationModel).where(
                    CertificationModel.name == certification
                )
            )
            if not existing_certification:
                sertificat = CertificationModel(name=certification)
                session.add(sertificat)
                await session.commit()
