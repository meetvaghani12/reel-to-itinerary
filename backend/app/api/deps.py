from app.core.config import get_settings

settings = get_settings()


async def get_youtube_client():
    import httpx
    return httpx.AsyncClient(
        base_url="https://www.googleapis.com/youtube/v3",
        params={"key": settings.youtube_api_key},
    )
