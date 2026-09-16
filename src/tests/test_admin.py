from sqlalchemy import select

from database.models.accounts import UserModel
from conftest import test_AsyncPostgresqlSessionLocal


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
