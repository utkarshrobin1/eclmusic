import asyncio
import os
import re
from pathlib import Path
import yt_dlp
from config import CACHE_DIR, MAX_CACHE_SIZE_MB
from core.logger import logger

YTDLP_OPTS_AUDIO = {
    "format": "bestaudio/best",
    "outtmpl": f"{CACHE_DIR}/%(id)s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "socket_timeout": 30,
    "retries": 5,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "extractor_retries": 5,
    "fragment_retries": 5,
    "skip_unavailable_fragments": True,
    "ignoreerrors": False,
    "source_address": "0.0.0.0",
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    # Use piped/invidious as fallback if direct YouTube fails
    "postprocessors": [],
}

YTDLP_SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": "in_playlist",
    "skip_download": True,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    },
}


def _is_url(text: str) -> bool:
    return re.match(r"https?://", text.strip()) is not None


def _cache_path(video_id: str) -> str | None:
    for ext in ("webm", "m4a", "mp3", "opus", "wav", "ogg"):
        path = os.path.join(CACHE_DIR, f"{video_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


def _manage_cache():
    cache = Path(CACHE_DIR)
    files = sorted(cache.iterdir(), key=lambda f: f.stat().st_mtime)
    total_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
    while total_mb > MAX_CACHE_SIZE_MB and files:
        oldest = files.pop(0)
        total_mb -= oldest.stat().st_size / (1024 * 1024)
        oldest.unlink(missing_ok=True)
        logger.debug(f"Cache evicted: {oldest.name}")


async def search_youtube(query: str, limit: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()

    def _search():
        opts = {**YTDLP_SEARCH_OPTS, "default_search": f"ytsearch{limit}"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", [])
            results = []
            for e in entries:
                results.append({
                    "id": e.get("id"),
                    "title": e.get("title", "Unknown"),
                    "duration": e.get("duration", 0),
                    "views": e.get("view_count", 0),
                    "uploader": e.get("uploader", "Unknown"),
                    "url": f"https://www.youtube.com/watch?v={e.get('id')}",
                    "thumb": f"https://i.ytimg.com/vi/{e.get('id')}/hqdefault.jpg",
                    "release_date": e.get("upload_date", ""),
                })
            return results

    try:
        return await loop.run_in_executor(None, _search)
    except Exception as e:
        logger.error(f"search_youtube error: {e}")
        return []


async def extract_info(url_or_query: str, download: bool = True) -> dict | None:
    loop = asyncio.get_event_loop()
    query = url_or_query if _is_url(url_or_query) else f"ytsearch1:{url_or_query}"

    def _extract():
        opts = {**YTDLP_OPTS_AUDIO, "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=download)
            if "entries" in info:
                info = info["entries"][0]
            return info

    try:
        info = await loop.run_in_executor(None, _extract)
        if not info:
            return None

        video_id = info.get("id", "")
        cached = _cache_path(video_id)

        if cached:
            file_path = cached
        elif download:
            # Find downloaded file
            requested = info.get("requested_downloads", [{}])
            file_path = requested[0].get("filepath", "") if requested else ""
            if not file_path:
                file_path = os.path.join(CACHE_DIR, f"{video_id}.{info.get('ext','webm')}")
        else:
            file_path = ""

        _manage_cache()

        return {
            "id": video_id,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "views": info.get("view_count", 0),
            "uploader": info.get("uploader", "Unknown"),
            "url": info.get("webpage_url", url_or_query),
            "stream_url": info.get("url", ""),
            "thumb": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "file_path": file_path,
            "release_date": info.get("upload_date", ""),
            "genre": info.get("genre", ""),
            "description": (info.get("description", "") or "")[:200],
        }
    except Exception as e:
        logger.error(f"extract_info error: {e}")
        return None


async def extract_playlist(url: str, max_tracks: int = 50) -> list[dict]:
    loop = asyncio.get_event_loop()

    def _extract():
        opts = {
            **YTDLP_SEARCH_OPTS,
            "extract_flat": True,
            "noplaylist": False,
            "playlistend": max_tracks,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get("entries", [])
            results = []
            for e in entries:
                results.append({
                    "id": e.get("id"),
                    "title": e.get("title", "Unknown"),
                    "duration": e.get("duration", 0),
                    "url": f"https://www.youtube.com/watch?v={e.get('id')}",
                    "thumb": f"https://i.ytimg.com/vi/{e.get('id')}/hqdefault.jpg",
                    "uploader": e.get("uploader", "Unknown"),
                    "views": e.get("view_count", 0),
                })
            return results

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        logger.error(f"extract_playlist error: {e}")
        return []


async def download_track(track: dict) -> str | None:
    # Check cache first
    cached = _cache_path(track.get("id", ""))
    if cached:
        logger.info(f"Cache hit: {track.get('title')}")
        return cached

    logger.info(f"Downloading: {track.get('title')}")
    info = await extract_info(track.get("url", track.get("title", "")), download=True)
    if info and info.get("file_path") and os.path.exists(info["file_path"]):
        return info["file_path"]

    logger.error(f"Download failed for: {track.get('title')} | url: {track.get('url')}")
    return None


async def spotify_to_youtube(spotify_url: str) -> dict | None:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
        if not SPOTIFY_CLIENT_ID:
            return None
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
        ))
        track_id = re.search(r"track/([A-Za-z0-9]+)", spotify_url)
        if not track_id:
            return None
        meta = sp.track(track_id.group(1))
        name = meta["name"]
        artist = meta["artists"][0]["name"]
        results = await search_youtube(f"{name} {artist}", 1)
        return results[0] if results else None
    except Exception as e:
        logger.error(f"Spotify resolve error: {e}")
        return None
