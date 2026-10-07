from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database.database import get_postgresql_db
from database.models.movies import MovieModel, GenreModel, movie_genres_model
from schemas.movies import (
    MovieDetailResponseSchema,
    GenreWithMovieCountResponseSchema,
    MovieListResponseSchema,
    MovieListItemResponseSchema,
)

router = APIRouter(prefix="/movies")


@router.get(
    "/genres/",
    summary="List genres with movie counts",
    description="Returns a list of all genres along with how many movies belong to each. Publicly accessible, no authentication required.",
    response_model=list[GenreWithMovieCountResponseSchema],
    status_code=200,
)
async def get_movie_genres(
    db: AsyncSession = Depends(get_postgresql_db),
):
    stmt = (
        select(
            GenreModel.id,
            GenreModel.name,
            func.count(movie_genres_model.c.movie_id).label("movie_count"),
        )
        .outerjoin(
            movie_genres_model, movie_genres_model.c.genre_id == GenreModel.id
        )
        .group_by(GenreModel.id, GenreModel.name)
    )
    result = await db.execute(stmt)
    db_genres = result.all()

    return db_genres


@router.get(
    "/",
    response_model=MovieListResponseSchema,
)
async def get_movies_list(
    db: AsyncSession = Depends(get_postgresql_db),
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10, ge=1, le=20, description="Number of items per page"
    ),
    genre_id: list[int] | None = Query(None, description="Filter by genre id"),
    year: int | None = Query(None, description="Filter by year"),
):
    offset = (page - 1) * per_page
    filters = []
    if genre_id:
        filters.append(
            MovieModel.genres.any(
                GenreModel.id.in_(genre_id),
            )
        )

    if year is not None:
        filters.append(MovieModel.year == year)

    count_stmt = select(func.count(MovieModel.id)).where(*filters)
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    stmt = (
        select(MovieModel)
        .where(*filters)
        .options(selectinload(MovieModel.genres))
        .order_by(MovieModel.id)
    )

    stmt = stmt.offset(offset).limit(per_page)

    result = await db.execute(stmt)
    db_movies = result.scalars().all() or []

    movie_list = [
        MovieListItemResponseSchema.model_validate(movie)
        for movie in db_movies
    ]

    total_pages = (total_items + per_page - 1) // per_page

    prev_page_number = min(page - 1, total_pages)

    genre_query = "".join(f"&genre_id={genr_id}" for genr_id in genre_id or [])
    year_query = f"&year={year}" if year is not None else ""

    return MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            f"/movies/?page={prev_page_number}&per_page={per_page}{genre_query}{year_query}"
            if prev_page_number >= 1
            else None
        ),
        next_page=(
            f"/movies/?page={page + 1}&per_page={per_page}{genre_query}{year_query}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get(
    "/{movie_id}/",
    summary="Get movie details",
    description="Retrieve full details of a single movie by its ID. Publicly accessible, no authentication required.",
    response_model=MovieDetailResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "Movie with this id does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with this id does not exist",
                    }
                }
            },
        },
    },
)
async def get_movie_details(
    movie_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
) -> MovieDetailResponseSchema:

    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.genres),
            joinedload(MovieModel.directors),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.certification),
        )
        .where(MovieModel.id == movie_id)
    )

    db_movie = await db.scalar(stmt)

    if not db_movie:
        raise HTTPException(
            status_code=404, detail="Movie with this id does not exist"
        )

    return MovieDetailResponseSchema.model_validate(db_movie)
