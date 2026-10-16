from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.cart import CartModel, CartItemModel
from database.models.movies import MovieModel
from schemas.accounts import MessageResponseSchema
from schemas.cart import (
    CartItemAddRequestSchema,
    CartResponseSchema,
    CartItemResponseSchema,
)
from schemas.movies import GenreResponseSchema
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/cart",
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
    "/items/",
    summary="Add a movie to the cart",
    description=(
        "Adds a movie to the current user's cart. The cart is created "
        "automatically on the first addition. A movie can be added only "
        "once and only if it has a price. Authentication required."
    ),
    response_model=MessageResponseSchema,
    status_code=201,
    responses={
        400: {
            "description": "The movie has no price and cannot be purchased",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "This movie is not available for purchase"
                    }
                }
            },
        },
        404: {
            "description": "Movie with this id does not exist",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with this id does not exist"}
                }
            },
        },
        409: {
            "description": "The movie is already in the cart",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie is already in the cart"}
                }
            },
        },
    },
)
async def add_item_to_cart(
    movie_data: CartItemAddRequestSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_movie = await db.scalar(
        select(MovieModel).where(MovieModel.id == movie_data.movie_id)
    )
    if db_movie is None:
        raise HTTPException(
            status_code=404, detail="Movie with this id does not exist"
        )

    if not db_movie.price:
        raise HTTPException(
            status_code=400, detail="This movie is not available for purchase"
        )

    user_cart = await db.scalar(
        select(CartModel).where(CartModel.user_id == current_user.id)
    )

    if not user_cart:
        user_cart = CartModel(user_id=current_user.id)
        db.add(user_cart)
        await db.flush()

    movie_in_cart = await db.scalar(
        select(CartItemModel).where(
            CartItemModel.movie_id == movie_data.movie_id,
            CartItemModel.cart_id == user_cart.id,
        )
    )
    if movie_in_cart:
        raise HTTPException(
            status_code=409, detail="Movie is already in the cart"
        )

    add_movie_in_cart = CartItemModel(
        movie_id=movie_data.movie_id,
        cart_id=user_cart.id,
    )
    db.add(add_movie_in_cart)
    await db.commit()
    return MessageResponseSchema(message="Movie added to the cart")


@router.get(
    "/",
    summary="Get my cart",
    description=(
        "Returns the current user's cart with the movies in it (title, "
        "price, genres, release year), the number of items and the total "
        "price. If the user has no cart yet, an empty cart is returned. "
        "Authentication required."
    ),
    response_model=CartResponseSchema,
    status_code=200,
)
async def get_cart(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    user_cart = await db.scalar(
        select(CartModel).where(CartModel.user_id == current_user.id)
    )
    if not user_cart:
        return CartResponseSchema(
            items=[],
            total_items=0,
            total_price=Decimal("0"),
        )

    stmt = await db.execute(
        select(CartItemModel, MovieModel)
        .join(MovieModel, MovieModel.id == CartItemModel.movie_id)
        .where(CartItemModel.cart_id == user_cart.id)
        .options(selectinload(MovieModel.genres))
        .order_by(CartItemModel.added_at.asc())
    )
    rows = stmt.all()

    items = [
        CartItemResponseSchema(
            movie_id=movie.id,
            name=movie.name,
            price=movie.price,
            year=movie.year,
            genres=[
                GenreResponseSchema.model_validate(g) for g in movie.genres
            ],
            added_at=item.added_at,
        )
        for item, movie in rows
    ]
    total_items = len(items)
    total_price = sum((item.price for item in items), Decimal("0"))

    return CartResponseSchema(
        items=items,
        total_items=total_items,
        total_price=total_price,
    )


@router.delete(
    "/items/{movie_id}/",
    summary="Remove a movie from the cart",
    description=(
        "Removes the movie from the current user's cart. "
        "Authentication required."
    ),
    status_code=204,
    responses={
        404: {
            "description": "The movie is not in the user's cart",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie is not in the cart"}
                }
            },
        },
    },
)
async def remove_item(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    user_cart = await db.scalar(
        select(CartModel).where(CartModel.user_id == current_user.id)
    )
    if not user_cart:
        raise HTTPException(status_code=404, detail="Movie is not in the cart")

    item = await db.scalar(
        select(CartItemModel).where(
            CartItemModel.movie_id == movie_id,
            CartItemModel.cart_id == user_cart.id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Movie is not in the cart")

    await db.delete(item)
    await db.commit()
    return
