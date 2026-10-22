import decimal
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import ForeignKey, Enum, Numeric, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from database.database import Base


class PaymentStatusEnum(StrEnum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentModel(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(
        Enum(PaymentStatusEnum), default=PaymentStatusEnum.SUCCESSFUL
    )
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
    external_payment_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True
    )


class PaymentItemModel(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE")
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    price_at_payment: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
