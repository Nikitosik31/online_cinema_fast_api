import secrets
from datetime import datetime, timedelta

from conftest import test_AsyncPostgresqlSessionLocal
from sqlalchemy import select
from database.models.accounts import (
    ActivationTokenModel,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
)
from security import passwords


async def test_register_user_success(client):
    response = await client.post(
        "/register/", json={"email": "test@test.com", "password": "TestTest1!"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@test.com"
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data


async def test_register_user_with_existing_email(client):
    response = await client.post(
        "/register/",
        json={"email": "test@test1.com", "password": "TestTest1!"},
    )
    assert response.status_code == 201

    response = await client.post(
        "/register/",
        json={"email": "test@test1.com", "password": "TestTest1!"},
    )
    assert response.status_code == 409
    data = response.json()
    assert (
        data["detail"]
        == "A user with this email test@test1.com already exists."
    )


async def test_register_user_with_invalid_password(client):
    response = await client.post(
        "/register/", json={"email": "test@test1.com", "password": "testest!"}
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "password"]
    assert "uppercase letter" in data["detail"][0]["msg"]


async def test_activate_user_success(client):
    response = await client.post(
        "/register/", json={"email": "test@test2.com", "password": "teStest1!"}
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    async with test_AsyncPostgresqlSessionLocal() as session:
        token_obj = await session.scalar(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == user_id
            )
        )
    res = await client.post(f"/activate/", json={"token": token_obj.token})

    async with test_AsyncPostgresqlSessionLocal() as ses:
        user_obj = await ses.scalar(
            select(UserModel).where(UserModel.id == user_id)
        )
    assert res.status_code == 200
    assert user_obj.is_active is True


async def test_activate_user_token_not_found(client):
    response = await client.post(
        "/activate/", json={"token": "ejwncjwnjwcnwjncjnejncweknwekneejc"}
    )
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"]
        == "Activation token ejwncjwnjwcnwjncjnejncweknwekneejc does not exist."
    )


async def test_activate_user_token_expired(client):
    password = "TesTtest!1"
    hashed_password = passwords.hash_password(password)

    async with test_AsyncPostgresqlSessionLocal() as session:
        group = await session.scalar(
            select(UserGroupModel).where(
                UserGroupModel.name == UserGroupEnum.USER
            )
        )

        user = UserModel(
            email="test@test3.com",
            hashed_password=hashed_password,
            group=group,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        activation_token = ActivationTokenModel(
            user_id=user.id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now() - timedelta(hours=1),
        )

        session.add(activation_token)
        await session.commit()

    response = await client.post(
        "/activate/", json={"token": activation_token.token}
    )
    assert response.status_code == 400
    data = response.json()
    assert (
        data["detail"] == f"Activation token {activation_token.token} expired."
    )


async def test_login_user_success(client, active_user):
    response = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_login_user_incorrect_password(client, active_user):
    response = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": "incorectPASs",
        },
    )
    assert response.status_code == 401


async def test_login_user_incorrect_email(client):
    response = await client.post(
        "/login/",
        json={
            "email": "IncorrectEmail@inc.com",
            "password": "LAlalcsdc",
        },
    )
    assert response.status_code == 401


async def test_user_login_not_activated(client):
    email = "Test@test.com"
    password = "TestTest1!"
    response = await client.post(
        "/register/", json={"email": email, "password": password}
    )
    assert response.status_code == 201

    res = await client.post(
        "/login/", json={"email": email, "password": password}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["detail"] == "Account not activated."
