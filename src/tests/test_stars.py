class TestCreateStar:
    async def test_moderator_create_star_success(self, client, moderator_user):
        login_res = await client.post(
            "/login/",
            json={
                "email": moderator_user["email"],
                "password": moderator_user["password"],
            },
        )
        assert login_res.status_code == 200
        access_token = login_res.json()["access_token"]

        create_star_res = await client.post(
            "/movies/stars/",
            json={"name": "Brad Pittt"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert create_star_res.status_code == 201

        data = create_star_res.json()
        assert data["name"] == "Brad Pittt"

    async def test_moderator_create_duplicate_star(
        self, client, existing_star
    ):
        res = await client.post(
            "/movies/stars/",
            json={
                "name": existing_star["name"],
            },
            headers={
                "Authorization": f"Bearer {existing_star['access_token']}"
            },
        )
        assert res.status_code == 409
        assert res.json()["detail"] == "Star with this name already exists"


class TestUpdateStar:

    async def test_moderator_update_star_success(self, client, existing_star):
        update_star_res = await client.patch(
            f"/movies/stars/{existing_star['id']}/",
            json={
                "name": "some star",
            },
            headers={
                "Authorization": f"Bearer {existing_star['access_token']}"
            },
        )

        assert update_star_res.status_code == 200
        data = update_star_res.json()
        assert data["name"] == "some star"

    async def test_moderator_update_duplicate_star(
        self, client, existing_star
    ):
        res_create_genre = await client.post(
            "/movies/stars/",
            json={
                "name": "Will Smith",
            },
            headers={
                "Authorization": f"Bearer {existing_star['access_token']}"
            },
        )
        assert res_create_genre.status_code == 201

        res_update_star = await client.patch(
            f"/movies/stars/{existing_star['id']}/",
            json={
                "name": "Will Smith",
            },
            headers={
                "Authorization": f"Bearer {existing_star['access_token']}"
            },
        )
        assert res_update_star.status_code == 409

    async def test_moderator_update_not_found_star(
        self, client, existing_star
    ):
        res_update_star = await client.patch(
            f"/movies/stars/99999999/",
            json={
                "name": "some star",
            },
            headers={
                "Authorization": f"Bearer {existing_star['access_token']}"
            },
        )

        assert res_update_star.status_code == 404
        assert (
            res_update_star.json()["detail"]
            == "Star with this id does not exist"
        )


class TestDeleteStar:
    async def test_moderator_delete_star_success(self, client, existing_star):
        delete_star_res = await client.delete(
            f"/movies/stars/{existing_star['id']}/",
            headers={
                "Authorization": f"Bearer {existing_star['access_token']}"
            },
        )

        assert delete_star_res.status_code == 204

    async def test_moderator_delete_star_not_found_star(
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

        delete_star_res = await client.delete(
            f"/movies/stars/1/",
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert delete_star_res.status_code == 404
