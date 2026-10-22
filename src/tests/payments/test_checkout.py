from decimal import Decimal

import pytest
import stripe
from sqlalchemy import select

from database.models.orders import OrderModel, OrderStatusEnum
from database.models.payments import PaymentModel
from tests.conftest import test_AsyncPostgresqlSessionLocal

CHECKOUT_URL = "/payments/checkout/"


def auth(user):
    return {"Authorization": f"Bearer {user['access_token']}"}


class TestCreateCheckoutSession:
    async def test_checkout_returns_201_with_payment_url(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        order = await create_order(
            active_user_with_token["id"],
            [(movie_1["id"], 150), (movie_2["id"], 250)],
        )

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 201
        assert res.json() == {
            "checkout_url": "https://checkout.stripe.test/pay"
        }

    async def test_checkout_sends_correct_data_to_stripe(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price="9.99")
        order = await create_order(
            active_user_with_token["id"],
            [(movie_1["id"], 150), (movie_2["id"], "9.99")],
        )

        await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        mock_stripe_session.assert_awaited_once()
        kwargs = mock_stripe_session.await_args.kwargs
        assert kwargs["mode"] == "payment"
        assert kwargs["metadata"] == {"order_id": str(order["id"])}
        assert kwargs["success_url"].endswith("/payments/success/")
        assert kwargs["cancel_url"].endswith("/payments/cancel/")

        amounts = {
            line["price_data"]["product_data"]["name"]: line["price_data"][
                "unit_amount"
            ]
            for line in kwargs["line_items"]
        }
        assert amounts == {"Movie1": 15000, "Movie2": 999}
        assert all(line["quantity"] == 1 for line in kwargs["line_items"])

    async def test_checkout_does_not_create_payment_or_change_order(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        async with test_AsyncPostgresqlSessionLocal() as db:
            payments = (await db.scalars(select(PaymentModel))).all()
            db_order = await db.scalar(
                select(OrderModel).where(OrderModel.id == order["id"])
            )
        assert payments == []
        assert db_order.status == OrderStatusEnum.PENDING

    async def test_checkout_without_token_returns_401(
        self, client, mock_stripe_session
    ):
        res = await client.post(CHECKOUT_URL, json={"order_id": 1})

        assert res.status_code == 401
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_with_invalid_body_returns_422(
        self, client, active_user_with_token, mock_stripe_session
    ):
        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": "not-a-number"},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 422

    async def test_checkout_for_missing_order_returns_404(
        self, client, active_user_with_token, mock_stripe_session
    ):
        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": 999999},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 404
        assert res.json()["detail"] == "Order not found"
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_for_another_users_order_returns_404(
        self,
        client,
        create_movie,
        create_order,
        moderator_user,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie = await create_movie("Movie1", price=150)
        other_users_order = await create_order(
            moderator_user["id"], [(movie["id"], 150)]
        )

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": other_users_order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 404
        mock_stripe_session.assert_not_awaited()

    @pytest.mark.parametrize(
        "status", [OrderStatusEnum.PAID, OrderStatusEnum.CANCELED]
    )
    async def test_checkout_for_not_pending_order_returns_409(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
        status,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)], status=status
        )

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 409
        assert res.json()["detail"] == "Only pending orders can be paid"
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_when_price_changed_returns_409(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 100)]
        )

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 409
        assert "Prices have changed" in res.json()["detail"]
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_when_movie_no_longer_has_price_returns_409(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie = await create_movie("Movie1")
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 100)]
        )

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 409
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_when_total_does_not_match_items_returns_400(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )
        async with test_AsyncPostgresqlSessionLocal() as db:
            db_order = await db.scalar(
                select(OrderModel).where(OrderModel.id == order["id"])
            )
            db_order.total_amount = Decimal("999")
            await db.commit()

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 400
        assert res.json()["detail"] == "Order total does not match its items"
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_for_order_without_items_returns_400(
        self,
        client,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        order = await create_order(active_user_with_token["id"], [])

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 400
        mock_stripe_session.assert_not_awaited()

    async def test_checkout_when_stripe_fails_returns_502(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        mock_stripe_session,
    ):
        mock_stripe_session.side_effect = stripe.StripeError("Stripe is down")
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        res = await client.post(
            CHECKOUT_URL,
            json={"order_id": order["id"]},
            headers=auth(active_user_with_token),
        )

        assert res.status_code == 502
        assert res.json()["detail"] == "Payment service is unavailable"


class TestPaymentResultPages:
    async def test_success_page_is_public(self, client):
        res = await client.get("/payments/success/")

        assert res.status_code == 200
        assert "message" in res.json()

    async def test_cancel_page_is_public_and_gives_a_recommendation(
        self, client
    ):
        res = await client.get("/payments/cancel/")

        assert res.status_code == 200
        assert "different payment method" in res.json()["message"]
