import decimal
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from database.models.interactions import ReactionTypeEnum, NotificationTypeEnum


class NamedEntityRequestSchema(BaseModel):
    """Base schema for creating or updating genres and stars:
    only a name (max 100 characters)."""

    name: str = Field(max_length=100)


class NamedEntityResponseSchema(BaseModel):
    """Base schema for genres, stars, directors and certifications:
    an id and a name."""

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
    """
    Data for adding a movie to the catalog.

    Genres, directors and stars are passed by name, not by id. `price` is
    optional: a movie without a price cannot be purchased.
    """

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
    """
    One page of the movie catalog.

    `prev_page` and `next_page` are ready-to-use links and are `null` on the
    first and last page. The same pagination fields are used by the comment,
    notification and order lists.
    """

    movies: List[MovieListItemResponseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)


class MovieDetailResponseSchema(BaseModel):
    """
    Full information about a movie.

    `average_rating` is `null` until someone rates the movie.
    `likes_count` and `dislikes_count` count the reactions to the movie.
    """

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
    likes_count: int = 0
    dislikes_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class MovieUpdateRequestSchema(BaseModel):
    """Partial update of a movie. All fields are optional."""

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
    """A rating from 1 to 10."""

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


class CommentReplyResponseSchema(BaseModel):
    id: int
    movie_id: int
    user_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    parent_id: int
    likes_count: int = 0
    dislikes_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CommentRequestSchema(BaseModel):
    """
    Text of a new comment (1 to 1000 characters).

    Set `parent_id` to reply to another comment. Replies are allowed only
    one level deep: you cannot reply to a reply.
    """

    content: str = Field(min_length=1, max_length=1000)
    parent_id: int | None = None


class CommentResponseSchema(BaseModel):
    """
    A comment with its replies and reaction counts.

    `parent_id` is `null` for a top-level comment. `replies` contains the
    direct replies only.
    """

    id: int
    movie_id: int
    user_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    parent_id: int | None = None
    replies: list[CommentReplyResponseSchema] = []
    likes_count: int = 0
    dislikes_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CommentListResponseSchema(BaseModel):
    comments: List[CommentResponseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)


class CommentReactionRequestSchema(BaseModel):
    reaction_type: ReactionTypeEnum


class CommentReactionResponseSchema(BaseModel):
    id: int
    comment_id: int
    reaction_type: ReactionTypeEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationResponseSchema(BaseModel):
    id: int
    notification_type: NotificationTypeEnum
    comment_id: int
    sender_id: int
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponseSchema(BaseModel):
    notifications: List[NotificationResponseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)
