from datetime import datetime

from sqlalchemy import select

from database.models.interactions import FavoriteMovieModel
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
                select(FavoriteMovieModel).where(
                    FavoriteMovieModel.movie_id == movie["id"],
                    FavoriteMovieModel.user_id == active_user_with_token["id"],
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
                select(FavoriteMovieModel).where(
                    FavoriteMovieModel.movie_id == movie["id"],
                    FavoriteMovieModel.user_id == active_user_with_token["id"],
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
                select(FavoriteMovieModel).where(
                    FavoriteMovieModel.movie_id == movie["id"],
                    FavoriteMovieModel.user_id == active_user_with_token["id"],
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
            mov1 = FavoriteMovieModel(
                user_id=moderator_user["id"],
                movie_id=movie["id"],
            )

            mov2 = FavoriteMovieModel(
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
                select(FavoriteMovieModel).where(
                    FavoriteMovieModel.movie_id == movie["id"],
                    FavoriteMovieModel.user_id == moderator_user["id"],
                )
            )
            favorite = result.all()
        assert len(favorite) == 1


class TestListFavorites:
    async def test_list_favorites_empty_returns_empty_list(
        self, client, active_user_with_token
    ):
        res = await client.get(
            f"/movies/favorites/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["movies"] == []
        assert data["total_pages"] == 0
        assert data["total_items"] == 0
        assert data["next_page"] is None
        assert data["prev_page"] is None

    async def test_list_favorites_returns_user_favorites(
        self, client, active_user_with_token, create_movie
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        movie3 = await create_movie("Movie3")

        res1 = await client.post(
            f"/movies/{movie1['id']}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        res2 = await client.post(
            f"/movies/{movie2['id']}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        res = await client.get(
            f"/movies/favorites/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie2["id"], movie1["id"]]
        movie = data["movies"][1]
        assert movie["id"] == movie1["id"]
        assert movie["name"] == movie1["name"]
        assert movie["year"] == movie1["year"]
        assert movie["imdb"] == movie1["imdb"]
        assert {genre["name"] for genre in movie["genres"]} == {
            genre["name"] for genre in movie1["genres"]
        }

    async def test_list_favorites_does_not_include_other_users_favorites(
        self, client, create_movie, moderator_user, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        async with test_AsyncPostgresqlSessionLocal() as db:
            mov1 = FavoriteMovieModel(
                user_id=moderator_user["id"],
                movie_id=movie2["id"],
            )

            mov2 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie1["id"],
            )
            db.add_all([mov1, mov2])
            await db.commit()

        res = await client.get(
            f"/movies/favorites/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(FavoriteMovieModel).where(
                    FavoriteMovieModel.movie_id == movie2["id"],
                    FavoriteMovieModel.user_id == moderator_user["id"],
                )
            )
            favorite = result.all()
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie1["id"]]

    async def test_list_favorites_does_not_include_movies_not_in_favorites(
        self, client, create_movie, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        movie3 = await create_movie("Movie3")

        post_res = await client.post(
            f"/movies/{movie1['id']}/favorite/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        res = await client.get(
            f"/movies/favorites/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie1["id"]]

    async def test_list_favorites_newest_first(
        self, client, create_movie, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        movie3 = await create_movie("Movie3")

        async with test_AsyncPostgresqlSessionLocal() as db:
            mov1 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie1["id"],
                created_at=datetime(2024, 1, 1),
            )
            mov2 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie2["id"],
                created_at=datetime(2024, 1, 3),
            )
            mov3 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie3["id"],
                created_at=datetime(2024, 1, 2),
            )

            db.add_all([mov1, mov2, mov3])
            await db.commit()

        res = await client.get(
            f"/movies/favorites/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie2["id"], movie3["id"], movie1["id"]]

    async def test_list_favorites_pagination_links(
        self, client, create_movie, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        movie3 = await create_movie("Movie3")
        movie4 = await create_movie("Movie4")
        movie5 = await create_movie("Movie5")
        async with test_AsyncPostgresqlSessionLocal() as db:
            mov1 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie1["id"],
            )
            mov2 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie2["id"],
            )
            mov3 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie3["id"],
            )
            mov4 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie4["id"],
            )
            mov5 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie5["id"],
            )

            db.add_all([mov1, mov2, mov3, mov4, mov5])
            await db.commit()

        res = await client.get(
            f"/movies/favorites/?page=1&per_page=2",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["next_page"] == "/movies/favorites/?page=2&per_page=2"
        assert data["prev_page"] is None
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

    async def test_list_favorites_without_token_returns_401(self, client):
        res = await client.get("/movies/favorites/")
        assert res.status_code == 401

    async def test_list_favorites_page_out_of_range_returns_empty_list(
        self, client, active_user_with_token, create_movie
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        movie3 = await create_movie("Movie3")
        movie4 = await create_movie("Movie4")
        movie5 = await create_movie("Movie5")
        async with test_AsyncPostgresqlSessionLocal() as db:
            mov1 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie1["id"],
            )
            mov2 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie2["id"],
            )
            mov3 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie3["id"],
            )
            mov4 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie4["id"],
            )
            mov5 = FavoriteMovieModel(
                user_id=active_user_with_token["id"],
                movie_id=movie5["id"],
            )

            db.add_all([mov1, mov2, mov3, mov4, mov5])
            await db.commit()

        res = await client.get(
            f"/movies/favorites/?page=99&per_page=2",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )

        assert res.status_code == 200
        data = res.json()
        assert data["next_page"] is None
        assert data["prev_page"] == "/movies/favorites/?page=3&per_page=2"
        assert data["total_pages"] == 3
        assert data["total_items"] == 5
        assert data["movies"] == []
