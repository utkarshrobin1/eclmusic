import asyncio
import os
import subprocess
import tempfile
from core.logger import logger

EQ_PRESETS = {
    "flat":      [0] * 10,
    "bass":      [8, 6, 4, 2, 0, 0, 0, 0, 0, 0],
    "treble":    [0, 0, 0, 0, 0, 2, 4, 6, 7, 8],
    "pop":       [2, 3, 4, 2, 0, -1, 2, 3, 4, 3],
    "rock":      [4, 3, 2, 0, -1, 2, 3, 4, 3, 2],
    "jazz":      [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
    "classical": [0, 0, 0, 0, 0, 0, -1, -2, -3, -4],
    "hiphop":    [5, 4, 3, 1, -1, 0, 2, 2, 3, 4],
    "lofi":      [3, 2, 1, 0, -1, -2, -1, 0, 1, 2],
    "vocal":     [-2, -1, 0, 2, 3, 3, 2, 0, -1, -2],
}

EQ_FREQS = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]


def build_eq_filter(gains: list[float]) -> str:
    parts = []
    for freq, gain in zip(EQ_FREQS, gains):
        parts.append(f"equalizer=f={freq}:width_type=o:width=2:g={gain}")
    return ",".join(parts)


def build_audio_filter(effects: dict) -> str:
    filters = []

    # EQ preset or custom bands
    eq_preset = effects.get("eq_preset", "flat")
    eq_custom = effects.get("eq_custom")
    gains = eq_custom if eq_custom else EQ_PRESETS.get(eq_preset, EQ_PRESETS["flat"])
    eq_filter = build_eq_filter(gains)
    filters.append(eq_filter)

    # Bass boost
    bass_level = effects.get("bass_boost", 0)
    if bass_level:
        intensity = bass_level * 4
        filters.append(f"equalizer=f=60:width_type=o:width=2:g={intensity}")

    # Reverb / echo
    if effects.get("reverb"):
        filters.append("aecho=0.8:0.9:40|50:0.4|0.3")

    # Nightcore
    if effects.get("nightcore"):
        filters.append("atempo=1.25,asetrate=48000*1.25,aresample=48000")
    elif effects.get("daycore"):
        filters.append("atempo=0.8,asetrate=48000*0.8,aresample=48000")

    # Playback speed (independent of nightcore)
    speed = effects.get("speed")
    if speed and not effects.get("nightcore") and not effects.get("daycore"):
        if 0.5 <= speed <= 2.0 and speed != 1.0:
            filters.append(f"atempo={speed}")

    # Pitch shift (semitones)
    semitones = effects.get("pitch", 0)
    if semitones:
        ratio = 2 ** (semitones / 12)
        filters.append(f"asetrate=48000*{ratio},aresample=48000")

    # Karaoke (vocal remove)
    if effects.get("karaoke"):
        filters.append("pan=stereo|c0=c0-c1|c1=c1-c0")

    # 3D / Spatial audio
    if effects.get("spatial"):
        filters.append("extrastereo=m=2.5")

    # Volume
    volume = effects.get("volume", 100)
    if volume != 100:
        filters.append(f"volume={volume / 100}")

    # Normalizer
    if effects.get("normalize"):
        filters.append("dynaudnorm")

    # Mute
    if effects.get("muted"):
        filters.append("volume=0")

    return ",".join(filters)


async def apply_effects(input_path: str, effects: dict) -> str:
    out_path = input_path + "_fx.raw"
    af = build_audio_filter(effects)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", af,
        "-f", "s16le",
        "-ar", "48000",
        "-ac", "2",
        out_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode == 0 and os.path.exists(out_path):
            return out_path
    except Exception as e:
        logger.error(f"FFmpeg effects error: {e}")
    return input_path


async def convert_to_raw(input_path: str) -> str:
    out_path = input_path + ".raw"
    if os.path.exists(out_path):
        return out_path
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-f", "s16le",
        "-ar", "48000",
        "-ac", "2",
        out_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return out_path if os.path.exists(out_path) else input_path


def format_duration(seconds: int) -> str:
    if not seconds:
        return "LIVE"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_progress_bar(elapsed: int, total: int, length: int = 12) -> str:
    if not total:
        return "📻 LIVE"
    filled = int((elapsed / total) * length) if total else 0
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {format_duration(elapsed)} / {format_duration(total)}"
