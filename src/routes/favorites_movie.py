from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.interactions import FavoriteMovie
from database.models.movies import MovieModel
from schemas.accounts import MessageResponseSchema
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/movies",
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
    "/{movie_id}/favorite/",
    summary="Add movie to favorites",
    description=(
        "Adds the movie to the current user's favorites. "
        "Authentication required."
    ),
    response_model=MessageResponseSchema,
    status_code=201,
    responses={
        404: {
            "description": "Movie with this id does not exist",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with this id does not exist"}
                }
            },
        },
        409: {
            "description": "Movie is already in favorites",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie is already in favorites"}
                }
            },
        },
    },
)
async def add_movie_to_favorite(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_movie = await db.scalar(
        select(MovieModel).where(MovieModel.id == movie_id)
    )
    if not db_movie:
        raise HTTPException(
            status_code=404, detail="Movie with this id does not exist"
        )

    db_movie_favorite = await db.scalar(
        select(FavoriteMovie).where(
            FavoriteMovie.movie_id == movie_id,
            FavoriteMovie.user_id == current_user.id,
        )
    )
    if db_movie_favorite:
        raise HTTPException(
            status_code=409, detail="Movie is already in favorites"
        )

    movie_favorite = FavoriteMovie(
        movie_id=movie_id,
        user_id=current_user.id,
    )
    db.add(movie_favorite)
    await db.commit()
    await db.refresh(movie_favorite)

    return MessageResponseSchema(message="Movie added to favorites")


@router.delete(
    "/{movie_id}/favorite/",
    summary="Remove movie from favorites",
    description=(
        "Removes the movie from the current user's favorites. "
        "Authentication required."
    ),
    status_code=204,
    responses={
        404: {
            "description": "Movie is not in the user's favorites",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie is not in favorites"}
                }
            },
        },
    },
)
async def remove_movie_from_favorite(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_movie_in_favorite = await db.scalar(
        select(FavoriteMovie).where(
            FavoriteMovie.movie_id == movie_id,
            FavoriteMovie.user_id == current_user.id,
        )
    )
    if not db_movie_in_favorite:
        raise HTTPException(
            status_code=404, detail="Movie is not in favorites"
        )

    await db.delete(db_movie_in_favorite)
    await db.commit()

    return
