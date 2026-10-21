from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Enum,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.database import Base


class ReactionTypeEnum(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"


class NotificationTypeEnum(StrEnum):
    COMMENT_REPLY = "comment_reply"
    COMMENT_LIKE = "comment_like"


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
    """
    A user's rating of a movie, from 1 to 10.

    One rating per user and movie: changing it updates the existing row.
    The range is also enforced by the database (`check_rating_range`).
    """

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


class CommentModel(Base):
    """
    A comment on a movie, or a reply to another comment.

    `parent_id` points to the comment being replied to (None for a top-level
    comment). Replies are allowed only one level deep. Deleting a comment
    also deletes its replies, reactions and notifications.
    """

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class CommentReactionModel(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "comment_id", name="unique_comment_reactions"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    reaction_type: Mapped[ReactionTypeEnum] = mapped_column(
        Enum(ReactionTypeEnum)
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    notification_type: Mapped[NotificationTypeEnum] = mapped_column(
        Enum(NotificationTypeEnum)
    )
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
