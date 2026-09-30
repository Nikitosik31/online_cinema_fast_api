from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.database import get_postgresql_db
from database.models.movies import MovieModel
from schemas.movies import MovieDetailResponseSchema

router = APIRouter(prefix="/movies")


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
