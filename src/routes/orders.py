from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
