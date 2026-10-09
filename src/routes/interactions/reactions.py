from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.interactions import MovieReaction
from database.models.movies import MovieModel
from schemas.movies import (
    MovieReactionResponseSchema,
    MovieReactionRequestSchema,
)
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


@router.put(
    "/{movie_id}/reaction/",
    summary="Like or dislike a movie",
    description=(
        "Sets the current user's reaction (like or dislike) to the movie. "
        "If the user has already reacted to this movie, the reaction is "
        "replaced. Authentication required."
    ),
    response_model=MovieReactionResponseSchema,
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
async def put_reaction_movie(
    movie_id: int,
    data_reaction: MovieReactionRequestSchema,
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

    reaction_movie = await db.scalar(
        select(MovieReaction).where(
            MovieReaction.movie_id == movie_id,
            MovieReaction.user_id == current_user.id,
        )
    )

    try:
        if not reaction_movie:
            reaction_movie = MovieReaction(
                movie_id=movie_id,
                user_id=current_user.id,
                reaction_type=data_reaction.reaction_type,
            )
            db.add(reaction_movie)

        else:
            reaction_movie.reaction_type = data_reaction.reaction_type

        await db.commit()
        await db.refresh(reaction_movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return MovieReactionResponseSchema.model_validate(reaction_movie)
