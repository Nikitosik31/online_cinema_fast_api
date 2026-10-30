from sqlalchemy import select

from database.models.accounts import UserModel, UserGroupEnum, UserGroupModel
from tests.conftest import test_AsyncPostgresqlSessionLocal


async def test_admin_activate_user_success(client, admin_user):
    response = await client.post(
        "/register/", json={"email": "test@test.com", "password": "TestTest1!"}
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    login_res = await client.post(
        "/login/",
        json={
            "email": admin_user["email"],
            "password": admin_user["password"],
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data

    res = await client.patch(
        f"/admin/users/{user_id}/activate/",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert res.status_code == 200
    async with test_AsyncPostgresqlSessionLocal() as session:
        user = await session.scalar(
            select(UserModel).where(UserModel.email == "test@test.com")
        )

    assert user.is_active


async def test_admin_activate_user_not_found(client, admin_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": admin_user["email"],
            "password": admin_user["password"],
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data

    res = await client.patch(
        f"/admin/users/99999999/activate/",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert res.status_code == 404


async def test_not_admin_activate_user(client, active_user):
    response = await client.post(
        "/register/", json={"email": "test@test.com", "password": "TestTest1!"}
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

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

    res = await client.patch(
        f"/admin/users/{user_id}/activate/",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert res.status_code == 403


async def test_admin_change_user_group_success(
    client, admin_user, active_user
):
    login_res = await client.post(
        "/login/",
        json={
            "email": admin_user["email"],
            "password": admin_user["password"],
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()

    change_group_res = await client.patch(
        f"/admin/users/{active_user["id"]}/group/",
        json={"group": UserGroupEnum.ADMIN},
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert change_group_res.status_code == 200

    async with test_AsyncPostgresqlSessionLocal() as session:
        user = await session.scalar(
            select(UserModel).where(UserModel.id == active_user["id"])
        )

        group = await session.scalar(
            select(UserGroupModel).where(UserGroupModel.id == user.group_id)
        )

    assert group.name == UserGroupEnum.ADMIN


async def test_admin_change_user_group_user_not_found(client, admin_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": admin_user["email"],
            "password": admin_user["password"],
        },
    )
    assert login_res.status_code == 200

    response = await client.patch(
        "/admin/users/99999999/group/",
        json={"group": UserGroupEnum.ADMIN},
        headers={
            "Authorization": f"Bearer {login_res.json()['access_token']}"
        },
    )
    assert response.status_code == 404


async def test_not_admin_change_group_user(client, active_user):
    response = await client.post(
        "/register/", json={"email": "test@test.com", "password": "TestTest1!"}
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert login_res.status_code == 200

    change_group_res = await client.patch(
        f"/admin/users/{user_id}/group/",
        json={"group": UserGroupEnum.ADMIN},
        headers={
            "Authorization": f"Bearer {login_res.json()['access_token']}"
        },
    )

    assert change_group_res.status_code == 403
