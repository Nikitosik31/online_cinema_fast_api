from datetime import datetime

from sqlalchemy import select

from database.models.interactions import (
    NotificationTypeEnum,
    NotificationModel,
)
from tests.conftest import test_AsyncPostgresqlSessionLocal


async def fetch_notifications():
    async with test_AsyncPostgresqlSessionLocal() as db:
        result = await db.scalars(select(NotificationModel))
        return result.all()


class TestListNotifications:
    async def test_list_notifications_empty_returns_empty_list(
        self, client, active_user_with_token
    ):
        res = await client.get(
            "/notifications/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["notifications"] == []
        assert data["total_items"] == 0
        assert data["total_pages"] == 0
        assert data["prev_page"] is None
        assert data["next_page"] is None

    async def test_list_notifications_returns_only_my_notifications(
        self,
        client,
        create_movie,
        create_comment,
        create_notification,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )
        notification = await create_notification(
            active_user_with_token["id"],
            moderator_user["id"],
            comment["id"],
            NotificationTypeEnum.COMMENT_REPLY,
        )
        await create_notification(
            moderator_user["id"],
            active_user_with_token["id"],
            comment["id"],
            NotificationTypeEnum.COMMENT_REPLY,
        )
        res = await client.get(
            "/notifications/",
            headers={
                "Authorization": f"Bearer {active_user_with_token["access_token"]}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        ids = [notification["id"] for notification in data["notifications"]]
        assert ids == [notification["id"]]
        assert data["total_items"] == 1

    async def test_list_notifications_newest_first(
        self,
        client,
        create_movie,
        create_comment,
        create_notification,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )
        notification1 = await create_notification(
            active_user_with_token["id"],
            moderator_user["id"],
            comment["id"],
            NotificationTypeEnum.COMMENT_REPLY,
            created_at=datetime(2020, 1, 3),
        )
        notification2 = await create_notification(
            active_user_with_token["id"],
            moderator_user["id"],
            comment["id"],
            NotificationTypeEnum.COMMENT_REPLY,
            created_at=datetime(2020, 1, 1),
        )
        notification3 = await create_notification(
            active_user_with_token["id"],
            moderator_user["id"],
            comment["id"],
            NotificationTypeEnum.COMMENT_REPLY,
            created_at=datetime(2020, 1, 2),
        )
        res = await client.get(
            "/notifications/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        ids = [notification["id"] for notification in data["notifications"]]
        assert ids == [
            notification1["id"],
            notification3["id"],
            notification2["id"],
        ]
        assert data["total_items"] == 3

    async def test_list_notifications_pagination_links(
        self,
        client,
        create_movie,
        create_comment,
        create_notification,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )
        for _ in range(5):
            await create_notification(
                active_user_with_token["id"],
                moderator_user["id"],
                comment["id"],
                NotificationTypeEnum.COMMENT_REPLY,
            )
        headers = {
            "Authorization": f"Bearer {active_user_with_token['access_token']}"
        }

        res1 = await client.get(
            "/notifications/?page=1&per_page=2", headers=headers
        )
        assert res1.status_code == 200
        data = res1.json()
        assert len(data["notifications"]) == 2
        assert data["prev_page"] is None
        assert data["next_page"] == "/notifications/?page=2&per_page=2"
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

        res2 = await client.get(
            "/notifications/?page=2&per_page=2", headers=headers
        )
        assert res2.status_code == 200
        data = res2.json()
        assert len(data["notifications"]) == 2
        assert data["prev_page"] == "/notifications/?page=1&per_page=2"
        assert data["next_page"] == "/notifications/?page=3&per_page=2"

        res3 = await client.get(
            "/notifications/?page=3&per_page=2", headers=headers
        )
        assert res3.status_code == 200
        data = res3.json()
        assert len(data["notifications"]) == 1
        assert data["prev_page"] == "/notifications/?page=2&per_page=2"
        assert data["next_page"] is None

    async def test_list_notifications_page_out_of_range_returns_empty_list(
        self,
        client,
        create_movie,
        create_comment,
        create_notification,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )
        await create_notification(
            active_user_with_token["id"],
            moderator_user["id"],
            comment["id"],
            NotificationTypeEnum.COMMENT_LIKE,
        )

        res = await client.get(
            "/notifications/?page=99&per_page=2",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["notifications"] == []
        assert data["total_items"] == 1
        assert data["total_pages"] == 1
        assert data["next_page"] is None
        assert data["prev_page"] == "/notifications/?page=1&per_page=2"

    async def test_list_notifications_without_token_returns_401(self, client):
        res = await client.get("/notifications/")
        assert res.status_code == 401


class TestNotificationCreation:
    async def test_reply_creates_notification_for_parent_author(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        parent = await create_comment(
            movie["id"], active_user_with_token["id"]
        )

        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "reply", "parent_id": parent["id"]},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 201

        notifications = await fetch_notifications()
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.recipient_id == active_user_with_token["id"]
        assert notification.sender_id == moderator_user["id"]
        assert notification.comment_id == res.json()["id"]
        assert (
            notification.notification_type
            == NotificationTypeEnum.COMMENT_REPLY
        )
        assert notification.is_read is False

    async def test_reply_to_own_comment_does_not_create_notification(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        parent = await create_comment(
            movie["id"], active_user_with_token["id"]
        )

        res = await client.post(
            f"/movies/{movie['id']}/comments/",
            json={"content": "reply", "parent_id": parent["id"]},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        assert await fetch_notifications() == []

    async def test_like_comment_creates_notification_for_author(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )

        res = await client.put(
            f"/movies/{movie['id']}/comments/{comment['id']}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 200

        notifications = await fetch_notifications()
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.recipient_id == active_user_with_token["id"]
        assert notification.sender_id == moderator_user["id"]
        assert notification.comment_id == comment["id"]
        assert (
            notification.notification_type == NotificationTypeEnum.COMMENT_LIKE
        )

    async def test_like_own_comment_does_not_create_notification(
        self, client, create_movie, create_comment, active_user_with_token
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )

        res = await client.put(
            f"/movies/{movie['id']}/comments/{comment['id']}/reaction/",
            json={"reaction_type": "like"},
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        assert await fetch_notifications() == []

    async def test_dislike_comment_does_not_create_notification(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )

        res = await client.put(
            f"/movies/{movie['id']}/comments/{comment['id']}/reaction/",
            json={"reaction_type": "dislike"},
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 200
        assert await fetch_notifications() == []

    async def test_repeated_like_does_not_duplicate_notification(
        self,
        client,
        create_movie,
        create_comment,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie")
        comment = await create_comment(
            movie["id"], active_user_with_token["id"]
        )
        url = f"/movies/{movie['id']}/comments/{comment['id']}/reaction/"
        headers = {"Authorization": f"Bearer {moderator_user['access_token']}"}

        first = await client.put(
            url, json={"reaction_type": "like"}, headers=headers
        )
        second = await client.put(
            url, json={"reaction_type": "like"}, headers=headers
        )
        assert first.status_code == 200
        assert second.status_code == 200

        assert len(await fetch_notifications()) == 1
