from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.interactions import CommentModel
from database.models.movies import MovieModel
from schemas.movies import CommentResponseSchema, CommentRequestSchema
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
    "/{movie_id}/comments/",
    summary="Add a comment to a movie",
    description=(
        "Creates a new comment on the movie on behalf of the current user. "
        "Authentication required."
    ),
    response_model=CommentResponseSchema,
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
    },
)
async def add_comment(
    movie_id: int,
    comment_data: CommentRequestSchema,
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

    comment = CommentModel(
        user_id=current_user.id,
        movie_id=movie_id,
        content=comment_data.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentResponseSchema.model_validate(comment)
