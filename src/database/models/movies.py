import decimal
from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Text,
    ForeignKey,
    Numeric,
    Uuid,
    UniqueConstraint,
    Table,
    Column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base

movie_genres_model = Table(
    "movie_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.py.id"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "genre_id", ForeignKey("genres.id"), primary_key=True, nullable=False
    ),
)

movie_directors_model = Table(
    "movie_directors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.py.id"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "director_id",
        ForeignKey("directors.id"),
        primary_key=True,
        nullable=False,
    ),
)

movie_stars_model = Table(
    "movie_stars",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.py.id"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "star_id", ForeignKey("stars.id"), primary_key=True, nullable=False
    ),
)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    movies: Mapped[list[MovieModel]] = relationship(
        secondary=movie_genres_model, back_populates="genres"
    )


class StarModel(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    movies: Mapped[list[MovieModel]] = relationship(
        secondary=movie_stars_model, back_populates="stars"
    )


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    movies: Mapped[list[MovieModel]] = relationship(
        secondary=movie_directors_model, back_populates="directors"
    )


class CertificationModel(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    movies: Mapped[list[MovieModel]] = relationship(
        back_populates="certification"
    )


class MovieModel(Base):
    __tablename__ = "movies.py"
    __table_args__ = (
        UniqueConstraint(
            "name", "year", "time", name="uq_movie_name_year_time"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True)
    name: Mapped[str] = mapped_column(String(250))
    year: Mapped[int] = mapped_column(Integer)
    time: Mapped[int] = mapped_column(Integer)
    imdb: Mapped[float] = mapped_column(Float)
    votes: Mapped[int] = mapped_column(Integer)
    meta_score: Mapped[Optional[float]] = mapped_column(Float)
    gross: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id")
    )

    genres: Mapped[list[GenreModel]] = relationship(
        "GenreModel", secondary=movie_genres_model, back_populates="movies.py"
    )
    directors: Mapped[list[DirectorModel]] = relationship(
        "DirectorModel",
        secondary=movie_directors_model,
        back_populates="movies.py",
    )
    stars: Mapped[list[StarModel]] = relationship(
        "StarModel", secondary=movie_stars_model, back_populates="movies.py"
    )
    certification: Mapped[CertificationModel] = relationship(
        "CertificationModel", back_populates="movies.py"
    )
