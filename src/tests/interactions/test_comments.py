from datetime import datetime

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


class TestListComments:
    async def test_list_comments_empty_returns_empty_list(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["comments"] == []

    async def test_list_comments_returns_movie_comments_newest_first(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment1 = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
            created_at=datetime(2024, 1, 1),
        )
        comment2 = await create_comment(
            movie["id"],
            content="good",
            user_id=active_user_with_token["id"],
            created_at=datetime(2024, 1, 3),
        )
        comment3 = await create_comment(
            movie["id"],
            content="good",
            user_id=active_user_with_token["id"],
            created_at=datetime(2024, 1, 2),
        )

        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        ids = [comment["id"] for comment in data["comments"]]
        assert ids == [comment2["id"], comment3["id"], comment1["id"]]

    async def test_list_comments_movie_not_found_returns_404(self, client):
        res = await client.get(
            f"/movies/999999/comments/",
        )
        assert res.status_code == 404

    async def test_list_comments_does_not_include_other_movies_comments(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        comment1 = await create_comment(
            movie1["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        comment2 = await create_comment(
            movie2["id"],
            content="good",
            user_id=active_user_with_token["id"],
        )

        res = await client.get(
            f"/movies/{movie1['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_items"] == 1

    async def test_list_comments_pagination_links(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        await create_comment(
            movie["id"],
            content="good",
            user_id=active_user_with_token["id"],
        )
        await create_comment(
            movie["id"],
            content="go",
            user_id=active_user_with_token["id"],
        )
        await create_comment(
            movie["id"],
            content="good",
            user_id=active_user_with_token["id"],
        )
        await create_comment(
            movie["id"],
            content="good",
            user_id=active_user_with_token["id"],
        )
        res = await client.get(
            f"/movies/{movie['id']}/comments/?page=1&per_page=2",
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["comments"]) == 2
        assert data["prev_page"] is None
        assert (
            data["next_page"]
            == f"/movies/{movie['id']}/comments/?page=2&per_page=2"
        )
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

        res2 = await client.get(
            f"/movies/{movie['id']}/comments/?page=2&per_page=2",
        )
        assert res2.status_code == 200
        data = res2.json()
        assert len(data["comments"]) == 2
        assert (
            data["prev_page"]
            == f"/movies/{movie['id']}/comments/?page=1&per_page=2"
        )
        assert (
            data["next_page"]
            == f"/movies/{movie['id']}/comments/?page=3&per_page=2"
        )
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

        res3 = await client.get(
            f"/movies/{movie['id']}/comments/?page=3&per_page=2",
        )
        assert res3.status_code == 200
        data = res3.json()
        assert len(data["comments"]) == 1
        assert (
            data["prev_page"]
            == f"/movies/{movie['id']}/comments/?page=2&per_page=2"
        )
        assert data["next_page"] is None
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

    async def test_list_comments_page_out_of_range_returns_empty_list(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        res = await client.get(
            f"/movies/{movie['id']}/comments/?page=999&per_page=2",
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["comments"]) == 0
        assert (
            data["prev_page"]
            == f"/movies/{movie['id']}/comments/?page=1&per_page=2"
        )
        assert data["next_page"] is None
        assert data["total_pages"] == 1
        assert data["total_items"] == 1


class TestDeleteComment:
    async def test_delete_own_comment_returns_204(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        res = await client.delete(
            f"/movies/{movie['id']}/comments/{comment['id']}/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )

        assert res.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(CommentModel).where(
                    CommentModel.movie_id == movie["id"],
                    CommentModel.user_id == active_user_with_token["id"],
                )
            )
            comments = result.all()

        assert len(comments) == 0

    async def test_delete_comment_by_moderator_returns_204(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(CommentModel).where(
                    CommentModel.movie_id == movie["id"],
                    CommentModel.user_id == active_user_with_token["id"],
                )
            )
            comments = result.all()

        assert len(comments) == 1

        res_delete = await client.delete(
            f"/movies/{movie['id']}/comments/{comment['id']}/",
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res_delete.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(CommentModel).where(
                    CommentModel.movie_id == movie["id"],
                    CommentModel.user_id == active_user_with_token["id"],
                )
            )
            comments = result.all()

        assert len(comments) == 0

    async def test_delete_comment_by_admin_returns_204(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
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
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(CommentModel).where(
                    CommentModel.movie_id == movie["id"],
                    CommentModel.user_id == active_user_with_token["id"],
                )
            )
            comments = result.all()

        assert len(comments) == 1

        res_delete = await client.delete(
            f"/movies/{movie['id']}/comments/{comment['id']}/",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert res_delete.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(CommentModel).where(
                    CommentModel.movie_id == movie["id"],
                    CommentModel.user_id == active_user_with_token["id"],
                )
            )
            comments = result.all()

        assert len(comments) == 0

    async def test_delete_comment_not_author_returns_403(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=moderator_user["id"],
        )
        delete_res = await client.delete(
            f"/movies/{movie['id']}/comments/{comment['id']}/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert delete_res.status_code == 403

    async def test_delete_comment_not_found_returns_404(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res_delete = await client.delete(
            f"/movies/{movie['id']}/comments/999/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_delete.status_code == 404

    async def test_delete_comment_of_other_movie_returns_404(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        movie2 = await create_movie("Movie2")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        res_delete = await client.delete(
            f"/movies/{movie2["id"]}/comments/{comment['id']}/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_delete.status_code == 404

    async def test_delete_comment_without_token_returns_401(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        res_delete = await client.delete(
            f"/movies/{movie['id']}/comments/{comment['id']}/",
        )

        assert res_delete.status_code == 401
