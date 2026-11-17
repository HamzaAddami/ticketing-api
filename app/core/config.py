from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_ignore_empty=True, extra="ignore"
    )

    app_name: str = "Ticketing API"
    docs_enabled: bool = True
    database_url: str = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"

    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)

    max_seats_per_reservation: int = Field(default=10, gt=0)

    admin_email: EmailStr | None = None
    admin_password: str | None = Field(default=None, min_length=8, max_length=72)

    seed_demo_data: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()