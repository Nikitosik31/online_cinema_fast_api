from sqlalchemy import select

from database.models.interactions import FavoriteMovie
from tests.conftest import test_AsyncPostgresqlSessionLocal


class TestAddFavorite:
    async def test_add_movie_to_favorites_returns_201(
        self, client, active_user_with_token, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie["id"]}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201

        async with test_AsyncPostgresqlSessionLocal() as db:
            favorite = await db.scalar(
                select(FavoriteMovie).where(
                    FavoriteMovie.movie_id == movie["id"],
                    FavoriteMovie.user_id == active_user_with_token["id"],
                )
            )
        assert favorite is not None

    async def test_add_movie_to_favorites_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.post(
            f"/movies/999999/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_add_movie_to_favorites_movie_already_exists_returns_409(
        self, client, active_user_with_token, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie["id"]}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201

        res_2 = await client.post(
            f"/movies/{movie['id']}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_2.status_code == 409

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(FavoriteMovie).where(
                    FavoriteMovie.movie_id == movie["id"],
                    FavoriteMovie.user_id == active_user_with_token["id"],
                )
            )
            favorites = result.all()
            assert len(favorites) == 1

    async def test_add_movie_to_favorites_unauthorized_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie["id"]}/favorite/",
        )
        assert res.status_code == 401


class TestRemoveFavorite:
    async def test_remove_movie_from_favorites_returns_204(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        post_res = await client.post(
            f"/movies/{movie["id"]}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert post_res.status_code == 201

        res = await client.delete(
            f"/movies/{movie["id"]}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            favorite = await db.scalar(
                select(FavoriteMovie).where(
                    FavoriteMovie.movie_id == movie["id"],
                    FavoriteMovie.user_id == active_user_with_token["id"],
                )
            )
            assert favorite is None

    async def test_remove_movie_from_favorites_movie_not_in_favorites_returns_404(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.delete(
            f"/movies/{movie["id"]}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_remove_movie_from_favorites_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.delete(
            "/movies/999999/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_remove_movie_from_favorites_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.delete(
            f"/movies/{movie["id"]}/favorite/",
        )
        assert res.status_code == 401

    async def test_remove_movie_from_favorites_does_not_touch_other_users(
        self, client, create_movie, moderator_user, active_user_with_token
    ):
        movie = await create_movie("Movie")
        async with test_AsyncPostgresqlSessionLocal() as db:
            mov1 = FavoriteMovie(
                user_id=moderator_user["id"],
                movie_id=movie["id"],
            )

            mov2 = FavoriteMovie(
                user_id=active_user_with_token["id"],
                movie_id=movie["id"],
            )
            db.add_all([mov1, mov2])
            await db.commit()

        res = await client.delete(
            f"/movies/{movie['id']}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(FavoriteMovie).where(
                    FavoriteMovie.movie_id == movie["id"],
                    FavoriteMovie.user_id == moderator_user["id"],
                )
            )
            favorite = result.all()
        assert len(favorite) == 1
