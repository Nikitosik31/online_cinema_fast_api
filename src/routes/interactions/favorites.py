from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.interactions import FavoriteMovieModel
from database.models.movies import MovieModel
from schemas.accounts import MessageResponseSchema
from schemas.movies import MovieListResponseSchema, MovieListItemResponseSchema
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/movies",
    tags=["Favorites"],
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
        select(FavoriteMovieModel).where(
            FavoriteMovieModel.movie_id == movie_id,
            FavoriteMovieModel.user_id == current_user.id,
        )
    )
    if db_movie_favorite:
        raise HTTPException(
            status_code=409, detail="Movie is already in favorites"
        )

    movie_favorite = FavoriteMovieModel(
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
        select(FavoriteMovieModel).where(
            FavoriteMovieModel.movie_id == movie_id,
            FavoriteMovieModel.user_id == current_user.id,
        )
    )
    if not db_movie_in_favorite:
        raise HTTPException(
            status_code=404, detail="Movie is not in favorites"
        )

    await db.delete(db_movie_in_favorite)
    await db.commit()

    return


@router.get(
    "/favorites/",
    summary="List my favorite movies",
    description=(
        "Returns a paginated list of the current user's favorite movies, "
        "most recently added first. Authentication required."
    ),
    response_model=MovieListResponseSchema,
    status_code=200,
)
async def favorite_movies(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10, ge=1, le=20, description="Number of items per page (max 20)"
    ),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    offset = (page - 1) * per_page
    count_stmt = (
        select(func.count())
        .select_from(FavoriteMovieModel)
        .where(FavoriteMovieModel.user_id == current_user.id)
    )
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    stmt = (
        select(MovieModel)
        .join(FavoriteMovieModel, FavoriteMovieModel.movie_id == MovieModel.id)
        .where(FavoriteMovieModel.user_id == current_user.id)
        .options(selectinload(MovieModel.genres))
        .order_by(
            FavoriteMovieModel.created_at.desc(), FavoriteMovieModel.id.desc()
        )
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(stmt)
    db_movies = result.scalars().all() or []

    movie_list = [
        MovieListItemResponseSchema.model_validate(movie)
        for movie in db_movies
    ]

    total_pages = (total_items + per_page - 1) // per_page

    prev_page_number = min(page - 1, total_pages)

    return MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            f"/movies/favorites/?page={prev_page_number}&per_page={per_page}"
            if prev_page_number >= 1
            else None
        ),
        next_page=(
            f"/movies/favorites/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
