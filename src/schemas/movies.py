import decimal
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from database.models.interactions import ReactionTypeEnum


class NamedEntityRequestSchema(BaseModel):
    name: str = Field(max_length=100)


class NamedEntityResponseSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class GenreCreateUpdateRequestSchema(NamedEntityRequestSchema):
    pass


class GenreResponseSchema(NamedEntityResponseSchema):
    pass


class StarCreateUpdateRequestSchema(NamedEntityRequestSchema):
    pass


class StarResponseSchema(NamedEntityResponseSchema):
    pass


class DirectorResponseSchema(NamedEntityResponseSchema):
    pass


class CertificationResponseSchema(NamedEntityResponseSchema):
    pass


class MovieCreateRequestSchema(BaseModel):
    name: str = Field(max_length=255)
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None = None
    gross: float | None = None
    description: str
    price: decimal.Decimal | None = None
    certification_id: int
    genres: list[str]
    directors: list[str]
    stars: list[str]


class MovieListItemResponseSchema(BaseModel):
    id: int
    name: str
    year: int
    price: Optional[decimal.Decimal] = None
    imdb: float
    genres: list[GenreResponseSchema]

    model_config = ConfigDict(from_attributes=True)


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemResponseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)


class MovieDetailResponseSchema(BaseModel):
    id: int
    uuid: UUID
    name: str = Field(max_length=255)
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    price: Optional[decimal.Decimal]
    certification: CertificationResponseSchema
    genres: list[GenreResponseSchema]
    directors: list[DirectorResponseSchema]
    stars: list[StarResponseSchema]
    average_rating: float | None = None

    model_config = ConfigDict(from_attributes=True)


class MovieUpdateRequestSchema(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[float] = None
    votes: Optional[int] = None
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: Optional[str] = None
    price: Optional[decimal.Decimal] = None
    certification_id: Optional[int] = None
    genres: Optional[list[str]] = None
    directors: Optional[list[str]] = None
    stars: Optional[list[str]] = None


class GenreWithMovieCountResponseSchema(BaseModel):
    id: int
    name: str
    movie_count: int

    model_config = ConfigDict(from_attributes=True)


class MovieRatingRequestSchema(BaseModel):
    rating: int = Field(ge=1, le=10)


class MovieRatingResponseSchema(BaseModel):
    movie_id: int
    rating: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MovieReactionRequestSchema(BaseModel):
    reaction_type: ReactionTypeEnum


class MovieReactionResponseSchema(BaseModel):
    id: int
    movie_id: int
    reaction_type: ReactionTypeEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
