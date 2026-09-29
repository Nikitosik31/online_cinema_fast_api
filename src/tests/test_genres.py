class TestCreateGenre:
    async def test_moderator_create_genre_success(
        self, client, moderator_user
    ):
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

    async def test_moderator_create_duplicate_genre(
        self, client, existing_genre
    ):
        res = await client.post(
            "/movies/genres/",
            json={
                "name": existing_genre["name"],
            },
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )
        assert res.status_code == 409
        assert res.json()["detail"] == "Genre with this name already exists"

    async def test_unauthenticated_user_cannot_create_genre(self, client):
        res = await client.post(
            "/movies/genres/",
            json={"name": "action"},
        )
        assert res.status_code == 401

    async def test_user_not_moderator_cannot_create_genre(
        self, client, active_user
    ):
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


class TestUpdateGenre:

    async def test_moderator_update_genre_success(
        self, client, existing_genre
    ):
        update_genre_res = await client.patch(
            f"/movies/genres/{existing_genre['id']}/",
            json={
                "name": "some genre",
            },
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )

        assert update_genre_res.status_code == 200
        data = update_genre_res.json()
        assert data["name"] == "some genre"

    async def test_moderator_update_duplicate_genre(
        self, client, existing_genre
    ):
        res_create_genre = await client.post(
            "/movies/genres/",
            json={
                "name": "Comedy",
            },
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )
        assert res_create_genre.status_code == 201

        res_update_genre = await client.patch(
            f"/movies/genres/{existing_genre['id']}/",
            json={
                "name": "Comedy",
            },
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )
        assert res_update_genre.status_code == 409

    async def test_moderator_update_not_found_genre(
        self, client, existing_genre
    ):
        res_update_genre = await client.patch(
            f"/movies/genres/99999999/",
            json={
                "name": "Comedy",
            },
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )

        assert res_update_genre.status_code == 404
        assert (
            res_update_genre.json()["detail"]
            == "Genre with this id does not exist"
        )

    async def test_unauthenticated_user_cannot_update_genre(self, client):
        res = await client.patch(
            "/movies/genres/1/",
            json={
                "name": "Comedy",
            },
        )
        assert res.status_code == 401

    async def test_user_not_moderator_cannot_update_genre(
        self, client, active_user
    ):
        login_res = await client.post(
            "/login/",
            json={
                "email": active_user["email"],
                "password": active_user["password"],
            },
        )
        assert login_res.status_code == 200
        access_token = login_res.json()["access_token"]

        update_genre_res = await client.patch(
            f"/movies/genres/1/",
            json={
                "name": "Comedy",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert update_genre_res.status_code == 403


class TestDeleteGenre:
    async def test_moderator_delete_genre_success(
        self, client, existing_genre
    ):
        delete_genre_res = await client.delete(
            f"/movies/genres/{existing_genre['id']}/",
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )

        assert delete_genre_res.status_code == 204

    async def test_moderator_delete_genre_not_found_genre(
        self, client, moderator_user
    ):
        login_res = await client.post(
            "/login/",
            json={
                "email": moderator_user["email"],
                "password": moderator_user["password"],
            },
        )
        login_data = login_res.json()

        delete_genre_res = await client.delete(
            f"/movies/genres/1/",
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert delete_genre_res.status_code == 404
