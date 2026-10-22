from datetime import datetime, timezone
from decimal import Decimal

from database.models.payments import PaymentStatusEnum

HISTORY_URL = "/payments/"


def auth(user):
    return {"Authorization": f"Bearer {user['access_token']}"}


def at(day, hour=12):
    return datetime(2026, 3, day, hour, tzinfo=timezone.utc)


class TestPaymentHistory:
    async def test_history_returns_200_with_payment_data(
        self,
        client,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        order = await create_order(active_user_with_token["id"], [])
        payment = await create_payment(
            active_user_with_token["id"],
            order["id"],
            amount="49.90",
            status=PaymentStatusEnum.REFUNDED,
        )

        res = await client.get(
            HISTORY_URL, headers=auth(active_user_with_token)
        )

        assert res.status_code == 200
        data = res.json()
        assert data["total_items"] == 1
        item = data["payments"][0]
        assert item["id"] == payment["id"]
        assert item["order_id"] == order["id"]
        assert item["user_id"] == active_user_with_token["id"]
        assert Decimal(item["amount"]) == Decimal("49.90")
        assert item["status"] == "refunded"
        assert item["created_at"]

    async def test_history_returns_newest_first(
        self,
        client,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        user_id = active_user_with_token["id"]
        order = await create_order(user_id, [])
        middle = await create_payment(user_id, order["id"], created_at=at(15))
        newest = await create_payment(user_id, order["id"], created_at=at(20))
        oldest = await create_payment(user_id, order["id"], created_at=at(10))

        res = await client.get(
            HISTORY_URL, headers=auth(active_user_with_token)
        )

        ids = [item["id"] for item in res.json()["payments"]]
        assert ids == [newest["id"], middle["id"], oldest["id"]]

    async def test_history_contains_only_own_payments(
        self,
        client,
        create_order,
        create_payment,
        moderator_user,
        active_user_with_token,
    ):
        own_order = await create_order(active_user_with_token["id"], [])
        other_order = await create_order(moderator_user["id"], [])
        own = await create_payment(
            active_user_with_token["id"], own_order["id"]
        )
        await create_payment(moderator_user["id"], other_order["id"])

        res = await client.get(
            HISTORY_URL, headers=auth(active_user_with_token)
        )

        data = res.json()
        assert data["total_items"] == 1
        assert [item["id"] for item in data["payments"]] == [own["id"]]

    async def test_history_is_empty_for_user_without_payments(
        self, client, active_user_with_token
    ):
        res = await client.get(
            HISTORY_URL, headers=auth(active_user_with_token)
        )

        assert res.status_code == 200
        assert res.json() == {
            "payments": [],
            "prev_page": None,
            "next_page": None,
            "total_pages": 0,
            "total_items": 0,
        }

    async def test_history_pagination_links(
        self,
        client,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        user_id = active_user_with_token["id"]
        order = await create_order(user_id, [])
        for day in (10, 11, 12):
            await create_payment(user_id, order["id"], created_at=at(day))

        first = await client.get(
            HISTORY_URL,
            params={"page": 1, "per_page": 2},
            headers=auth(active_user_with_token),
        )
        second = await client.get(
            HISTORY_URL,
            params={"page": 2, "per_page": 2},
            headers=auth(active_user_with_token),
        )

        first_data = first.json()
        assert len(first_data["payments"]) == 2
        assert first_data["total_items"] == 3
        assert first_data["total_pages"] == 2
        assert first_data["prev_page"] is None
        assert first_data["next_page"] == "/payments/?page=2&per_page=2"

        second_data = second.json()
        assert len(second_data["payments"]) == 1
        assert second_data["prev_page"] == "/payments/?page=1&per_page=2"
        assert second_data["next_page"] is None

    async def test_history_page_beyond_the_last_is_empty(
        self,
        client,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        order = await create_order(active_user_with_token["id"], [])
        await create_payment(active_user_with_token["id"], order["id"])

        res = await client.get(
            HISTORY_URL,
            params={"page": 99},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 200
        assert res.json()["payments"] == []

    async def test_history_rejects_invalid_pagination(
        self, client, active_user_with_token
    ):
        headers = auth(active_user_with_token)

        assert (
            await client.get(HISTORY_URL, params={"page": 0}, headers=headers)
        ).status_code == 422
        assert (
            await client.get(
                HISTORY_URL, params={"per_page": 21}, headers=headers
            )
        ).status_code == 422

    async def test_history_without_token_returns_401(self, client):
        res = await client.get(HISTORY_URL)

        assert res.status_code == 401
