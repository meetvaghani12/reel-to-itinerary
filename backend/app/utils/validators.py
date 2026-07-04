import re

YOUTUBE_PATTERNS = [
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
]

INSTAGRAM_PATTERNS = [
    r"instagram\.com/[\w.]+/reel/([a-zA-Z0-9_-]+)",
    r"instagram\.com/[\w.]+/p/([a-zA-Z0-9_-]+)",
    r"instagram\.com/reel/([a-zA-Z0-9_-]+)",
    r"instagram\.com/p/([a-zA-Z0-9_-]+)",
    r"instagr\.am/reel/([a-zA-Z0-9_-]+)",
    r"instagr\.am/p/([a-zA-Z0-9_-]+)",
]


def detect_platform(url: str) -> str | None:
    for pattern in YOUTUBE_PATTERNS:
        if re.search(pattern, url):
            return "youtube"
    for pattern in INSTAGRAM_PATTERNS:
        if re.search(pattern, url):
            return "instagram"
    return None


def extract_video_id(url: str) -> str | None:
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_shortcode(url: str) -> str | None:
    for pattern in INSTAGRAM_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
