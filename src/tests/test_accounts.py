import secrets
from datetime import datetime, timedelta

from conftest import test_AsyncPostgresqlSessionLocal
from sqlalchemy import select
from database.models.accounts import (
    ActivationTokenModel,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    RefreshTokenModel,
    PasswordResetTokenModel,
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


async def test_user_activation_token_resend(client):
    register_res = await client.post(
        "/register/", json={"email": "test@test.com", "password": "Testtest1!"}
    )
    assert register_res.status_code == 201

    async with test_AsyncPostgresqlSessionLocal() as session:
        token_obj = await session.scalar(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == register_res.json()["id"]
            )
        )

    activation_resend_res = await client.post(
        "/activate/resend/", json={"email": "test@test.com"}
    )

    assert activation_resend_res.status_code == 200
    assert (
        activation_resend_res.json()["message"] == "Activation token resent."
    )

    async with test_AsyncPostgresqlSessionLocal() as session:
        new_token = await session.scalar(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == register_res.json()["id"]
            )
        )

    assert new_token.token != token_obj.token
    assert new_token.token


async def test_user_activation_token_resend_email_not_found(client):
    activation_resend_res = await client.post(
        "/activate/resend/", json={"email": "test@test.com"}
    )
    assert activation_resend_res.status_code == 200
    assert (
        activation_resend_res.json()["message"] == "Activation token resent."
    )


async def test_user_activation_token_resend_user_already_activated(
    client, active_user
):
    resend_res = await client.post(
        "/activate/resend/", json={"email": active_user["email"]}
    )
    assert resend_res.status_code == 200
    assert resend_res.json()["message"] == "Activation token resent."


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


async def test_user_logout_success(client, active_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert login_res.status_code == 200
    data_login = login_res.json()
    assert "access_token" in data_login
    assert "refresh_token" in data_login

    logout_res = await client.post(
        "/logout/",
        json={"refresh_token": data_login["refresh_token"]},
    )
    assert logout_res.status_code == 200
    refresh_token = data_login["refresh_token"]
    async with test_AsyncPostgresqlSessionLocal() as session:
        refresh_token_obj = await session.scalar(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token == refresh_token
            )
        )
    assert refresh_token_obj is None


async def test_user_logout_not_found(client, active_user):
    response = await client.post(
        "/logout/", json={"refresh_token": "cihnfdhncdihjncdijsncsdjsdkjjcm"}
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Refresh token does not exist."


async def test_user_refresh_token_success(client, active_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    refresh_res = await client.post(
        "/refresh/", json={"refresh_token": data["refresh_token"]}
    )
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data


async def test_user_refresh_token_not_found(client, active_user):
    response = await client.post(
        "/refresh/",
        json={
            "refresh_token": "cihnfdhncdijsncsdjwedjnwesdkjjcm",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Refresh token does not exist."


async def test_user_refresh_token_expired(client, active_user):
    async with test_AsyncPostgresqlSessionLocal() as session:
        refresh_token = RefreshTokenModel(
            user_id=active_user["id"],
            token="dcshcsdscdsfdvjsdkjjcdskjdcsjncds",
            expires_at=datetime.now() - timedelta(days=1),
        )

        session.add(refresh_token)
        await session.commit()

    response = await client.post(
        "/refresh/", json={"refresh_token": refresh_token.token}
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Refresh token expired."


async def test_user_reset_password_success(client, active_user):
    new_password = "Test123Test!"
    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    change_password_res = await client.post(
        "/change_password/",
        json={
            "old_password": active_user["password"],
            "new_password": new_password,
        },
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert change_password_res.status_code == 200

    login_res_with_old_password = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert login_res_with_old_password.status_code != 200

    login_res_with_new_password = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": new_password,
        },
    )
    assert login_res_with_new_password.status_code == 200


async def test_user_change_password_old_password_not_found(
    client, active_user
):
    new_password = "Test123Test!"
    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )

    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    change_password_res = await client.post(
        "/change_password/",
        json={
            "old_password": "lcdsmjndcs1!D",
            "new_password": new_password,
        },
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert change_password_res.status_code == 400
    data = change_password_res.json()
    assert data["detail"] == "Old password is not correct."


async def test_user_password_reset_request_success(client, active_user):
    res = await client.post(
        "/password-reset/request/",
        json={
            "email": active_user["email"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert (
        data["message"]
        == "If this email is registered, a password reset link has been sent."
    )

    async with test_AsyncPostgresqlSessionLocal() as session:
        password_reset_token = await session.scalar(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.user_id == active_user["id"]
            )
        )

    assert password_reset_token


async def test_user_password_reset_request_email_not_found(
    client, active_user
):
    res = await client.post(
        "/password-reset/request/",
        json={
            "email": "not_found@email.com",
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert (
        data["message"]
        == "If this email is registered, a password reset link has been sent."
    )

    async with test_AsyncPostgresqlSessionLocal() as session:
        password_reset_token = await session.scalar(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.user_id == active_user["id"]
            )
        )

    assert not password_reset_token


async def test_user_password_reset_request_not_activated_user(client):
    email = "email@email.com"
    password = "Password1!"
    register_res = await client.post(
        "/register/",
        json={
            "email": email,
            "password": password,
        },
    )
    assert register_res.status_code == 201

    reset_res = await client.post(
        "/password-reset/request/",
        json={
            "email": email,
        },
    )

    assert reset_res.status_code == 200
    data = reset_res.json()
    assert (
        data["message"]
        == "If this email is registered, a password reset link has been sent."
    )

    async with test_AsyncPostgresqlSessionLocal() as session:
        user = await session.scalar(
            select(UserModel).where(UserModel.email == email)
        )

        reset_token = await session.scalar(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.user_id == user.id
            )
        )

    assert not reset_token


async def test_user_password_reset_confirm_success(client, active_user):
    new_password = "NewPassword1!"
    async with test_AsyncPostgresqlSessionLocal() as session:
        password_reset_token = PasswordResetTokenModel(
            user_id=active_user["id"],
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now() + timedelta(hours=2),
        )

        session.add(password_reset_token)
        await session.commit()

    res = await client.post(
        "/password-reset/confirm/",
        json={
            "token": password_reset_token.token,
            "new_password": new_password,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "Password has been reset successfully."
    async with test_AsyncPostgresqlSessionLocal() as session:
        token = await session.scalar(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.user_id == active_user["id"]
            )
        )
    assert not token
    res_login_old_password = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    res_login_new_password = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": new_password,
        },
    )

    assert res_login_new_password.status_code == 200
    assert res_login_old_password.status_code == 401


async def test_user_password_reset_confirm_token_not_found(
    client, active_user
):
    res = await client.post(
        "/password-reset/confirm/",
        json={
            "token": secrets.token_urlsafe(32),
            "new_password": "NewPassword1!",
        },
    )

    assert res.status_code == 404
    assert res.json()["detail"] == "Password reset token does not exist."


async def test_user_password_reset_confirm_token_expired(client, active_user):
    async with test_AsyncPostgresqlSessionLocal() as session:
        password_reset_token = PasswordResetTokenModel(
            user_id=active_user["id"],
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now() - timedelta(hours=2),
        )
        session.add(password_reset_token)
        await session.commit()

    res = await client.post(
        "/password-reset/confirm/",
        json={
            "token": password_reset_token.token,
            "new_password": "NewPassword1!",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Password reset token expired."
