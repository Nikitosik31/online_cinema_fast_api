from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from schemas.movies import GenreResponseSchema


class CartItemAddRequestSchema(BaseModel):
    movie_id: int


class CartItemResponseSchema(BaseModel):
    movie_id: int
    name: str
    price: Decimal
    year: int
    genres: list[GenreResponseSchema]
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CartResponseSchema(BaseModel):
    items: list[CartItemResponseSchema]
    total_items: int
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)
