from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Reel-to-Itinerary"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "sqlite+aiosqlite:///./trips.db"
    redis_url: str = "redis://localhost:6379/0"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
