from sqlalchemy import select

from database.models.interactions import CommentModel
from tests.conftest import test_AsyncPostgresqlSessionLocal


class TestCreateComment:
    async def test_create_comment_returns_201(
        self, client, create_movie, active_user_with_token
    ):
        content = "good movie"
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": content},
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["movie_id"] == movie["id"]
        assert data["content"] == content
        assert data["user_id"] == active_user_with_token["id"]
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(CommentModel).where(
                    CommentModel.movie_id == movie["id"]
                )
            )
            comments = result.all()

        assert len(comments) == 1
        assert comments[0].content == content

    async def test_create_comment_empty_content_returns_422(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": ""},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 422

    async def test_create_comment_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.post(
            f"/movies/999999/comments/",
            json={"content": "good movie"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_create_comment_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "good movie"},
        )
        assert res.status_code == 401
