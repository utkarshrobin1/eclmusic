import asyncio
import io
import os
import textwrap
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from config import CACHE_DIR
from core.logger import logger

THUMB_DIR = os.path.join(CACHE_DIR, "thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)

THEMES = {
    "neon": {
        "bg": (6, 8, 16),
        "bar_bg": (30, 42, 58),
        "bar_fill": (0, 212, 255),
        "title_color": (232, 237, 245),
        "sub_color": (90, 106, 126),
        "accent": (0, 212, 255),
        "overlay": (0, 0, 0, 160),
    },
    "dark": {
        "bg": (15, 15, 15),
        "bar_bg": (40, 40, 40),
        "bar_fill": (255, 255, 255),
        "title_color": (255, 255, 255),
        "sub_color": (160, 160, 160),
        "accent": (255, 255, 255),
        "overlay": (0, 0, 0, 180),
    },
    "gradient": {
        "bg": (20, 10, 50),
        "bar_bg": (60, 30, 90),
        "bar_fill": (123, 47, 255),
        "title_color": (255, 255, 255),
        "sub_color": (180, 130, 255),
        "accent": (123, 47, 255),
        "overlay": (10, 5, 30, 160),
    },
    "minimal": {
        "bg": (245, 245, 245),
        "bar_bg": (210, 210, 210),
        "bar_fill": (50, 50, 50),
        "title_color": (30, 30, 30),
        "sub_color": (120, 120, 120),
        "accent": (50, 50, 50),
        "overlay": (245, 245, 245, 140),
    },
    "vibrant": {
        "bg": (255, 30, 80),
        "bar_bg": (180, 10, 50),
        "bar_fill": (255, 255, 0),
        "title_color": (255, 255, 255),
        "sub_color": (255, 200, 200),
        "accent": (255, 255, 0),
        "overlay": (255, 30, 80, 140),
    },
}


def _wrap_text(text: str, max_chars: int) -> str:
    lines = textwrap.wrap(text, max_chars)
    return "\n".join(lines[:2])


async def fetch_thumbnail(url: str) -> bytes | None:
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    return await r.read()
    except Exception as e:
        logger.debug(f"Thumb fetch error: {e}")
    return None


async def generate_now_playing_card(
    track: dict,
    elapsed: int = 0,
    theme_name: str = "neon",
    requester: str = "",
) -> str:
    loop = asyncio.get_event_loop()
    out_path = os.path.join(THUMB_DIR, f"np_{track.get('id','x')}.jpg")

    thumb_bytes = await fetch_thumbnail(track.get("thumb", ""))

    def _render():
        if not PIL_AVAILABLE:
            return None

        theme = THEMES.get(theme_name, THEMES["neon"])
        W, H = 800, 300

        img = Image.new("RGB", (W, H), theme["bg"])
        draw = ImageDraw.Draw(img, "RGBA")

        # Thumbnail panel
        thumb_img = None
        if thumb_bytes:
            try:
                thumb_img = Image.open(io.BytesIO(thumb_bytes)).convert("RGB")
                thumb_img = thumb_img.resize((300, H))
                img.paste(thumb_img, (0, 0))
                overlay = Image.new("RGBA", (300, H), theme["overlay"])
                img.paste(overlay, (0, 0), overlay)
            except Exception:
                pass

        # Right panel
        px = 320
        py = 30

        # Load font (fallback to default)
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        except Exception:
            font_title = font_sub = font_small = ImageFont.load_default()

        # Title
        title = _wrap_text(track.get("title", "Unknown"), 32)
        draw.text((px, py), title, font=font_title, fill=theme["title_color"])
        py += 60

        # Uploader
        draw.text((px, py), track.get("uploader", ""), font=font_sub, fill=theme["sub_color"])
        py += 30

        # Duration / progress bar
        total = track.get("duration", 0)
        from helpers.ffmpeg import format_duration, build_progress_bar
        progress_text = build_progress_bar(elapsed, total)
        draw.text((px, py), progress_text, font=font_small, fill=theme["sub_color"])
        py += 22

        # Visual bar
        bar_x, bar_y = px, py
        bar_w = W - px - 20
        bar_h = 8
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=4, fill=theme["bar_bg"])
        filled_w = int((elapsed / total) * bar_w) if total else 0
        if filled_w:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + filled_w, bar_y + bar_h], radius=4, fill=theme["bar_fill"])
        py += 20

        # Requester
        if requester:
            draw.text((px, py), f"Requested by {requester}", font=font_small, fill=theme["sub_color"])
            py += 20

        # Bot name watermark
        draw.text((W - 140, H - 25), "🎵 Elite Musico", font=font_small, fill=theme["accent"])

        img.save(out_path, "JPEG", quality=92)
        return out_path

    result = await loop.run_in_executor(None, _render)
    return result or ""
