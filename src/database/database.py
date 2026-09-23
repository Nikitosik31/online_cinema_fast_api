from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from config.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


engine = create_async_engine(get_settings().postgres_url)

AsyncPostgresqlSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_postgresql_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncPostgresqlSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_postgresql_db_contextmanager() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncPostgresqlSessionLocal() as session:
        yield session


async def init_db() -> None:
    from database.models.accounts import UserGroupEnum, UserGroupModel

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncPostgresqlSessionLocal() as session:
        for group_enum in UserGroupEnum:
            existing_group = await session.scalar(select(UserGroupModel).where(UserGroupModel.name == group_enum))
            if not existing_group:
                group = UserGroupModel(name=group_enum)
                session.add(group)
                await session.commit()
