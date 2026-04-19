"""URL fetching utilities for web pages and YouTube transcripts."""
import asyncio
import re

import httpx
from bs4 import BeautifulSoup

from utils.logging import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CourseArchitectBot/1.0)"
}


def is_youtube(url: str) -> bool:
    """Return True if the URL points to a YouTube video."""
    return "youtube.com/watch" in url or "youtu.be/" in url


def _extract_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from a watch or short URL."""
    short = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if short:
        return short.group(1)
    watch = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if watch:
        return watch.group(1)
    return None


async def fetch_youtube(url: str) -> str | None:
    """Fetch the transcript of a YouTube video.

    Uses asyncio.to_thread because youtube-transcript-api is synchronous.

    Args:
        url: A youtube.com/watch or youtu.be URL.

    Returns:
        Full transcript as plain text, or None if unavailable.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        logger.warning("Could not extract video ID from YouTube URL: %s", url)
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # v0.6+ uses an instance method; FetchedTranscript is iterable with .text on each snippet
        api = YouTubeTranscriptApi()
        transcript = await asyncio.to_thread(api.fetch, video_id)
        return " ".join(s.text for s in transcript)
    except Exception:
        logger.warning("Failed to fetch YouTube transcript for %s", url, exc_info=True)
        return None


async def fetch_url(url: str) -> str | None:
    """Fetch and parse the main text content of a web page.

    Strips navigation, footer, script, and style elements and extracts
    text from headings, paragraphs, and list items only.

    Args:
        url: Any HTTP/HTTPS URL.

    Returns:
        Extracted plain text, or None on any failure.
    """
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()
        tags = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
        text = "\n".join(t.get_text(separator=" ", strip=True) for t in tags if t.get_text(strip=True))
        return text or None
    except Exception:
        logger.warning("Failed to fetch URL: %s", url, exc_info=True)
        return None
