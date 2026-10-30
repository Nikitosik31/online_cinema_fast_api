import decimal
from enum import StrEnum
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column

from database.database import Base


class OrderStatusEnum(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderModel(Base):
    """
    An order created from the movies in a user's cart.

    Starts as `pending`; becomes `paid` after payment or `canceled` if the
    user cancels it first. `total_amount` is fixed at creation and does not
    change when movie prices change later. The cart is cleared only after
    payment, not when the order is created.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    status: Mapped[OrderStatusEnum] = mapped_column(
        Enum(OrderStatusEnum), default=OrderStatusEnum.PENDING
    )
    total_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))


class OrderItemModel(Base):
    """
    One movie in an order.

    `price_at_order` is a copy of the price at the time of ordering, so
    history stays correct when the price changes. A movie that appears in any
    order cannot be deleted from the catalog (`ondelete="RESTRICT"`).
    """

    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "movie_id", name="unique_order_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="RESTRICT"),
    )
    price_at_order: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
