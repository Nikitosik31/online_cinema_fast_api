"""Endpoints for paying for orders with Stripe and viewing payments."""

from decimal import Decimal
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.cart import CartModel, CartItemModel
from database.models.movies import MovieModel
from database.models.orders import OrderModel, OrderStatusEnum, OrderItemModel
from database.models.payments import (
    PaymentModel,
    PaymentStatusEnum,
    PaymentItemModel,
)
from notifications.email import send_email
from schemas.accounts import MessageResponseSchema
from schemas.payments import (
    PaymentCheckoutResponseSchema,
    PaymentCheckoutRequestSchema,
)
from security.dependencies import get_current_user
from config.config import get_settings

router = APIRouter(prefix="/payments", tags=["Payments"])

stripe.api_key = get_settings().stripe_secret_key
logger = logging.getLogger(__name__)


@router.post(
    "/checkout/",
    summary="Start paying for an order",
    description=(
        "Creates a Stripe payment page for a pending order of the current "
        "user and returns its link. The amount is taken from the order items, "
        "not from the request. If the prices of the movies changed since the "
        "order was placed, the order must be canceled and created again. "
        "The payment is confirmed by the Stripe webhook, not by this "
        "request. Authentication required."
    ),
    response_model=PaymentCheckoutResponseSchema,
    status_code=201,
    responses={
        400: {
            "description": "The order has no items or its total does not match them",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Order total does not match its items"
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated or invalid/expired token.",
            "content": {
                "application/json": {
                    "example": {"detail": "Token is invalid."}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {
                "application/json": {"example": {"detail": "Order not found"}}
            },
        },
        409: {
            "description": "The order cannot be paid",
            "content": {
                "application/json": {
                    "examples": {
                        "not_pending": {
                            "summary": "The order is not pending",
                            "value": {
                                "detail": "Only pending orders can be paid"
                            },
                        },
                        "prices_changed": {
                            "summary": "Movie prices changed after the order",
                            "value": {
                                "detail": "Prices have changed. Cancel this order and create a new one"
                            },
                        },
                    }
                }
            },
        },
        502: {
            "description": "The payment service (Stripe) is unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "Payment service is unavailable"}
                }
            },
        },
    },
)
async def create_checkout_session(
    payment_data: PaymentCheckoutRequestSchema,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    order = await db.scalar(
        select(OrderModel).where(
            OrderModel.user_id == current_user.id,
            OrderModel.id == payment_data.order_id,
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=409, detail="Only pending orders can be paid"
        )

    stmt = await db.execute(
        select(OrderItemModel, MovieModel)
        .join(MovieModel, MovieModel.id == OrderItemModel.movie_id)
        .where(OrderItemModel.order_id == order.id)
    )
    rows = stmt.all()

    if not rows:
        raise HTTPException(
            status_code=400, detail="Order total does not match its items"
        )

    sum_price_at_order = Decimal(0)
    for item, movie in rows:
        sum_price_at_order += item.price_at_order
        if item.price_at_order != movie.price:
            raise HTTPException(
                status_code=409,
                detail="Prices have changed. "
                "Cancel this order and create a new one",
            )

    if sum_price_at_order != order.total_amount:
        raise HTTPException(
            status_code=400,
            detail="Order total does not match its items",
        )

    line_items = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {"name": movie.name},
                "unit_amount": int(item.price_at_order * 100),
            },
            "quantity": 1,
        }
        for item, movie in rows
    ]

    try:
        session = await stripe.checkout.Session.create_async(
            mode="payment",
            line_items=line_items,
            success_url=f"{request.base_url}payments/success/",
            cancel_url=f"{request.base_url}payments/cancel/",
            metadata={"order_id": str(order.id)},
        )
    except stripe.StripeError:
        raise HTTPException(
            status_code=502, detail="Payment service is unavailable"
        )

    return PaymentCheckoutResponseSchema(checkout_url=session.url)


@router.get(
    "/success/",
    summary="Payment success page",
    description=(
        "The page Stripe sends the user back to after a payment. It only "
        "shows a message: the payment is confirmed by the Stripe webhook, "
        "not by this request. No authentication required, because the "
        "redirect comes from Stripe's page and has no access token."
    ),
    response_model=MessageResponseSchema,
    status_code=200,
)
async def payment_success():
    return MessageResponseSchema(
        message=(
            "Thank you! Your payment is being processed. The order will be "
            "marked as paid as soon as the payment is confirmed, and a "
            "confirmation email will be sent to you."
        )
    )


@router.get(
    "/cancel/",
    summary="Payment canceled page",
    description=(
        "The page Stripe sends the user back to when the payment was not "
        "completed (canceled or declined). It only shows a message with "
        "recommendations. The order stays pending. No authentication "
        "required, because the redirect comes from Stripe's page and has "
        "no access token."
    ),
    response_model=MessageResponseSchema,
    status_code=200,
)
async def payment_cancel():
    return MessageResponseSchema(
        message=(
            "The payment was not completed. Your order is still pending: "
            "try again, use a different payment method, or cancel the order."
        )
    )


async def handle_checkout_completed(session: dict, db: AsyncSession) -> None:
    """
    Process a completed Stripe payment page for an order.

    Does nothing (and does not raise) when the event cannot be applied, so
    that Stripe gets a 200 response and does not retry it forever: the
    payment is not paid yet, it was already recorded, the order is missing
    or not pending, or the paid amount does not match the order.

    Args:
        session (dict): The Stripe Checkout Session from the event.
        db (AsyncSession): Database session.
    """
    if session.get("payment_status") != "paid":
        return

    order_id = session.get("metadata", {}).get("order_id")
    payment_intent = session.get("payment_intent")
    if not order_id or not payment_intent:
        return

    existing_payment = await db.scalar(
        select(PaymentModel).where(
            PaymentModel.external_payment_id == payment_intent
        )
    )
    if existing_payment:
        return

    order = await db.scalar(
        select(OrderModel).where(OrderModel.id == int(order_id))
    )
    if not order or order.status != OrderStatusEnum.PENDING:
        return

    if session.get("amount_total") != int(order.total_amount * 100):
        return

    order_items = (
        await db.scalars(
            select(OrderItemModel).where(OrderItemModel.order_id == order.id)
        )
    ).all()

    movie_ids = [item.movie_id for item in order_items]

    payment = PaymentModel(
        user_id=order.user_id,
        order_id=order.id,
        amount=order.total_amount,
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=payment_intent,
    )
    db.add(payment)
    await db.flush()

    for item in order_items:
        db.add(
            PaymentItemModel(
                payment_id=payment.id,
                order_item_id=item.id,
                price_at_payment=item.price_at_order,
            )
        )

    order.status = OrderStatusEnum.PAID

    cart = await db.scalar(
        select(CartModel).where(CartModel.user_id == order.user_id)
    )
    if cart:
        await db.execute(
            delete(CartItemModel).where(
                CartItemModel.cart_id == cart.id,
                CartItemModel.movie_id.in_(movie_ids),
            )
        )

    await db.commit()

    user = await db.scalar(
        select(UserModel).where(UserModel.id == order.user_id)
    )
    stmt = await db.scalars(
        select(MovieModel.name).where(MovieModel.id.in_(movie_ids))
    )
    movies_paid = stmt.all()
    movies_list = "\n".join(f"- {name}" for name in movies_paid)
    body = (
        "Hello!\n\n"
        f"Thank you for your purchase. Your payment for order #{order.id} "
        "has been received.\n\n"
        f"Movies:\n{movies_list}\n\n"
        f"Total: {order.total_amount} USD\n\n"
        "Enjoy watching!\n"
        "Online Cinema"
    )

    try:
        await send_email(
            to=user.email,
            subject=f"Payment confirmation: order #{order.id}",
            body=body,
        )
    except Exception:
        logger.exception("Could not send the payment confirmation email")


async def handle_checkout_expired(session: dict, db: AsyncSession) -> None:
    """
    Record a canceled payment when a Stripe payment page expires unpaid.

    The user did not pay, so only a payment with the `canceled` status is
    saved (without payment items), and the order stays pending: the user can
    try to pay it again. Does nothing (and does not raise) when the event
    cannot be applied, so that Stripe gets a 200 response: the order is
    missing or no longer pending (for example, it was paid through another
    payment page), or this session was already recorded.

    The id of the Stripe session is used as `external_payment_id`, because an
    unpaid session has no payment intent.

    Args:
        session (dict): The expired Stripe Checkout Session from the event.
        db (AsyncSession): Database session.
    """
    order_id = session.get("metadata", {}).get("order_id")
    session_id = session.get("id")
    if not order_id or not session_id:
        return

    existing_payment = await db.scalar(
        select(PaymentModel).where(
            PaymentModel.external_payment_id == session_id
        )
    )
    if existing_payment:
        return

    order = await db.scalar(
        select(OrderModel).where(OrderModel.id == int(order_id))
    )
    if not order or order.status != OrderStatusEnum.PENDING:
        return

    db.add(
        PaymentModel(
            user_id=order.user_id,
            order_id=order.id,
            amount=order.total_amount,
            status=PaymentStatusEnum.CANCELED,
            external_payment_id=session_id,
        )
    )
    await db.commit()


@router.post(
    "/webhook/",
    summary="Stripe webhook",
    description=(
        "Receives payment events from Stripe (for example, a completed or "
        "expired payment page). It is called by Stripe, not by users: the "
        "request is verified with the `stripe-signature` header instead of an "
        "access token. Do not call it manually."
    ),
    response_model=MessageResponseSchema,
    status_code=200,
    responses={
        400: {
            "description": "The request body or the Stripe signature is invalid",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_payload": {
                            "summary": "The body is not valid JSON",
                            "value": {"detail": "Invalid payload"},
                        },
                        "invalid_signature": {
                            "summary": "The signature does not match",
                            "value": {"detail": "Invalid signature"},
                        },
                    }
                }
            },
        },
    },
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(...),
    db: AsyncSession = Depends(get_postgresql_db),
):
    """
    Handle an event sent by Stripe.

    The signature of the raw request body is verified with the webhook
    secret, so only genuine Stripe requests are processed. Stripe may deliver
    the same event more than once and expects a 200 response, otherwise it
    retries, so the handling must be safe to repeat.

    Args:
        request (Request): The incoming request, used to read the raw body.
        stripe_signature (str): Value of the `stripe-signature` header.

    Returns:
        MessageResponseSchema: A confirmation that the event was received.

    Raises:
        HTTPException: 400 if the body is not valid JSON or the signature
            does not match.
    """

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, get_settings().stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"].to_dict(), db)
    elif event_type == "checkout.session.expired":
        await handle_checkout_expired(event["data"]["object"].to_dict(), db)

    return MessageResponseSchema(message="Event received")
