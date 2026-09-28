from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.movies import GenreModel
from schemas.movies import GenreResponseSchema, GenreCreateUpdateRequestSchema
from security.dependencies import require_moderator

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
        },
        403: {
            "description": "The user is authenticated but does not have moderator or admin permissions.",
            "content": {
                "application/json": {
                    "example": {"detail": "You are not a moderator"}
                }
            },
        },
    },
)


@router.post(
    "/genres/",
    summary="Create a new genre",
    description="Genre creation by a moderator",
    response_model=GenreResponseSchema,
    status_code=201,
    responses={
        409: {
            "description": "Conflict - Genre with this name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with this name already exists",
                    }
                }
            },
        },
    },
)
async def create_genre(
    genre_data: GenreCreateUpdateRequestSchema,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    existing_genre = await db.scalar(
        select(GenreModel).where(GenreModel.name == genre_data.name)
    )
    if existing_genre:
        raise HTTPException(
            status_code=409, detail="Genre with this name already exists"
        )

    new_genre = GenreModel(name=genre_data.name)
    db.add(new_genre)
    await db.commit()

    return GenreResponseSchema.model_validate(new_genre)
