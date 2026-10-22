"""Pydantic schemas for payments."""

from pydantic import BaseModel


class PaymentCheckoutRequestSchema(BaseModel):
    order_id: int


class PaymentCheckoutResponseSchema(BaseModel):
    """
    Link to the Stripe payment page.

    Open `checkout_url` in the browser to enter the card details. The payment
    is confirmed only by the Stripe webhook, not by returning to the site.
    """

    checkout_url: str
