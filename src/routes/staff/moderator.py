from datetime import date, datetime, timedelta, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.orders import OrderStatusEnum, OrderModel
from database.models.payments import PaymentStatusEnum, PaymentModel
from routes.cart import build_cart_response
from routes.orders import build_orders_response
from routes.payments import build_payments_response
from schemas.cart import CartResponseSchema
from schemas.orders import OrderListResponseSchema
from schemas.payments import PaymentListResponseSchema
from security.dependencies import require_moderator

router = APIRouter(
    prefix="/moderator",
    tags=["Moderator: Carts, Orders & Payments"],
    dependencies=[Depends(require_moderator)],
    responses={
        401: {
            "description": "Not authenticated or invalid/expired token.",
            "content": {
                "application/json": {
                    "example": {"detail": "Token is invalid."}
                }
            },
        },
        403: {
            "description": "Moderator or administrator access required.",
            "content": {
                "application/json": {
                    "example": {"detail": "You are not a moderator"}
                }
            },
        },
    },
)


@router.get(
    "/carts/{user_id}/",
    summary="View a user's cart",
    description=(
        "Returns the contents of any user's cart for analysis or "
        "troubleshooting."
    ),
    response_model=CartResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "User not found",
            "content": {
                "application/json": {"example": {"detail": "User not found"}}
            },
        },
    },
)
async def moderator_get_cart(
    user_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
):
    current_user = await db.scalar(
        select(UserModel).where(UserModel.id == user_id)
    )
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    return await build_cart_response(user_id, db)


@router.get(
    "/orders/",
    summary="List all orders",
    description=(
        "Returns a paginated list of all users' orders (newest first). "
        "Can be filtered by user, status and creation date range "
        "(both dates are inclusive)."
    ),
    response_model=OrderListResponseSchema,
    status_code=200,
)
async def moderator_get_orders(
    user_id: int | None = Query(None, description="Filter by user id"),
    status: OrderStatusEnum | None = Query(
        None, description="Filter by order status"
    ),
    date_from: date | None = Query(
        None, description="Orders created on or after this date"
    ),
    date_to: date | None = Query(
        None, description="Orders created on or before this date"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10,
        ge=1,
        le=20,
        description="Number of items per page (max 20)",
    ),
    db: AsyncSession = Depends(get_postgresql_db),
):
    filters = []
    if user_id is not None:
        filters.append(OrderModel.user_id == user_id)
    if status is not None:
        filters.append(OrderModel.status == status)
    if date_from is not None:
        filters.append(
            OrderModel.created_at >= datetime.combine(date_from, time.min)
        )
    if date_to is not None:
        filters.append(
            OrderModel.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min)
        )

    extra_query = ""
    if user_id is not None:
        extra_query += f"&user_id={user_id}"
    if status is not None:
        extra_query += f"&status={status.value}"
    if date_from is not None:
        extra_query += f"&date_from={date_from}"
    if date_to is not None:
        extra_query += f"&date_to={date_to}"

    return await build_orders_response(
        filters, page, per_page, db, "/moderator/orders/", extra_query
    )


@router.get(
    "/payments/",
    summary="List all payments",
    description=(
        "Returns a paginated list of all users' payments (newest first). "
        "Can be filtered by user, status (successful, canceled or refunded) "
        "and creation date range (both dates are inclusive)."
    ),
    response_model=PaymentListResponseSchema,
    status_code=200,
)
async def moderator_get_payments(
    user_id: int | None = Query(None, description="Filter by user id"),
    status: PaymentStatusEnum | None = Query(
        None, description="Filter by payment status"
    ),
    date_from: date | None = Query(
        None, description="Payments created on or after this date (UTC)"
    ),
    date_to: date | None = Query(
        None, description="Payments created on or before this date (UTC)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10,
        ge=1,
        le=20,
        description="Number of items per page (max 20)",
    ),
    db: AsyncSession = Depends(get_postgresql_db),
):
    """
    Return a page of payments of all users for moderators and administrators.

    Each given filter narrows the result; filters are combined with AND.
    The date boundaries are interpreted in UTC, because payment timestamps
    are stored with a time zone. The filters are repeated in the pagination
    links so that the next page keeps them.

    Args:
        user_id (int | None): Only payments of this user.
        status (PaymentStatusEnum | None): Only payments with this status.
        date_from (date | None): Payments created on or after this date.
        date_to (date | None): Payments created on or before this date.
        page (int): Page number, starting from 1.
        per_page (int): Number of payments per page (max 20).
        db (AsyncSession): Database session (injected).

    Returns:
        PaymentListResponseSchema: The page of payments and pagination links.
    """

    filters = []
    if user_id is not None:
        filters.append(PaymentModel.user_id == user_id)
    if status is not None:
        filters.append(PaymentModel.status == status)
    if date_from is not None:
        filters.append(
            PaymentModel.created_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        filters.append(
            PaymentModel.created_at
            < datetime.combine(
                date_to + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
        )

    extra_query = ""
    if user_id is not None:
        extra_query += f"&user_id={user_id}"
    if status is not None:
        extra_query += f"&status={status.value}"
    if date_from is not None:
        extra_query += f"&date_from={date_from}"
    if date_to is not None:
        extra_query += f"&date_to={date_to}"

    return await build_payments_response(
        filters,
        page,
        per_page,
        db,
        "/moderator/payments/",
        extra_query,
    )
