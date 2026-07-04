from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Reel-to-Itinerary"
    app_env: str = "development"
    debug: bool = True

    youtube_api_key: str = ""

    # Preferred Instagram auth: path to a Netscape-format cookies.txt exported
    # from a logged-in Instagram session. Works headless / on servers, unlike
    # reading cookies live from a browser (instagram_browser is the fallback).
    instagram_cookies_file: str = ""
    instagram_browser: str = "safari"

    database_url: str = "sqlite+aiosqlite:///./trips.db"
    redis_url: str = "redis://localhost:6379/0"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
