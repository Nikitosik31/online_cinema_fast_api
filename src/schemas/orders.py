import decimal
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from database.models.orders import OrderStatusEnum


class ExcludedMovieSchema(BaseModel):
    """
    A movie from the cart that was left out of the order.

    `reason` is "no price" (the movie is not for sale) or
    "already purchased".
    """

    movie_id: int
    name: str
    reason: str


class OrderItemResponseSchema(BaseModel):
    """A movie in an order, with the price at the time the order was placed."""

    movie_id: int
    name: str
    price_at_order: decimal.Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderResponseSchema(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: decimal.Decimal
    items: List[OrderItemResponseSchema]

    model_config = ConfigDict(from_attributes=True)


class OrderCreateResponseSchema(BaseModel):
    """The created order and the cart movies that could not be included in it."""

    order: OrderResponseSchema
    excluded_movies: list[ExcludedMovieSchema]

    model_config = ConfigDict(from_attributes=True)


class OrderListResponseSchema(BaseModel):
    orders: List[OrderResponseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)
