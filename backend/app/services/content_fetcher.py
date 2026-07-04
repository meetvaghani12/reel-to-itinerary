import logging
import re
from pathlib import Path
from app.utils.validators import detect_platform, extract_video_id, extract_shortcode
from app.core.exceptions import ExtractionError
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def fetch_content(url: str) -> dict:
    platform = detect_platform(url)
    if not platform:
        raise ExtractionError("Unsupported URL. Please provide a YouTube or Instagram link.")

    if platform == "youtube":
        return await _fetch_youtube(url)
    elif platform == "instagram":
        return await _fetch_instagram(url)
    raise ExtractionError("Unsupported platform")


async def _fetch_youtube(url: str) -> dict:
    video_id = extract_video_id(url)
    if not video_id:
        raise ExtractionError("Could not extract video ID from YouTube URL")

    metadata = await _get_youtube_metadata(video_id)
    transcript = await _get_youtube_transcript(video_id)

    return {
        "platform": "youtube",
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "transcript": transcript,
        "tags": metadata.get("tags", []),
        "duration": metadata.get("duration", ""),
    }


async def _get_youtube_metadata(video_id: str) -> dict:
    if not settings.youtube_api_key:
        logger.warning("YouTube API key not set, using fallback metadata")
        return {"title": "", "description": "", "tags": [], "duration": ""}

    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,contentDetails",
                    "id": video_id,
                    "key": settings.youtube_api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return {"title": "", "description": "", "tags": [], "duration": ""}
            snippet = items[0].get("snippet", {})
            content = items[0].get("contentDetails", {})
            return {
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "duration": content.get("duration", ""),
            }
    except httpx.HTTPStatusError as e:
        logger.warning(f"YouTube API error {e.response.status_code}: {e.response.text}")
        return {"title": "", "description": "", "tags": [], "duration": ""}


async def _get_youtube_transcript(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        return " ".join(entry.text for entry in transcript.snippets)
    except Exception as e:
        logger.warning(f"Transcript fetch failed for {video_id}: {e}")
        return ""


async def _fetch_instagram(url: str) -> dict:
    """Fetch an Instagram reel's caption/hashtags. Instagram requires auth, so
    we try, in order of reliability:
      1. yt-dlp with an exported cookies.txt file  (works headless / on servers)
      2. instaloader without login                 (sometimes works, gives location)
      3. yt-dlp reading cookies live from a browser (local dev machine only)
    """
    shortcode = extract_shortcode(url)
    if not shortcode:
        raise ExtractionError("Could not extract shortcode from Instagram URL")

    # 1. Preferred: exported cookies.txt (portable, no live browser needed).
    cookies_path = _instagram_cookies_path()
    if cookies_path:
        try:
            logger.info("Fetching Instagram via cookies.txt")
            return _ytdlp_extract(url, {"cookiefile": str(cookies_path)})
        except Exception as e:
            logger.warning(f"yt-dlp with cookies.txt failed: {e}")

    # 2. instaloader (no login) — also surfaces a location tag when present.
    try:
        return _fetch_instagram_instaloader(shortcode)
    except Exception as e:
        logger.warning(f"Instaloader failed for {shortcode}: {e}")

    # 3. Fallback: cookies read live from a locally logged-in browser.
    return _fetch_instagram_browser_cookies(url)


def _instagram_cookies_path():
    """Return the configured cookies.txt Path if it exists, else None."""
    raw = settings.instagram_cookies_file
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.exists():
        return path
    logger.warning(f"INSTAGRAM_COOKIES_FILE set but file not found: {path}")
    return None


def _ytdlp_extract(url: str, extra_opts: dict) -> dict:
    """Run yt-dlp with the given auth options and normalise the result."""
    import yt_dlp

    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True, **extra_opts}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise ExtractionError("yt-dlp returned no metadata for this reel")

    description = info.get("description", "") or ""
    hashtags = [w[1:] for w in description.split() if w.startswith("#")]
    return {
        "platform": "instagram",
        "title": info.get("title") or description[:100],
        "description": description,
        "transcript": "",
        "tags": hashtags or info.get("tags", []),
    }


def _fetch_instagram_instaloader(shortcode: str) -> dict:
    import instaloader

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
    )
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    caption = post.caption or ""
    hashtags = [word[1:] for word in caption.split() if word.startswith("#")]

    return {
        "platform": "instagram",
        "title": caption[:100],
        "description": caption,
        "transcript": "",
        "tags": hashtags,
        "location_hints": {
            "name": post.location.name if post.location else "",
            "lat": post.location.lat if post.location else None,
            "lng": post.location.lng if post.location else None,
        },
    }


def _fetch_instagram_browser_cookies(url: str) -> dict:
    browsers_to_try = [settings.instagram_browser, "safari", "chrome", "firefox", "edge"]
    seen, browsers_unique = set(), []
    for b in browsers_to_try:
        if b not in seen:
            seen.add(b)
            browsers_unique.append(b)

    last_error = None
    for browser in browsers_unique:
        try:
            return _ytdlp_extract(url, {"cookiesfrombrowser": (browser,)})
        except Exception as e:
            last_error = e
            logger.warning(f"yt-dlp with {browser} failed: {e}")
            continue

    logger.error(f"All Instagram extraction methods failed. Last error: {last_error}")
    raise ExtractionError(
        "Failed to fetch Instagram content. Instagram requires login. Set "
        "INSTAGRAM_COOKIES_FILE to an exported cookies.txt (see README), or log "
        "into Instagram in your browser (Safari/Chrome/Firefox)."
    )
