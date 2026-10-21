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
