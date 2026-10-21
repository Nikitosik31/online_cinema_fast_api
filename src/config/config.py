"""Application settings loaded from environment variables and the .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application configuration.

    Values are read from environment variables, falling back to the `.env`
    file in the project root (see `BASE_DIR`). Every field is required: the
    application will not start if one of them is missing.

    Attributes:
        postgres_db (str): PostgreSQL database name.
        postgres_db_port (int): PostgreSQL port.
        postgres_user (str): PostgreSQL user.
        postgres_password (str): PostgreSQL password.
        postgres_host (str): PostgreSQL host.
        jwt_secret_key (str): Secret used to sign JWT access tokens.
        redis_host (str): Redis host (Celery broker and result backend).
        redis_port (int): Redis port.
        smtp_host (str): SMTP server host used to send emails.
        smtp_port (int): SMTP server port.
    """

    postgres_db: str
    postgres_db_port: int
    postgres_user: str
    postgres_password: str
    postgres_host: str

    jwt_secret_key: str

    redis_host: str
    redis_port: int

    smtp_host: str
    smtp_port: int

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")

    @property
    def postgres_url(self) -> str:
        """
        Build the async SQLAlchemy connection URL for PostgreSQL.

        Returns:
            str: URL in the `postgresql+asyncpg://user:password@host:port/db` form.
        """

        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_db_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        """
        Build the Redis connection URL (database 0).

        Returns:
            str: URL in the `redis://host:port/0` form.
        """

        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache()
def get_settings() -> Settings:
    """
    Return the application settings.

    The result is cached, so the `.env` file is read only once. Used as a
    FastAPI dependency and directly by modules that need configuration.

    Returns:
        Settings: The shared settings instance.
    """

    return Settings()
