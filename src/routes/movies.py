from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.database import get_postgresql_db
from database.models.movies import MovieModel, GenreModel, movie_genres_model
from schemas.movies import (
    MovieDetailResponseSchema,
    GenreWithMovieCountResponseSchema,
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
