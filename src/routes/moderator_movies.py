from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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


@router.patch(
    "/genres/{genre_id}/",
    summary="Update a genre",
    description="Update an existing genre's name by its ID. Only available to moderators and admins.",
    response_model=GenreResponseSchema,
    status_code=200,
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
        404: {
            "description": "Genre with this id does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with this id does not exist",
                    }
                }
            },
        },
    },
)
async def patch_genre(
    genre_id: int,
    genre_data: GenreCreateUpdateRequestSchema,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_genre = await db.scalar(
        select(GenreModel).where(GenreModel.id == genre_id)
    )
    if not db_genre:
        raise HTTPException(
            status_code=404, detail="Genre with this id does not exist"
        )

    existing_genre = await db.scalar(
        select(GenreModel).where(
            GenreModel.name == genre_data.name, GenreModel.id != genre_id
        )
    )
    if existing_genre:
        raise HTTPException(
            status_code=409, detail="Genre with this name already exists"
        )

    db_genre.name = genre_data.name
    await db.commit()
    return GenreResponseSchema.model_validate(db_genre)


@router.delete(
    "/genres/{genre_id}/",
    summary="Delete a genre",
    description="Delete a genre by its ID. Only available to moderators and admins. Fails with 404 if the genre does not exist.",
    status_code=204,
    responses={
        404: {
            "description": "Genre with this id does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with this id does not exist",
                    }
                }
            },
        },
    },
)
async def delete_genre(
    genre_id: int,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    genre = await db.scalar(
        select(GenreModel).where(GenreModel.id == genre_id)
    )
    if not genre:
        raise HTTPException(
            status_code=404, detail="Genre with this id does not exist"
        )

    await db.delete(genre)
    await db.commit()
    return
