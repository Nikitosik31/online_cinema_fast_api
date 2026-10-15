from sqlalchemy import select

from database.models.interactions import FavoriteMovieModel, MovieRatingModel
from tests.conftest import test_AsyncPostgresqlSessionLocal, moderator_user


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
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                    MovieRatingModel.user_id == active_user_with_token["id"],
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
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                    MovieRatingModel.user_id == active_user_with_token["id"],
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
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                    MovieRatingModel.user_id == active_user_with_token["id"],
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
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                )
            )
            movies = result.all()

        assert len(movies) == 2


class TestRemoveRating:
    async def test_remove_rating_returns_204(
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

        del_res = await client.delete(
            f"/movies/{movie["id"]}/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert del_res.status_code == 204

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                    MovieRatingModel.user_id == active_user_with_token["id"],
                )
            )
            movies = result.all()

        assert len(movies) == 0

    async def test_remove_rating_not_rated_returns_404(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        del_res = await client.delete(
            f"/movies/{movie["id"]}/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert del_res.status_code == 404

    async def test_remove_rating_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        del_res = await client.delete(
            f"/movies/999999/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert del_res.status_code == 404

    async def test_remove_rating_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        del_res = await client.delete(
            f"/movies/{movie["id"]}/rating/",
        )
        assert del_res.status_code == 401

    async def test_remove_rating_does_not_touch_other_users(
        self, client, create_movie, active_user_with_token, moderator_user
    ):
        movie = await create_movie("Movie")
        await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {moderator_user["access_token"]}"
            },
        )
        await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 10},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        del_res = await client.delete(
            f"/movies/{movie["id"]}/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert del_res.status_code == 204

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                    MovieRatingModel.user_id == active_user_with_token["id"],
                )
            )
            del_movie = result.all()

            result_other = await db.scalars(
                select(MovieRatingModel).where(
                    MovieRatingModel.movie_id == movie["id"],
                    MovieRatingModel.user_id == moderator_user["id"],
                )
            )
            exist_movie = result_other.all()

        assert len(exist_movie) == 1
        assert len(del_movie) == 0


class TestGetMyRating:
    async def test_get_my_rating_returns_200(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        put_res = await client.put(
            f"/movies/{movie["id"]}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert put_res.status_code == 200
        res = await client.get(
            f"/movies/{movie['id']}/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["rating"] == 5
        assert data["movie_id"] == movie["id"]

    async def test_get_my_rating_not_rated_returns_404(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.get(
            f"/movies/{movie["id"]}/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 404

    async def test_get_my_rating_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.get(
            f"/movies/{movie['id']}/rating/",
        )
        assert res.status_code == 401

    async def test_get_my_rating_does_not_return_other_users_rating(
        self, client, create_movie, active_user_with_token, moderator_user
    ):
        movie = await create_movie("Movie")
        await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 10},
            headers={
                "Authorization": f"Bearer {moderator_user["access_token"]}"
            },
        )

        res = await client.get(
            f"/movies/{movie['id']}/rating/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["rating"] == 5
        assert data["movie_id"] == movie["id"]


class TestMovieAverageRating:
    async def test_movie_details_without_ratings_has_null_average(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.get(
            f"/movies/{movie['id']}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["average_rating"] is None

    async def test_movie_details_returns_average_rating(
        self, client, create_movie, active_user_with_token, moderator_user
    ):
        movie = await create_movie("Movie")
        put_res_1 = await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        put_res_2 = await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 10},
            headers={
                "Authorization": f"Bearer {moderator_user["access_token"]}"
            },
        )
        res = await client.get(
            f"/movies/{movie['id']}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["average_rating"] == 7.5

    async def test_movie_details_average_rating_is_rounded(
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
            f"/movies/{movie['id']}/rating/",
            json={"rating": 7},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 8},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 8},
            headers={
                "Authorization": f"Bearer {moderator_user["access_token"]}"
            },
        )
        res = await client.get(
            f"/movies/{movie['id']}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["average_rating"] == 7.7

    async def test_movie_details_average_rating_ignores_other_movies(
        self, client, create_movie, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")

        await client.put(
            f"/movies/{movie1['id']}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        await client.put(
            f"/movies/{movie2['id']}/rating/",
            json={"rating": 10},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        res = await client.get(
            f"/movies/{movie1['id']}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["average_rating"] == 5.0

    async def test_movie_details_average_rating_updates_when_rating_changes(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 5},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        await client.put(
            f"/movies/{movie['id']}/rating/",
            json={"rating": 10},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        res = await client.get(
            f"/movies/{movie['id']}/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["average_rating"] == 10.0
