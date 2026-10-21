import datetime

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.interactions import MovieRatingModel
from database.models.movies import MovieModel
from schemas.movies import MovieRatingResponseSchema, MovieRatingRequestSchema
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/movies",
    tags=["Ratings"],
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


@router.put(
    "/{movie_id}/rating/",
    summary="Rate a movie",
    description=(
        "Sets the current user's rating (1-10) for the movie. "
        "If the user has already rated this movie, the rating is updated. "
        "Authentication required."
    ),
    response_model=MovieRatingResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "Movie with this id does not exist",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with this id does not exist"}
                }
            },
        },
    },
)
async def set_movie_rating(
    movie_id: int,
    rating_data: MovieRatingRequestSchema,
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

    rating_movie = await db.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.movie_id == movie_id,
            MovieRatingModel.user_id == current_user.id,
        ),
    )
    try:
        if rating_movie:
            rating_movie.rating = rating_data.rating

        else:
            rating_movie = MovieRatingModel(
                movie_id=movie_id,
                rating=rating_data.rating,
                user_id=current_user.id,
            )
            db.add(rating_movie)
        await db.commit()
        await db.refresh(rating_movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return MovieRatingResponseSchema.model_validate(rating_movie)


@router.delete(
    "/{movie_id}/rating/",
    summary="Remove my rating of a movie",
    description=(
        "Removes the current user's rating for the movie. "
        "Authentication required."
    ),
    status_code=204,
    responses={
        404: {
            "description": "The user has not rated this movie",
            "content": {
                "application/json": {"example": {"detail": "Rating not found"}}
            },
        },
    },
)
async def remove_movie_rating(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    rating_movie = await db.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.movie_id == movie_id,
            MovieRatingModel.user_id == current_user.id,
        )
    )
    if not rating_movie:
        raise HTTPException(status_code=404, detail="Rating not found")

    await db.delete(rating_movie)
    await db.commit()

    return


@router.get(
    "/{movie_id}/rating/",
    summary="Get my rating of a movie",
    description=(
        "Returns the current user's rating for the movie. "
        "Authentication required."
    ),
    response_model=MovieRatingResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "The user has not rated this movie",
            "content": {
                "application/json": {"example": {"detail": "Rating not found"}}
            },
        },
    },
)
async def get_movie_rating(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    rating_movie = await db.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.movie_id == movie_id,
            MovieRatingModel.user_id == current_user.id,
        )
    )
    if not rating_movie:
        raise HTTPException(status_code=404, detail="Rating not found")

    return MovieRatingResponseSchema.model_validate(rating_movie)
