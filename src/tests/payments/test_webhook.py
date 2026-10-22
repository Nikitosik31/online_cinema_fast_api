from decimal import Decimal

import pytest
import stripe
from sqlalchemy import select

from database.models.cart import CartItemModel
from database.models.orders import OrderModel, OrderStatusEnum
from database.models.payments import (
    PaymentItemModel,
    PaymentModel,
    PaymentStatusEnum,
)
from tests.conftest import test_AsyncPostgresqlSessionLocal

WEBHOOK_URL = "/payments/webhook/"


def completed_session(order, **overrides):
    session = {
        "id": "cs_test_1",
        "payment_status": "paid",
        "payment_intent": "pi_test_1",
        "amount_total": int(order["total_amount"] * 100),
        "metadata": {"order_id": str(order["id"])},
    }
    session.update(overrides)
    return session


def expired_session(order, **overrides):
    session = {
        "id": "cs_test_expired",
        "metadata": {"order_id": str(order["id"])},
    }
    session.update(overrides)
    return session


async def get_all(model):
    async with test_AsyncPostgresqlSessionLocal() as db:
        return (await db.scalars(select(model))).all()


async def get_order(order_id):
    async with test_AsyncPostgresqlSessionLocal() as db:
        return await db.scalar(
            select(OrderModel).where(OrderModel.id == order_id)
        )


async def get_payment(payment_id):
    async with test_AsyncPostgresqlSessionLocal() as db:
        return await db.scalar(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )


class TestWebhookSecurity:
    async def test_invalid_signature_returns_400(self, client):
        res = await client.post(
            WEBHOOK_URL,
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=not-a-valid-signature"},
        )

        assert res.status_code == 400
        assert res.json()["detail"] == "Invalid signature"

    async def test_missing_signature_header_returns_422(self, client):
        res = await client.post(WEBHOOK_URL, content=b"{}")

        assert res.status_code == 422

    async def test_invalid_payload_returns_400(self, client, monkeypatch):
        def raise_value_error(payload, sig_header, secret):
            raise ValueError("not json")

        monkeypatch.setattr(
            stripe.Webhook, "construct_event", raise_value_error
        )

        res = await client.post(
            WEBHOOK_URL,
            content=b"not json",
            headers={"stripe-signature": "test"},
        )

        assert res.status_code == 400
        assert res.json()["detail"] == "Invalid payload"

    async def test_unknown_event_type_is_acknowledged(
        self, client, send_stripe_event
    ):
        res = await send_stripe_event("customer.created", {"id": "cus_1"})

        assert res.status_code == 200
        assert res.json() == {"message": "Event received"}
        assert await get_all(PaymentModel) == []


class TestCheckoutCompleted:
    async def test_completed_records_payment_and_items(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        order = await create_order(
            active_user_with_token["id"],
            [(movie_1["id"], 150), (movie_2["id"], 250)],
        )

        res = await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        assert res.status_code == 200
        payments = await get_all(PaymentModel)
        assert len(payments) == 1
        payment = payments[0]
        assert payment.user_id == active_user_with_token["id"]
        assert payment.order_id == order["id"]
        assert payment.amount == Decimal("400")
        assert payment.status == PaymentStatusEnum.SUCCESSFUL
        assert payment.external_payment_id == "pi_test_1"

        items = await get_all(PaymentItemModel)
        assert len(items) == 2
        assert all(item.payment_id == payment.id for item in items)
        assert {item.price_at_payment for item in items} == {
            Decimal("150"),
            Decimal("250"),
        }

    async def test_completed_marks_order_as_paid(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        assert (await get_order(order["id"])).status == OrderStatusEnum.PAID

    async def test_completed_removes_only_paid_movies_from_cart(
        self,
        send_stripe_event,
        create_movie,
        create_cart_item,
        create_order,
        active_user_with_token,
    ):
        user_id = active_user_with_token["id"]
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        movie_3 = await create_movie("Movie3", price=300)
        for movie in (movie_1, movie_2, movie_3):
            await create_cart_item(user_id, movie["id"])
        order = await create_order(
            user_id, [(movie_1["id"], 150), (movie_2["id"], 250)]
        )

        await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        cart_items = await get_all(CartItemModel)
        assert [item.movie_id for item in cart_items] == [movie_3["id"]]

    async def test_completed_works_when_user_has_no_cart(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        res = await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        assert res.status_code == 200
        assert len(await get_all(PaymentModel)) == 1

    async def test_completed_sends_confirmation_email(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
        mock_send_payment_email,
    ):
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        order = await create_order(
            active_user_with_token["id"],
            [(movie_1["id"], 150), (movie_2["id"], 250)],
        )

        await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        mock_send_payment_email.assert_awaited_once()
        kwargs = mock_send_payment_email.await_args.kwargs
        assert kwargs["to"] == active_user_with_token["email"]
        assert str(order["id"]) in kwargs["subject"]
        assert "Movie1" in kwargs["body"]
        assert "Movie2" in kwargs["body"]
        assert "400" in kwargs["body"]

    async def test_completed_still_records_payment_when_email_fails(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
        mock_send_payment_email,
    ):
        mock_send_payment_email.side_effect = Exception("SMTP is down")
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        res = await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        assert res.status_code == 200
        assert len(await get_all(PaymentModel)) == 1
        assert (await get_order(order["id"])).status == OrderStatusEnum.PAID

    async def test_repeated_delivery_records_payment_once(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
        mock_send_payment_email,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        first = await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )
        second = await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert len(await get_all(PaymentModel)) == 1
        assert len(await get_all(PaymentItemModel)) == 1
        mock_send_payment_email.assert_awaited_once()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"amount_total": 1},
            {"payment_status": "unpaid"},
            {"payment_intent": None},
            {"metadata": {}},
            {"metadata": {"order_id": "999999"}},
        ],
        ids=[
            "amount_mismatch",
            "not_paid",
            "no_payment_intent",
            "no_order_id",
            "unknown_order",
        ],
    )
    async def test_completed_is_ignored_when_it_cannot_be_applied(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
        mock_send_payment_email,
        overrides,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        res = await send_stripe_event(
            "checkout.session.completed",
            completed_session(order, **overrides),
        )

        assert res.status_code == 200
        assert await get_all(PaymentModel) == []
        assert (await get_order(order["id"])).status == OrderStatusEnum.PENDING
        mock_send_payment_email.assert_not_awaited()

    @pytest.mark.parametrize(
        "status", [OrderStatusEnum.PAID, OrderStatusEnum.CANCELED]
    )
    async def test_completed_is_ignored_for_not_pending_order(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
        mock_send_payment_email,
        status,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)], status=status
        )

        res = await send_stripe_event(
            "checkout.session.completed", completed_session(order)
        )

        assert res.status_code == 200
        assert await get_all(PaymentModel) == []
        assert (await get_order(order["id"])).status == status
        mock_send_payment_email.assert_not_awaited()


class TestCheckoutExpired:
    async def test_expired_records_canceled_payment(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        res = await send_stripe_event(
            "checkout.session.expired", expired_session(order)
        )

        assert res.status_code == 200
        payments = await get_all(PaymentModel)
        assert len(payments) == 1
        payment = payments[0]
        assert payment.status == PaymentStatusEnum.CANCELED
        assert payment.user_id == active_user_with_token["id"]
        assert payment.order_id == order["id"]
        assert payment.amount == Decimal("150")
        assert payment.external_payment_id == "cs_test_expired"

    async def test_expired_keeps_order_pending_and_has_no_items(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        await send_stripe_event(
            "checkout.session.expired", expired_session(order)
        )

        assert (await get_order(order["id"])).status == OrderStatusEnum.PENDING
        assert await get_all(PaymentItemModel) == []

    async def test_expired_repeated_delivery_records_payment_once(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        await send_stripe_event(
            "checkout.session.expired", expired_session(order)
        )
        await send_stripe_event(
            "checkout.session.expired", expired_session(order)
        )

        assert len(await get_all(PaymentModel)) == 1

    async def test_expired_after_a_paid_attempt_is_ignored(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"],
            [(movie["id"], 150)],
            status=OrderStatusEnum.PAID,
        )

        res = await send_stripe_event(
            "checkout.session.expired", expired_session(order)
        )

        assert res.status_code == 200
        assert await get_all(PaymentModel) == []

    @pytest.mark.parametrize(
        "overrides",
        [{"metadata": {}}, {"metadata": {"order_id": "999999"}}],
        ids=["no_order_id", "unknown_order"],
    )
    async def test_expired_is_ignored_when_order_is_unknown(
        self,
        send_stripe_event,
        create_movie,
        create_order,
        active_user_with_token,
        overrides,
    ):
        movie = await create_movie("Movie1", price=150)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 150)]
        )

        res = await send_stripe_event(
            "checkout.session.expired", expired_session(order, **overrides)
        )

        assert res.status_code == 200
        assert await get_all(PaymentModel) == []


class TestChargeRefunded:
    async def test_full_refund_marks_payment_as_refunded(
        self,
        send_stripe_event,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        order = await create_order(active_user_with_token["id"], [])
        payment = await create_payment(
            active_user_with_token["id"],
            order["id"],
            external_payment_id="pi_test_1",
        )

        res = await send_stripe_event(
            "charge.refunded",
            {"refunded": True, "payment_intent": "pi_test_1"},
        )

        assert res.status_code == 200
        db_payment = await get_payment(payment["id"])
        assert db_payment.status == PaymentStatusEnum.REFUNDED

    async def test_partial_refund_is_ignored(
        self,
        send_stripe_event,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        order = await create_order(active_user_with_token["id"], [])
        payment = await create_payment(
            active_user_with_token["id"],
            order["id"],
            external_payment_id="pi_test_1",
        )

        res = await send_stripe_event(
            "charge.refunded",
            {"refunded": False, "payment_intent": "pi_test_1"},
        )

        assert res.status_code == 200
        db_payment = await get_payment(payment["id"])
        assert db_payment.status == PaymentStatusEnum.SUCCESSFUL

    async def test_refund_of_unknown_payment_is_ignored(
        self,
        send_stripe_event,
        create_order,
        create_payment,
        active_user_with_token,
    ):
        order = await create_order(active_user_with_token["id"], [])
        payment = await create_payment(
            active_user_with_token["id"],
            order["id"],
            external_payment_id="pi_test_1",
        )

        res = await send_stripe_event(
            "charge.refunded",
            {"refunded": True, "payment_intent": "pi_somebody_else"},
        )

        assert res.status_code == 200
        db_payment = await get_payment(payment["id"])
        assert db_payment.status == PaymentStatusEnum.SUCCESSFUL

    @pytest.mark.parametrize(
        "status", [PaymentStatusEnum.CANCELED, PaymentStatusEnum.REFUNDED]
    )
    async def test_refund_only_applies_to_successful_payments(
        self,
        send_stripe_event,
        create_order,
        create_payment,
        active_user_with_token,
        status,
    ):
        order = await create_order(active_user_with_token["id"], [])
        payment = await create_payment(
            active_user_with_token["id"],
            order["id"],
            status=status,
            external_payment_id="pi_test_1",
        )

        res = await send_stripe_event(
            "charge.refunded",
            {"refunded": True, "payment_intent": "pi_test_1"},
        )

        assert res.status_code == 200
        db_payment = await get_payment(payment["id"])
        assert db_payment.status == status
