from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.cart import CartModel, CartItemModel
from database.models.movies import MovieModel
from database.models.orders import OrderItemModel, OrderModel, OrderStatusEnum
from schemas.orders import (
    OrderCreateResponseSchema,
    ExcludedMovieSchema,
    OrderResponseSchema,
    OrderItemResponseSchema,
    OrderListResponseSchema,
)
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/orders",
    responses={
        401: {
            "description": "Not authenticated or invalid/expired token.",
            "content": {
                "application/json": {
                    "example": {"detail": "Token is invalid."}
                }
            },
        }
    },
)


@router.post(
    "/",
    summary="Place an order",
    description=(
        "Creates an order from the movies in the current user's cart. "
        "Movies that are unavailable (no price) or already purchased are "
        "excluded and listed in `excluded_movies`. The cart is not changed: "
        "it is cleared only after a successful payment. "
        "Authentication required."
    ),
    response_model=OrderCreateResponseSchema,
    status_code=201,
    responses={
        400: {
            "description": "The cart is empty or there is nothing to order",
            "content": {
                "application/json": {"example": {"detail": "Cart is empty"}}
            },
        },
        409: {
            "description": (
                "Some of the movies are already in a pending order"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You already have a pending order with these movies"
                    }
                }
            },
        },
    },
)
async def create_order(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    user_cart = await db.scalar(
        select(CartModel).where(CartModel.user_id == current_user.id)
    )
    if not user_cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    stmt = await db.scalars(
        select(OrderItemModel.movie_id)
        .join(OrderModel, OrderModel.id == OrderItemModel.order_id)
        .where(
            OrderModel.user_id == current_user.id,
            OrderModel.status == OrderStatusEnum.PAID,
        )
    )
    purchased_items = stmt.all()
    purchased_ids = set(purchased_items)

    stmt = await db.execute(
        select(CartItemModel, MovieModel)
        .join(MovieModel, MovieModel.id == CartItemModel.movie_id)
        .where(CartItemModel.cart_id == user_cart.id)
        .order_by(CartItemModel.added_at.asc())
    )

    rows = stmt.all()
    if not rows:
        raise HTTPException(status_code=400, detail="Cart is empty")

    items_for_order = []
    excluded_items = []

    for _, movie in rows:
        if movie.price is None:
            excluded_items.append(
                ExcludedMovieSchema(
                    movie_id=movie.id, name=movie.name, reason="no price"
                )
            )
        elif movie.id in purchased_ids:
            excluded_items.append(
                ExcludedMovieSchema(
                    movie_id=movie.id,
                    name=movie.name,
                    reason="already purchased",
                )
            )
        else:
            items_for_order.append(movie)

    if not items_for_order:
        raise HTTPException(
            status_code=400, detail="No movies available for purchase"
        )

    stmt = await db.scalars(
        select(OrderItemModel.movie_id)
        .join(OrderModel, OrderModel.id == OrderItemModel.order_id)
        .where(
            OrderModel.user_id == current_user.id,
            OrderModel.status == OrderStatusEnum.PENDING,
        )
    )
    pending_orders = stmt.all()
    pending_ids = set(pending_orders)

    candidate_ids = {movie.id for movie in items_for_order}

    if candidate_ids & pending_ids:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending order with these movies",
        )

    total = sum((movie.price for movie in items_for_order), Decimal(0))
    order = OrderModel(
        user_id=current_user.id,
        total_amount=total,
    )
    db.add(order)
    await db.flush()

    for movie in items_for_order:
        db.add(
            OrderItemModel(
                order_id=order.id,
                movie_id=movie.id,
                price_at_order=movie.price,
            ),
        )

    await db.commit()
    await db.refresh(order)

    return OrderCreateResponseSchema(
        order=OrderResponseSchema(
            id=order.id,
            created_at=order.created_at,
            status=order.status,
            total_amount=order.total_amount,
            items=[
                OrderItemResponseSchema(
                    movie_id=movie.id,
                    name=movie.name,
                    price_at_order=movie.price,
                )
                for movie in items_for_order
            ],
        ),
        excluded_movies=excluded_items,
    )


@router.get(
    "/",
    summary="List my orders",
    description=(
        "Returns a paginated list of the current user's orders (newest "
        "first) with their movies, total amount and status. "
        "Authentication required."
    ),
    response_model=OrderListResponseSchema,
    status_code=200,
)
async def list_orders(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10,
        ge=1,
        le=20,
        description="Number of items per page (max 20)",
    ),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    count_result = await db.execute(
        select(func.count())
        .select_from(OrderModel)
        .where(OrderModel.user_id == current_user.id)
    )
    total_items = count_result.scalar() or 0

    stmt = await db.scalars(
        select(OrderModel)
        .where(OrderModel.user_id == current_user.id)
        .order_by(OrderModel.created_at.desc(), OrderModel.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    orders = stmt.all()

    order_ids = [order.id for order in orders]

    items_by_order = {}
    if order_ids:
        result = await db.execute(
            select(OrderItemModel, MovieModel)
            .join(MovieModel, MovieModel.id == OrderItemModel.movie_id)
            .where(OrderItemModel.order_id.in_(order_ids))
        )
        for item, movie in result.all():
            items_by_order.setdefault(item.order_id, []).append(
                OrderItemResponseSchema(
                    movie_id=movie.id,
                    name=movie.name,
                    price_at_order=item.price_at_order,
                )
            )

    total_pages = (total_items + per_page - 1) // per_page
    prev_page_number = min(page - 1, total_pages)

    return OrderListResponseSchema(
        orders=[
            OrderResponseSchema(
                id=order.id,
                created_at=order.created_at,
                status=order.status,
                total_amount=order.total_amount,
                items=items_by_order.get(order.id, []),
            )
            for order in orders
        ],
        prev_page=(
            f"/orders/?page={prev_page_number}&per_page={per_page}"
            if prev_page_number >= 1
            else None
        ),
        next_page=(
            f"/orders/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post(
    "/{order_id}/cancel/",
    summary="Cancel an order",
    description=(
        "Cancels the current user's pending order. A paid order cannot be "
        "canceled this way: it can only be returned via a refund request. "
        "Authentication required."
    ),
    response_model=OrderResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "Order not found",
            "content": {
                "application/json": {"example": {"detail": "Order not found"}}
            },
        },
        409: {
            "description": "Only pending orders can be canceled",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Only pending orders can be canceled"
                    }
                }
            },
        },
    },
)
async def cancel_order(
    order_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    user_order = await db.scalar(
        select(OrderModel).where(
            OrderModel.user_id == current_user.id, OrderModel.id == order_id
        )
    )
    if not user_order:
        raise HTTPException(status_code=404, detail="Order not found")

    if user_order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=409, detail="Only pending orders can be canceled"
        )

    user_order.status = OrderStatusEnum.CANCELED
    await db.commit()
    await db.refresh(user_order)

    result = await db.execute(
        select(OrderItemModel, MovieModel)
        .join(MovieModel, MovieModel.id == OrderItemModel.movie_id)
        .where(OrderItemModel.order_id == user_order.id)
    )
    items = [
        OrderItemResponseSchema(
            movie_id=movie.id,
            name=movie.name,
            price_at_order=item.price_at_order,
        )
        for item, movie in result.all()
    ]

    return OrderResponseSchema(
        id=user_order.id,
        created_at=user_order.created_at,
        status=user_order.status,
        total_amount=user_order.total_amount,
        items=items,
    )
