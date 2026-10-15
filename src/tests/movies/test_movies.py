from sqlalchemy import select

from database.models.movies import (
    CertificationModel,
    CertificationEnum,
    GenreModel,
)
from tests.conftest import test_AsyncPostgresqlSessionLocal


class TestCreateMovie:
    async def test_create_movie_success(self, client, moderator_user):
        async with test_AsyncPostgresqlSessionLocal() as session:
            certification = await session.scalar(
                select(CertificationModel).where(
                    CertificationModel.name == CertificationEnum.G
                )
            )
        res_login = await client.post(
            "/login/",
            json={
                "email": moderator_user["email"],
                "password": moderator_user["password"],
            },
        )
        assert res_login.status_code == 200
        access_token = res_login.json()["access_token"]

        movie_res = await client.post(
            "/movies/",
            json={
                "name": "Inception",
                "year": 2010,
                "time": 148,
                "imdb": 8.8,
                "votes": 2000000,
                "description": "A thief who steals corporate secrets...",
                "certification_id": certification.id,
                "genres": ["Sci-Fi", "Action"],
                "directors": ["Christopher Nolan"],
                "stars": ["Leonardo DiCaprio"],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert movie_res.status_code == 201

    async def test_create_movie_reuses_existing_genre(
        self, client, moderator_user, existing_genre
    ):
        async with test_AsyncPostgresqlSessionLocal() as session:
            certification = await session.scalar(
                select(CertificationModel).where(
                    CertificationModel.name == CertificationEnum.G
                )
            )

        movie_res = await client.post(
            "/movies/",
            json={
                "name": "Inception",
                "year": 2010,
                "time": 148,
                "imdb": 8.8,
                "votes": 2000000,
                "description": "A thief who steals corporate secrets...",
                "certification_id": certification.id,
                "genres": ["Sci-Fi", f"{existing_genre['name']}"],
                "directors": ["Christopher Nolan"],
                "stars": ["Leonardo DiCaprio"],
            },
            headers={
                "Authorization": f"Bearer {existing_genre['access_token']}"
            },
        )
        assert movie_res.status_code == 201
        data = movie_res.json()
        genres_ids = [g["id"] for g in data["genres"]]
        assert existing_genre["id"] in genres_ids

        async with test_AsyncPostgresqlSessionLocal() as session:
            results = await session.scalars(
                select(GenreModel).where(
                    GenreModel.name == existing_genre["name"]
                )
            )
            genres_without_same_name = results.all()

            assert len(genres_without_same_name) == 1

    async def test_create_movie_duplicate(
        self, client, moderator_user, existing_movie
    ):
        movie_res = await client.post(
            "/movies/",
            json={
                "name": existing_movie["name"],
                "year": existing_movie["year"],
                "time": existing_movie["time"],
                "imdb": 8.8,
                "votes": 20000,
                "description": "A steals corporate secrets...",
                "certification_id": existing_movie["certification_id"],
                "genres": ["Sci-Fi"],
                "directors": ["some"],
                "stars": ["Leonardo DiCaprio"],
            },
            headers={
                "Authorization": f"Bearer {existing_movie['access_token']}"
            },
        )
        assert movie_res.status_code == 409

    async def test_create_movie_certification_not_found(
        self, client, moderator_user
    ):
        res_login = await client.post(
            "/login/",
            json={
                "email": moderator_user["email"],
                "password": moderator_user["password"],
            },
        )
        assert res_login.status_code == 200
        access_token = res_login.json()["access_token"]

        movie_res = await client.post(
            "/movies/",
            json={
                "name": "Inception",
                "year": 2010,
                "time": 148,
                "imdb": 8.8,
                "votes": 2000000,
                "description": "A thief who steals corporate secrets...",
                "certification_id": 9999999,
                "genres": ["Sci-Fi", "Action"],
                "directors": ["Christopher Nolan"],
                "stars": ["Leonardo DiCaprio"],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert movie_res.status_code == 404


class TestUpdateMovie:
    async def test_update_movie_success(
        self, client, moderator_user, existing_movie
    ):
        update_res = await client.patch(
            f"/movies/{existing_movie['id']}/",
            json={
                "name": "Interstellar",
            },
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )

        assert update_res.status_code == 200

    async def test_update_movie_not_found(self, client, moderator_user):
        update_res = await client.patch(
            "/movies/99999999/",
            json={"name": "Test"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert update_res.status_code == 404
        assert update_res.json() == {
            "detail": "Movie with this id does not exist"
        }

    async def test_update_movie_duplicate(
        self, client, moderator_user, existing_movie
    ):
        movie_res = await client.post(
            "/movies/",
            json={
                "name": "Interstellar",
                "year": 2020,
                "time": 150,
                "imdb": 8.8,
                "votes": 2000000,
                "description": "A thief who steals corporate secrets...",
                "certification_id": existing_movie["certification_id"],
                "genres": ["Sci-Fi", "Action"],
                "directors": ["Christopher Nolan"],
                "stars": ["Leonardo DiCaprio"],
            },
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )

        update_res = await client.patch(
            f"/movies/{existing_movie['id']}/",
            json={
                "name": "Interstellar",
                "year": 2020,
                "time": 150,
            },
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert update_res.status_code == 409

    async def test_update_movie_certification_not_found(
        self, client, existing_movie
    ):
        update_res = await client.patch(
            f"/movies/{existing_movie['id']}/",
            json={
                "certification_id": "999",
            },
            headers={
                "Authorization": f"Bearer {existing_movie['access_token']}"
            },
        )
        assert update_res.status_code == 404


class TestGetMovieDetails:
    async def test_get_movie_details_success(self, client, existing_movie):
        res = await client.get(
            f"/movies/{existing_movie['id']}/",
        )
        assert res.status_code == 200

        data = res.json()
        assert data["id"] == existing_movie["id"]
        assert data["name"] == existing_movie["name"]
        assert data["year"] == existing_movie["year"]
        assert data["time"] == existing_movie["time"]
        assert (
            data["certification"]["id"] == existing_movie["certification_id"]
        )

        genre_names = {g["name"] for g in data["genres"]}
        assert genre_names == {"Sci-Fi", "Action"}

        director_names = {d["name"] for d in data["directors"]}
        assert director_names == {"Christopher Nolan"}

        star_names = {s["name"] for s in data["stars"]}
        assert star_names == {"Leonardo DiCaprio"}

    async def test_get_movie_details_not_found(self, client, existing_movie):
        res = await client.get(
            f"/movies/999999999/",
        )
        assert res.status_code == 404
        assert res.json() == {"detail": "Movie with this id does not exist"}


class TestGetMovieByGenre:
    async def test_get_movie_by_genre_success(
        self, client, existing_movie, existing_genre
    ):
        res = await client.get(
            f"/movies/genres/",
        )
        assert res.status_code == 200

        data = res.json()
        genres_by_name = {g["name"]: g["movie_count"] for g in data}

        assert genres_by_name[existing_genre["name"]] == 0

        assert genres_by_name["Sci-Fi"] >= 1
        assert genres_by_name["Action"] >= 1
