"""Pydantic schemas for payments."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from database.models.payments import PaymentStatusEnum


class PaymentCheckoutRequestSchema(BaseModel):
    """Id of the order to pay for. The order must belong to the current user and be pending."""

    order_id: int


class PaymentCheckoutResponseSchema(BaseModel):
    """
    Link to the Stripe payment page.

    Open `checkout_url` in the browser to enter the card details. The payment
    is confirmed only by the Stripe webhook, not by returning to the site.
    """

    checkout_url: str


class PaymentResponseSchema(BaseModel):
    """A payment with its date and time, amount and status (successful, canceled or refunded)."""

    id: int
    order_id: int
    created_at: datetime
    amount: Decimal
    status: PaymentStatusEnum
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponseSchema(BaseModel):
    payments: list[PaymentResponseSchema]
    prev_page: str | None
    next_page: str | None
    total_pages: int
    total_items: int
