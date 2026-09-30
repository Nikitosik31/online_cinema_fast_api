from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.movies import (
    GenreModel,
    StarModel,
    MovieModel,
    CertificationModel,
    DirectorModel,
)
from schemas.movies import (
    GenreResponseSchema,
    GenreCreateUpdateRequestSchema,
    StarResponseSchema,
    StarCreateUpdateRequestSchema,
    MovieCreateRequestSchema,
    MovieDetailResponseSchema,
)
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


@router.post(
    "/stars/",
    summary="Create a new star",
    description="Create a new star (actor). Only available to moderators and admins.",
    response_model=StarResponseSchema,
    status_code=201,
    responses={
        409: {
            "description": "Conflict - Star with this name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Star with this name already exists",
                    }
                }
            },
        }
    },
)
async def create_star(
    star_data: StarCreateUpdateRequestSchema,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_star = await db.scalar(
        select(StarModel).where(StarModel.name == star_data.name)
    )
    if db_star:
        raise HTTPException(
            status_code=409, detail="Star with this name already exists"
        )

    new_star = StarModel(name=star_data.name)
    db.add(new_star)
    await db.commit()
    return StarResponseSchema.model_validate(new_star)


@router.patch(
    "/stars/{star_id}/",
    summary="Update a star",
    description="Update a star by its ID. Only available to moderators and admins.",
    response_model=StarResponseSchema,
    status_code=200,
    responses={
        409: {
            "description": "Conflict - Star with this name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Star with this name already exists",
                    }
                }
            },
        },
        404: {
            "description": "Star with this id does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Star with this id does not exist",
                    }
                }
            },
        },
    },
)
async def update_star(
    star_id: int,
    star_data: StarCreateUpdateRequestSchema,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_star = await db.scalar(select(StarModel).where(StarModel.id == star_id))
    if not db_star:
        raise HTTPException(
            status_code=404, detail="Star with this id does not exist"
        )

    existing_star = await db.scalar(
        select(StarModel).where(
            StarModel.name == star_data.name, StarModel.id != star_id
        )
    )

    if existing_star:
        raise HTTPException(
            status_code=409, detail="Star with this name already exists"
        )

    db_star.name = star_data.name
    await db.commit()
    return StarResponseSchema.model_validate(db_star)


@router.delete(
    "/stars/{star_id}/",
    summary="Delete a star",
    description="Delete a star by its ID. Only available to moderators and admins.",
    status_code=204,
    responses={
        404: {
            "description": "Star with this id does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Star with this id does not exist",
                    }
                }
            },
        }
    },
)
async def delete_star(
    star_id: int,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_star = await db.scalar(select(StarModel).where(StarModel.id == star_id))
    if not db_star:
        raise HTTPException(
            status_code=404, detail="Star with this id does not exist"
        )
    await db.delete(db_star)
    await db.commit()
    return


@router.post(
    "/",
    summary="Create a new movie",
    description="Create a new movie. Only available to moderators and admins.",
    response_model=MovieDetailResponseSchema,
    status_code=201,
    responses={
        409: {
            "description": "Conflict - Movie with this name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with this name already exists",
                    }
                }
            },
        },
        404: {
            "description": "certification with this id does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Certification with this id does not exist",
                    }
                }
            },
        },
    },
)
async def create_movie(
    movie_data: MovieCreateRequestSchema,
    current_user: UserModel = Depends(require_moderator),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_movie = await db.scalar(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.year == movie_data.year,
            MovieModel.time == movie_data.time,
        )
    )
    if db_movie:
        raise HTTPException(
            status_code=409, detail="Movie with this name already exists"
        )

    certification = await db.scalar(
        select(CertificationModel).where(
            CertificationModel.id == movie_data.certification_id,
        )
    )
    if not certification:
        raise HTTPException(
            status_code=404, detail="Certification with this id does not exist"
        )

    try:
        genres = []
        for genre in movie_data.genres:
            existing_genre = await db.scalar(
                select(GenreModel).where(
                    GenreModel.name == genre,
                )
            )
            if existing_genre:
                genres.append(existing_genre)

            else:
                new_genre = GenreModel(name=genre)
                db.add(new_genre)
                await db.flush()
                genres.append(new_genre)

        stars = []
        for star in movie_data.stars:
            existing_star = await db.scalar(
                select(StarModel).where(StarModel.name == star)
            )
            if existing_star:
                stars.append(existing_star)

            else:
                new_star = StarModel(name=star)
                db.add(new_star)
                await db.flush()
                stars.append(new_star)

        directors = []
        for director in movie_data.directors:
            existing_director = await db.scalar(
                select(DirectorModel).where(DirectorModel.name == director)
            )
            if existing_director:
                directors.append(existing_director)

            else:
                new_director = DirectorModel(name=director)
                db.add(new_director)
                await db.flush()
                directors.append(new_director)

        movie = MovieModel(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=certification,
            genres=genres,
            directors=directors,
            stars=stars,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(
            movie, ["genres", "stars", "directors", "certification"]
        )

        return MovieDetailResponseSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")
