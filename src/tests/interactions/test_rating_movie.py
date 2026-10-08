from sqlalchemy import select

from database.models.interactions import FavoriteMovie, MovieRating
from tests.conftest import test_AsyncPostgresqlSessionLocal


class TestSetRating:
    async def test_set_rating_first_time_returns_200(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieRating).where(
                    MovieRating.movie_id == movie["id"],
                    MovieRating.user_id == active_user_with_token["id"],
                )
            )
            movies = result.all()

        assert len(movies) == 1
        assert movies[0].rating == 5

    async def test_set_rating_again_updates_existing_rating(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 6},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )

        res = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 8},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["rating"] == 8
        assert data["movie_id"] == movie["id"]
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieRating).where(
                    MovieRating.movie_id == movie["id"],
                    MovieRating.user_id == active_user_with_token["id"],
                )
            )
            movies = result.all()
            assert len(movies) == 1
            assert movies[0].rating == 8

    async def test_set_rating_invalid_value_returns_422(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 11},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 422
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieRating).where(
                    MovieRating.movie_id == movie["id"],
                    MovieRating.user_id == active_user_with_token["id"],
                )
            )
            favorite_movie = result.all()

        assert len(favorite_movie) == 0

    async def test_set_rating_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.put(
            f"/movies/99999/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 404

    async def test_set_rating_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 5},
        )
        assert res.status_code == 401

    async def test_set_rating_does_not_change_other_users_rating(
        self, client, create_movie, active_user_with_token, moderator_user
    ):
        movie = await create_movie("Movie")
        res_1 = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res_1.status_code == 200
        res_2 = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 10},
            headers={
                "Authorization": f"Bearer {moderator_user["access_token"]}"
            },
        )
        assert res_2.status_code == 200

        assert res_1.json()["rating"] == 5
        assert res_2.json()["rating"] == 10
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieRating).where(
                    MovieRating.movie_id == movie["id"],
                )
            )
            movies = result.all()

        assert len(movies) == 2
