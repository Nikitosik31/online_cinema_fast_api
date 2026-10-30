from datetime import datetime, timezone

import pytest

from database.models.payments import PaymentStatusEnum

URL = "/moderator/payments/"


def auth(user):
    return {"Authorization": f"Bearer {user['access_token']}"}


def at(day, hour=12, minute=0, second=0):
    return datetime(2026, 3, day, hour, minute, second, tzinfo=timezone.utc)


@pytest.fixture
async def payments_setup(
    create_order, create_payment, moderator_user, active_user_with_token
):
    """
    Three payments of two users:
      oldest: user, successful, March 10
      middle: user, canceled,   March 15, 23:59:59 (last second of the day)
      newest: moderator, refunded, March 16, 00:00:00 (first second of the day)
    """
    user_order = await create_order(active_user_with_token["id"], [])
    moderator_order = await create_order(moderator_user["id"], [])

    oldest = await create_payment(
        active_user_with_token["id"],
        user_order["id"],
        status=PaymentStatusEnum.SUCCESSFUL,
        created_at=at(10),
    )
    middle = await create_payment(
        active_user_with_token["id"],
        user_order["id"],
        status=PaymentStatusEnum.CANCELED,
        created_at=at(15, 23, 59, 59),
    )
    newest = await create_payment(
        moderator_user["id"],
        moderator_order["id"],
        status=PaymentStatusEnum.REFUNDED,
        created_at=at(16, 0, 0, 0),
    )
    return {"oldest": oldest, "middle": middle, "newest": newest}


def ids_of(response):
    return [item["id"] for item in response.json()["payments"]]


class TestModeratorPaymentsAccess:
    async def test_moderator_gets_200(self, client, moderator_user):
        res = await client.get(URL, headers=auth(moderator_user))

        assert res.status_code == 200

    async def test_admin_gets_200(self, client, admin_user):
        login = await client.post(
            "/login/",
            json={
                "email": admin_user["email"],
                "password": admin_user["password"],
            },
        )
        token = login.json()["access_token"]

        res = await client.get(
            URL, headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200

    async def test_regular_user_gets_403(self, client, active_user_with_token):
        res = await client.get(URL, headers=auth(active_user_with_token))

        assert res.status_code == 403

    async def test_without_token_gets_401(self, client):
        res = await client.get(URL)

        assert res.status_code == 401


class TestModeratorPaymentsList:
    async def test_returns_payments_of_all_users_newest_first(
        self, client, moderator_user, payments_setup
    ):
        res = await client.get(URL, headers=auth(moderator_user))

        data = res.json()
        assert ids_of(res) == [
            payments_setup["newest"]["id"],
            payments_setup["middle"]["id"],
            payments_setup["oldest"]["id"],
        ]
        assert data["total_items"] == 3
        assert {item["user_id"] for item in data["payments"]} == {
            payments_setup["newest"]["user_id"],
            payments_setup["middle"]["user_id"],
        }

    async def test_is_empty_without_payments(self, client, moderator_user):
        res = await client.get(URL, headers=auth(moderator_user))

        assert res.json()["payments"] == []
        assert res.json()["total_items"] == 0

    async def test_filter_by_user(
        self, client, moderator_user, active_user_with_token, payments_setup
    ):
        res = await client.get(
            URL,
            params={"user_id": active_user_with_token["id"]},
            headers=auth(moderator_user),
        )

        assert ids_of(res) == [
            payments_setup["middle"]["id"],
            payments_setup["oldest"]["id"],
        ]

    @pytest.mark.parametrize(
        "status, expected",
        [
            ("successful", ["oldest"]),
            ("canceled", ["middle"]),
            ("refunded", ["newest"]),
        ],
    )
    async def test_filter_by_status(
        self, client, moderator_user, payments_setup, status, expected
    ):
        res = await client.get(
            URL, params={"status": status}, headers=auth(moderator_user)
        )

        assert ids_of(res) == [payments_setup[name]["id"] for name in expected]

    async def test_invalid_status_returns_422(self, client, moderator_user):
        res = await client.get(
            URL, params={"status": "unknown"}, headers=auth(moderator_user)
        )

        assert res.status_code == 422

    async def test_filter_date_from_is_inclusive(
        self, client, moderator_user, payments_setup
    ):
        res = await client.get(
            URL,
            params={"date_from": "2026-03-15"},
            headers=auth(moderator_user),
        )

        assert ids_of(res) == [
            payments_setup["newest"]["id"],
            payments_setup["middle"]["id"],
        ]

    async def test_filter_date_to_includes_the_whole_day(
        self, client, moderator_user, payments_setup
    ):
        res = await client.get(
            URL,
            params={"date_to": "2026-03-15"},
            headers=auth(moderator_user),
        )

        assert ids_of(res) == [
            payments_setup["middle"]["id"],
            payments_setup["oldest"]["id"],
        ]

    async def test_filter_by_single_day(
        self, client, moderator_user, payments_setup
    ):
        res = await client.get(
            URL,
            params={"date_from": "2026-03-15", "date_to": "2026-03-15"},
            headers=auth(moderator_user),
        )

        assert ids_of(res) == [payments_setup["middle"]["id"]]

    async def test_filters_are_combined(
        self, client, moderator_user, active_user_with_token, payments_setup
    ):
        res = await client.get(
            URL,
            params={
                "user_id": active_user_with_token["id"],
                "status": "successful",
                "date_to": "2026-03-12",
            },
            headers=auth(moderator_user),
        )

        assert ids_of(res) == [payments_setup["oldest"]["id"]]

    async def test_pagination_links_keep_the_filters(
        self, client, moderator_user, active_user_with_token, payments_setup
    ):
        user_id = active_user_with_token["id"]

        res = await client.get(
            URL,
            params={"user_id": user_id, "page": 1, "per_page": 1},
            headers=auth(moderator_user),
        )

        data = res.json()
        assert len(data["payments"]) == 1
        assert data["total_items"] == 2
        assert data["prev_page"] is None
        assert (
            data["next_page"]
            == f"/moderator/payments/?page=2&per_page=1&user_id={user_id}"
        )
