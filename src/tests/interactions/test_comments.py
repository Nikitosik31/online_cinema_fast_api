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

    async def test_create_reply_returns_201(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "good movie"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        data = res.json()

        res2 = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={
                "content": "good movie",
                "parent_id": data["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res2.status_code == 201
        assert res2.json()["parent_id"] == data["id"]

    async def test_create_reply_parent_not_found_returns_404(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "good movie", "parent_id": 99999},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_create_reply_parent_of_other_movie_returns_404(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie1 = await create_movie("Movie")
        movie2 = await create_movie("Movie2")

        parent = await create_comment(
            movie1["id"], active_user_with_token["id"]
        )

        res = await client.post(
            f"/movies/{movie2['id']}/comments/",
            json={"content": "reply", "parent_id": parent["id"]},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_create_reply_to_reply_returns_400(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")

        parent = await create_comment(
            movie["id"], active_user_with_token["id"]
        )

        reply = await create_comment(
            movie["id"], active_user_with_token["id"], parent_id=parent["id"]
        )

        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "reply to reply", "parent_id": reply["id"]},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 400

    async def test_create_comment_without_parent_has_null_parent_id(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "good movie"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["parent_id"] is None


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

    async def test_list_comments_returns_replies_inside_parent(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        replies1 = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
            parent_id=comment["id"],
        )
        replies2 = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
            parent_id=comment["id"],
        )

        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        reply_ids = [reply["id"] for reply in data["comments"][0]["replies"]]
        assert reply_ids == [replies1["id"], replies2["id"]]
        assert len(data["comments"]) == 1
        assert data["total_items"] == 1

    async def test_list_comments_replies_are_ordered_oldest_first(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        parent = await create_comment(
            movie["id"], active_user_with_token["id"], content="parent"
        )

        reply_jan3 = await create_comment(
            movie["id"],
            active_user_with_token["id"],
            content="third",
            parent_id=parent["id"],
            created_at=datetime(2024, 1, 3),
        )
        reply_jan1 = await create_comment(
            movie["id"],
            active_user_with_token["id"],
            content="first",
            parent_id=parent["id"],
            created_at=datetime(2024, 1, 1),
        )
        reply_jan2 = await create_comment(
            movie["id"],
            active_user_with_token["id"],
            content="second",
            parent_id=parent["id"],
            created_at=datetime(2024, 1, 2),
        )
        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        reply_ids = [r["id"] for r in data["comments"][0]["replies"]]
        assert reply_ids == [
            reply_jan1["id"],
            reply_jan2["id"],
            reply_jan3["id"],
        ]

    async def test_list_comments_pagination_counts_only_top_level(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        parent1 = await create_comment(
            movie_id=movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        parent2 = await create_comment(
            movie_id=movie["id"],
            content="second movie",
            user_id=active_user_with_token["id"],
        )
        reply_jan1 = await create_comment(
            movie_id=movie["id"],
            content="first movie",
            user_id=active_user_with_token["id"],
            parent_id=parent1["id"],
        )
        reply_jan2 = await create_comment(
            movie_id=movie["id"],
            content="second movie",
            user_id=active_user_with_token["id"],
            parent_id=parent1["id"],
        )
        reply_jan3 = await create_comment(
            movie_id=movie["id"],
            content="third movie",
            user_id=active_user_with_token["id"],
            parent_id=parent2["id"],
        )

        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["comments"]) == 2
        assert data["total_items"] == 2
        total_replies = sum(
            len(comment["replies"]) for comment in data["comments"]
        )
        assert total_replies == 3

    async def test_list_comments_comment_without_replies_has_empty_list(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["comments"]) == 1
        assert data["comments"][0]["replies"] == []

    async def test_list_comments_without_reactions_has_zero_counts(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"],
            content="good movie",
            user_id=active_user_with_token["id"],
        )
        res = await client.get(
            f"/movies/{movie['id']}/comments/",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["comments"][0]["likes_count"] == 0
        assert data["comments"][0]["dislikes_count"] == 0

    async def test_list_comments_returns_likes_and_dislikes_counts(
        self,
        client,
        create_movie,
        create_comment,
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
        admin_token = login_res.json()["access_token"]

        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"], content="Test comment"
        )
        url = f"/movies/{movie['id']}/comments/{comment['id']}/reaction/"

        await client.put(
            url,
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        await client.put(
            url,
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        await client.put(
            url,
            json={"reaction_type": "like"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        res = await client.get(f"/movies/{movie['id']}/comments/")
        assert res.status_code == 200
        data = res.json()
        assert data["comments"][0]["likes_count"] == 2
        assert data["comments"][0]["dislikes_count"] == 1

    async def test_list_comments_reaction_counts_ignore_other_comments(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment1 = await create_comment(
            movie["id"], active_user_with_token["id"], content="first"
        )
        comment2 = await create_comment(
            movie["id"], active_user_with_token["id"], content="second"
        )

        await client.put(
            f"/movies/{movie['id']}/comments/{comment1['id']}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )

        res = await client.get(f"/movies/{movie['id']}/comments/")
        assert res.status_code == 200
        by_id = {c["id"]: c for c in res.json()["comments"]}
        assert by_id[comment1["id"]]["likes_count"] == 1
        assert by_id[comment1["id"]]["dislikes_count"] == 0
        assert by_id[comment2["id"]]["likes_count"] == 0
        assert by_id[comment2["id"]]["dislikes_count"] == 0

    async def test_list_comments_reply_has_reaction_counts(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        parent = await create_comment(
            movie["id"], active_user_with_token["id"], content="parent"
        )
        reply = await create_comment(
            movie["id"],
            active_user_with_token["id"],
            content="reply",
            parent_id=parent["id"],
        )

        await client.put(
            f"/movies/{movie['id']}/comments/{reply['id']}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )

        res = await client.get(f"/movies/{movie['id']}/comments/")
        assert res.status_code == 200
        data = res.json()
        reply_data = data["comments"][0]["replies"][0]
        assert reply_data["likes_count"] == 1
        assert reply_data["dislikes_count"] == 0


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
