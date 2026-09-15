import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from config.config import Settings, BASE_DIR
from database.database import Base
from database.models.accounts import (
    UserGroupEnum,
    UserGroupModel,
    UserModel,
    ActivationTokenModel,
)
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import get_postgresql_db

test_settings = Settings(_env_file=BASE_DIR / ".env.test")


test_engine = create_async_engine(test_settings.postgres_url)

test_AsyncPostgresqlSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_AsyncPostgresqlSessionLocal() as session:
        for group_enum in UserGroupEnum:
            existing_group = await session.scalar(
                select(UserGroupModel).where(UserGroupModel.name == group_enum)
            )
            if not existing_group:
                group = UserGroupModel(name=group_enum)
                session.add(group)
                await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with test_AsyncPostgresqlSessionLocal() as session:
        yield session


app.dependency_overrides[get_postgresql_db] = override_get_db


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def active_user(client):
    email = "active_user_fixture@test.com"
    password = "Testtest1!"

    response = await client.post(
        "/register/", json={"email": email, "password": password}
    )
    user_id = response.json()["id"]

    async with test_AsyncPostgresqlSessionLocal() as session:
        token_obj = await session.scalar(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == user_id
            )
        )
        await client.post("/activate/", json={"token": token_obj.token})

    return {"email": email, "password": password, "id": user_id}


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    async with test_AsyncPostgresqlSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name != "user_groups":
                await session.execute(table.delete())
                await session.commit()
