import asyncio
import os
import re
from pathlib import Path
import yt_dlp
from config import CACHE_DIR, MAX_CACHE_SIZE_MB
from core.logger import logger

_COOKIES_FILE = "cookies.txt"
_COOKIES = _COOKIES_FILE if os.path.exists(_COOKIES_FILE) else None

_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "socket_timeout": 30,
    "retries": 5,
    "http_headers": _COMMON_HEADERS,
    **({"cookiefile": _COOKIES} if _COOKIES else {}),
}

YTDLP_OPTS_AUDIO = {
    **_BASE_OPTS,
    "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "outtmpl": f"{CACHE_DIR}/%(id)s.%(ext)s",
    "noplaylist": True,
    "extractor_retries": 5,
    "fragment_retries": 5,
    "postprocessors": [],
}

YTDLP_SEARCH_OPTS = {
    **_BASE_OPTS,
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


def _parse_entry(e: dict) -> dict:
    vid_id = e.get("id", "")
    return {
        "id": vid_id,
        "title": e.get("title", "Unknown"),
        "duration": e.get("duration", 0),
        "views": e.get("view_count", 0),
        "uploader": e.get("uploader") or e.get("channel", "Unknown"),
        "url": f"https://www.youtube.com/watch?v={vid_id}",
        "thumb": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
        "release_date": e.get("upload_date", ""),
    }


async def search_ytmusicapi(query: str, limit: int = 5) -> list[dict]:
    """Search using ytmusicapi — not rate-limited like yt-dlp search."""
    loop = asyncio.get_event_loop()

    def _search():
        from ytmusicapi import YTMusic
        yt = YTMusic()
        results = yt.search(query, filter="songs", limit=limit)
        tracks = []
        for r in results[:limit]:
            vid_id = r.get("videoId", "")
            if not vid_id:
                continue
            duration_raw = r.get("duration_seconds") or 0
            tracks.append({
                "id": vid_id,
                "title": r.get("title", "Unknown"),
                "duration": duration_raw,
                "views": 0,
                "uploader": r.get("artists", [{}])[0].get("name", "Unknown") if r.get("artists") else "Unknown",
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "thumb": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                "release_date": "",
            })
        return tracks

    try:
        results = await loop.run_in_executor(None, _search)
        if results:
            logger.info(f"ytmusicapi search OK: {len(results)} results")
            return results
    except Exception as e:
        logger.warning(f"ytmusicapi search failed: {e}")

    return []


async def search_youtube(query: str, limit: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()

    # Try ytmusicapi first (no IP blocking)
    results = await search_ytmusicapi(query, limit)
    if results:
        return results

    # Fallback to yt-dlp search
    def _search(prefix):
        opts = {**YTDLP_SEARCH_OPTS, "default_search": f"{prefix}{limit}"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", [])
            return [_parse_entry(e) for e in entries if e.get("id")]

    for prefix in ("ytsearch", "ytmsearch"):
        try:
            results = await loop.run_in_executor(None, _search, prefix)
            if results:
                return results
        except Exception as e:
            logger.warning(f"yt-dlp search [{prefix}] failed: {e}")

    logger.error(f"All search methods failed for: {query}")
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


async def get_stream_url(track: dict) -> str | None:
    """Get direct stream URL without downloading — avoids IP blocks."""
    loop = asyncio.get_event_loop()
    url = track.get("url", "")
    if not url:
        return None

    def _get_url():
        opts = {
            **_BASE_OPTS,
            "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "noplaylist": True,
            "skip_download": True,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" in info:
                info = info["entries"][0]
            # Get the direct audio stream URL
            formats = info.get("formats", [])
            # Prefer audio-only formats
            audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
            if audio_formats:
                best = sorted(audio_formats, key=lambda f: f.get("tbr") or 0, reverse=True)[0]
                return best.get("url", info.get("url", ""))
            return info.get("url", "")

    try:
        stream_url = await loop.run_in_executor(None, _get_url)
        if stream_url:
            logger.info(f"Got stream URL for: {track.get('title')}")
            return stream_url
    except Exception as e:
        logger.error(f"get_stream_url error: {e}")
    return None


async def download_track(track: dict) -> str | None:
    # Check cache first
    cached = _cache_path(track.get("id", ""))
    if cached:
        logger.info(f"Cache hit: {track.get('title')}")
        return cached

    # Try direct stream URL (no download needed)
    stream_url = await get_stream_url(track)
    if stream_url:
        # Store stream URL in track for MediaStream to use directly
        track["stream_url"] = stream_url
        return stream_url

    # Last resort: try full download
    logger.info(f"Falling back to download: {track.get('title')}")
    info = await extract_info(track.get("url", track.get("title", "")), download=True)
    if info and info.get("file_path") and os.path.exists(info["file_path"]):
        return info["file_path"]

    logger.error(f"All download methods failed: {track.get('title')}")
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
            return [_parse_entry(e) for e in info.get("entries", []) if e.get("id")]

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        logger.error(f"extract_playlist error: {e}")
        return []


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
