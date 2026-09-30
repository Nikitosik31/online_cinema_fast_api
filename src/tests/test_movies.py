from sqlalchemy import select

from database.models.movies import (
    CertificationModel,
    CertificationEnum,
    GenreModel,
)
from conftest import test_AsyncPostgresqlSessionLocal


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
