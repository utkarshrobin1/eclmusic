import asyncio
import os
import re
import hashlib
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
    "postprocessors": [],
    "socket_timeout": 30,
    "retries": 3,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

YTDLP_SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": "in_playlist",
    "skip_download": True,
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

    return await loop.run_in_executor(None, _search)


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
        file_path = cached if cached else info.get("requested_downloads", [{}])[0].get("filepath", "")
        if not file_path and download:
            file_path = os.path.join(CACHE_DIR, f"{video_id}.{info.get('ext','webm')}")

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
            "description": info.get("description", "")[:200],
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

    return await loop.run_in_executor(None, _extract)


async def download_track(track: dict) -> str | None:
    cached = _cache_path(track.get("id", ""))
    if cached:
        return cached
    info = await extract_info(track.get("url", track.get("title", "")), download=True)
    return info.get("file_path") if info else None


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
