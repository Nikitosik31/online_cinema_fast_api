async def test_moderator_create_genre_success(client, moderator_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]

    create_genre_res = await client.post(
        "/movies/genres/",
        json={"name": "action"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert create_genre_res.status_code == 201

    data = create_genre_res.json()
    assert data["name"] == "action"


async def test_moderator_create_duplicate_genre(client, existing_genre):
    res = await client.post(
        "/movies/genres/",
        json={
            "name": existing_genre["name"],
        },
        headers={"Authorization": f"Bearer {existing_genre['access_token']}"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Genre with this name already exists"


async def test_unauthenticated_user_cannot_create_genre(client):
    res = await client.post(
        "/movies/genres/",
        json={"name": "action"},
    )
    assert res.status_code == 401


async def test_user_not_moderator_cannot_create_genre(client, active_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]

    create_genre_res = await client.post(
        "/movies/genres/",
        json={"name": "action"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_genre_res.status_code == 403
    data = create_genre_res.json()
    assert data["detail"] == "You are not a moderator"
