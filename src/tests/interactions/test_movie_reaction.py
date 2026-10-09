from sqlalchemy import select

from database.models.interactions import MovieReaction
from tests.conftest import test_AsyncPostgresqlSessionLocal, admin_user


class TestSetReaction:
    async def test_set_reaction_first_time_returns_200(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"]
                )
            )
            reactions = result.all()

        assert len(reactions) == 1
        assert reactions[0].reaction_type == "like"
        assert reactions[0].movie_id == movie["id"]

    async def test_set_reaction_again_changes_existing_reaction(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res_like = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res_like.status_code == 200

        res = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"]
                )
            )
            reactions = result.all()

        assert len(reactions) == 1
        assert reactions[0].reaction_type == "dislike"

    async def test_set_reaction_invalid_value_returns_422(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "love"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 422

    async def test_set_reaction_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.put(
            f"/movies/99999/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_set_reaction_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
        )
        assert res.status_code == 401

    async def test_set_reaction_does_not_change_other_users_reaction(
        self, client, create_movie, active_user_with_token, moderator_user
    ):
        movie = await create_movie("Movie")
        res_like = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_like.status_code == 200

        res_dislike = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res_dislike.status_code == 200

        async with test_AsyncPostgresqlSessionLocal() as db:
            user_reaction = await db.scalar(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"],
                    MovieReaction.user_id == active_user_with_token["id"],
                )
            )
            other_reaction = await db.scalar(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"],
                    MovieReaction.user_id == moderator_user["id"],
                )
            )

        assert user_reaction.reaction_type == "like"
        assert other_reaction.reaction_type == "dislike"


class TestRemoveReaction:
    async def test_remove_reaction_returns_204(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res_like = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_like.status_code == 200

        del_res = await client.delete(
            f"/movies/{movie["id"]}/reaction/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert del_res.status_code == 204

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"],
                )
            )
            reactions = result.all()

        assert len(reactions) == 0

    async def test_remove_reaction_not_reacted_returns_404(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res_del = await client.delete(
            f"/movies/{movie["id"]}/reaction/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_del.status_code == 404

    async def test_remove_reaction_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res_del = await client.delete(
            f"/movies/99999/reaction/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_del.status_code == 404

    async def test_remove_reaction_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res_del = await client.delete(
            f"/movies/{movie["id"]}/reaction/",
        )
        assert res_del.status_code == 401

    async def test_remove_reaction_does_not_touch_other_users(
        self, client, create_movie, active_user_with_token, moderator_user
    ):
        movie = await create_movie("Movie")
        res_like = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res_like.status_code == 200

        res_dislike = await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_dislike.status_code == 200

        del_res = await client.delete(
            f"/movies/{movie["id"]}/reaction/",
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert del_res.status_code == 204

        async with test_AsyncPostgresqlSessionLocal() as db:
            reaction = await db.scalar(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"],
                    MovieReaction.user_id == moderator_user["id"],
                )
            )
            other_reaction = await db.scalar(
                select(MovieReaction).where(
                    MovieReaction.movie_id == movie["id"],
                    MovieReaction.user_id == active_user_with_token["id"],
                )
            )

        assert reaction is None
        assert other_reaction is not None


class TestMovieReactionCounts:
    async def test_movie_details_without_reactions_has_zero_counts(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.get(
            f"/movies/{movie["id"]}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["likes_count"] == 0
        assert data["dislikes_count"] == 0

    async def test_movie_details_returns_likes_and_dislikes_counts(
        self,
        client,
        create_movie,
        active_user_with_token,
        moderator_user,
        admin_user,
    ):
        login_res = await client.post(
            "/login/",
            json={
                "email": admin_user["email"],
                "password": admin_user["password"],
            },
        )
        access_token = login_res.json()["access_token"]
        movie = await create_movie("Movie")

        await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        res = await client.get(
            f"/movies/{movie["id"]}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["likes_count"] == 2
        assert data["dislikes_count"] == 1

    async def test_movie_details_reaction_counts_ignore_other_movies(
        self, client, create_movie, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")

        await client.put(
            f"/movies/{movie1["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        await client.put(
            f"/movies/{movie2["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        res = await client.get(f"/movies/{movie1["id"]}/")
        assert res.status_code == 200
        data = res.json()
        assert data["likes_count"] == 1
        assert data["dislikes_count"] == 0

    async def test_movie_details_reaction_counts_update_when_reaction_changes(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        res = await client.get(f"/movies/{movie["id"]}/")
        assert res.status_code == 200
        data = res.json()
        assert data["likes_count"] == 1
        assert data["dislikes_count"] == 0

        await client.put(
            f"/movies/{movie["id"]}/reaction/",
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        res = await client.get(f"/movies/{movie["id"]}/")
        assert res.status_code == 200
        data = res.json()
        assert data["likes_count"] == 0
        assert data["dislikes_count"] == 1
