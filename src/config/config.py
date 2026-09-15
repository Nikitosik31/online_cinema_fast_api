from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    postgres_db: str
    postgres_db_port: int
    postgres_user: str
    postgres_password: str
    postgres_host: str

    jwt_secret_key: str

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")

    @property
    def postgres_url(self):
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_db_port}/{self.postgres_db}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
