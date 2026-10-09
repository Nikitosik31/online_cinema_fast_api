from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column

from database.database import Base


class ReactionTypeEnum(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"


class FavoriteMovieModel(Base):
    __tablename__ = "favorite_movies"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_favorite_movies"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class MovieRatingModel(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_movie_ratings"),
        CheckConstraint(
            "rating >= 1 AND rating <= 10", name="check_rating_range"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    rating: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class MovieReactionModel(Base):
    __tablename__ = "movie_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_movie_reactions"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    reaction_type: Mapped[ReactionTypeEnum] = mapped_column(
        Enum(ReactionTypeEnum)
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
