from unittest.mock import AsyncMock

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
from security import passwords

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


@pytest.fixture
async def admin_user(client):
    email = "Admin@admin.com"
    password = "Admin!1Admin"

    async with test_AsyncPostgresqlSessionLocal() as session:

        stmt = select(UserGroupModel).where(
            UserGroupModel.name == UserGroupEnum.ADMIN
        )
        admin = await session.scalar(stmt)
        admin_user = UserModel(
            email=email,
            hashed_password=passwords.hash_password(password),
            is_active=True,
            group=admin,
        )

        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

        return {
            "email": admin_user.email,
            "password": password,
            "id": admin_user.id,
        }


@pytest.fixture
async def moderator_user(client):
    email = "Moderator@admin.com"
    password = "Admin!1Admin"

    async with test_AsyncPostgresqlSessionLocal() as session:

        stmt = select(UserGroupModel).where(
            UserGroupModel.name == UserGroupEnum.MODERATOR
        )
        moderator = await session.scalar(stmt)
        moderator_user = UserModel(
            email=email,
            hashed_password=passwords.hash_password(password),
            is_active=True,
            group=moderator,
        )

        session.add(moderator_user)
        await session.commit()
        await session.refresh(moderator_user)

        return {
            "email": moderator_user.email,
            "password": password,
            "id": moderator_user.id,
        }


@pytest.fixture
async def existing_genre(client, moderator_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    create_res = await client.post(
        "/movies/genres/",
        json={"name": "Action"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    return {
        "id": create_res.json()["id"],
        "name": "Action",
        "access_token": access_token,
    }


@pytest.fixture
async def existing_star(client, moderator_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    create_res = await client.post(
        "/movies/stars/",
        json={"name": "Brad Pitt"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    return {
        "id": create_res.json()["id"],
        "name": "Brad Pitt",
        "access_token": access_token,
    }


@pytest.fixture(autouse=True)
def mock_send_user(monkeypatch):
    monkeypatch.setattr("routes.accounts.send_email", AsyncMock())
