"""
Core playback plugin — /play, /vplay, /radio, /stream, file play,
pause/resume, stop, skip, loop, shuffle, volume, mute/unmute.
"""
import asyncio
import os
import time
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality
from pytgcalls.exceptions import NoActiveGroupCall

from core.client import bot, call_py
from core.cache import (
    get_queue, set_queue, add_to_queue, pop_queue, get_now_playing,
    set_now_playing, clear_now_playing, clear_queue, get_session, update_session,
    clear_session, shuffle_queue,
)
from core.database import (
    add_to_history, get_group_settings, increment_user_requests,
    increment_group_stat, audit_log,
)
from helpers.downloader import extract_info, extract_playlist, spotify_to_youtube, search_youtube
from helpers.ffmpeg import format_duration
from helpers.thumbnail import generate_now_playing_card
from helpers.formatters import format_now_playing
from helpers.decorators import admin_or_dj, not_blacklisted, log_action
from config import DEFAULT_VOLUME, MAX_QUEUE_SIZE, OWNER_ID
from strings import get_string
from core.logger import logger

# ─── NP message tracker ──────────────────────────────────────────────────────
_np_messages: dict[int, int] = {}  # chat_id -> message_id


def _control_buttons(loop_mode: str = "none", volume: int = 100) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮", callback_data="cb_prev"),
            InlineKeyboardButton("⏸", callback_data="cb_pause"),
            InlineKeyboardButton("⏭", callback_data="cb_skip"),
        ],
        [
            InlineKeyboardButton("🔂" if loop_mode == "track" else "🔁" if loop_mode == "queue" else "➡️", callback_data="cb_loop"),
            InlineKeyboardButton("🔀", callback_data="cb_shuffle"),
            InlineKeyboardButton("⏹", callback_data="cb_stop"),
        ],
        [
            InlineKeyboardButton("🔉", callback_data="cb_vol_down"),
            InlineKeyboardButton(f"🔊 {volume}%", callback_data="cb_vol_info"),
            InlineKeyboardButton("🔊+", callback_data="cb_vol_up"),
        ],
        [
            InlineKeyboardButton("❤️ Like", callback_data="cb_like"),
            InlineKeyboardButton("📋 Queue", callback_data="cb_queue"),
            InlineKeyboardButton("ℹ️ Info", callback_data="cb_info"),
        ],
    ])


async def _send_now_playing(chat_id: int, track: dict, session: dict):
    from helpers.thumbnail import generate_now_playing_card
    settings = await get_group_settings(chat_id)
    theme = settings.get("theme", "neon")
    loop_mode = session.get("loop_mode", "none")
    volume = session.get("volume", DEFAULT_VOLUME)
    requester = track.get("requester_name", "")

    caption = format_now_playing(track, 0, loop_mode)
    buttons = _control_buttons(loop_mode, volume)
    thumb_path = await generate_now_playing_card(track, 0, theme, requester)

    try:
        if thumb_path and os.path.exists(thumb_path):
            msg = await bot.send_photo(
                chat_id, thumb_path,
                caption=caption, reply_markup=buttons,
            )
        else:
            msg = await bot.send_message(chat_id, caption, reply_markup=buttons)

        # Pin NP message
        if settings.get("pin_np", True):
            try:
                await bot.pin_chat_message(chat_id, msg.id, disable_notification=True)
            except Exception:
                pass

        old = _np_messages.get(chat_id)
        if old:
            try:
                await bot.unpin_chat_message(chat_id, old)
                await bot.delete_messages(chat_id, old)
            except Exception:
                pass
        _np_messages[chat_id] = msg.id
    except Exception as e:
        logger.error(f"send_np error: {e}")


async def _play_next(chat_id: int):
    session = await get_session(chat_id)
    loop_mode = session.get("loop_mode", "none")
    current = session.get("current")

    if loop_mode == "track" and current:
        track = current
    else:
        track = await pop_queue(chat_id)
        if not track:
            if loop_mode == "queue":
                # Nothing left — stopped
                await clear_now_playing(chat_id)
                await clear_session(chat_id)
                return
            await clear_now_playing(chat_id)
            await clear_session(chat_id)
            return

    await _stream_track(chat_id, track, session)


async def _stream_track(chat_id: int, track: dict, session: dict):
    from helpers.downloader import download_track
    from helpers.ffmpeg import apply_effects, convert_to_raw

    settings = await get_group_settings(chat_id)
    effects = session.get("effects", {})
    effects["volume"] = session.get("volume", DEFAULT_VOLUME)

    file_path = await download_track(track)
    if not file_path:
        await bot.send_message(chat_id, f"❌ Failed to download: **{track.get('title')}**")
        await _play_next(chat_id)
        return

    # Use stream URL directly if available (avoids IP blocks)
    audio_path = track.get("stream_url") or file_path

    has_effects = any(v for k, v in effects.items() if k != "volume" or v != 100)
    if has_effects and not audio_path.startswith("http"):
        audio_path = await apply_effects(file_path, effects)
    elif not audio_path.startswith("http"):
        audio_path = await convert_to_raw(file_path)

    try:
        await call_py.join_group_call(
            chat_id,
            MediaStream(audio_path, audio_quality=AudioQuality.HIGH),
        )
    except Exception:
        try:
            await call_py.change_stream(
                chat_id,
                MediaStream(audio_path, audio_quality=AudioQuality.HIGH),
            )
        except Exception as e:
            logger.error(f"Stream error chat {chat_id}: {e}")
            await bot.send_message(chat_id, f"❌ Stream error: {e}")
            return

    session["current"] = track
    session["start_time"] = time.time()
    await update_session(chat_id, session)
    await set_now_playing(chat_id, track)

    # Record activity for auto-leave tracker
    from plugins.autoleave import record_activity
    record_activity(chat_id)

    # DB logging
    await add_to_history(chat_id, track)
    await increment_group_stat(chat_id, "songs_played")
    await increment_group_stat(chat_id, "total_seconds", track.get("duration", 0))

    await _send_now_playing(chat_id, track, session)


# ─── /play command ────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["play", "p"]) & filters.group)
@not_blacklisted
async def cmd_play(client: Client, msg: Message):
    query = " ".join(msg.command[1:])

    if not query and not msg.reply_to_message:
        await msg.reply("Usage: /play <song name or URL>", quote=True)
        return

    # Handle file reply
    if msg.reply_to_message and (msg.reply_to_message.audio or msg.reply_to_message.voice or msg.reply_to_message.video):
        return await _play_file(client, msg)

    if not query and msg.reply_to_message and msg.reply_to_message.text:
        query = msg.reply_to_message.text.strip()

    if not query:
        await msg.reply("❌ Provide a song name or URL.")
        return

    searching = await msg.reply(f"🔍 Searching for **{query}**...")

    # Spotify?
    track = None
    if "spotify.com/track" in query:
        track = await spotify_to_youtube(query)
        if not track:
            await searching.edit("❌ Could not resolve Spotify track.")
            return
    elif "youtube.com/playlist" in query or "list=" in query:
        await _load_playlist(client, msg, query, searching)
        return
    else:
        results = await search_youtube(query, 1)
        track = results[0] if results else None

    if not track:
        await searching.edit("❌ No results found.")
        return

    uid = msg.from_user.id if msg.from_user else 0
    uname = msg.from_user.first_name if msg.from_user else "Unknown"
    track["requester_id"] = uid
    track["requester_name"] = uname

    queue = await get_queue(msg.chat.id)
    session = await get_session(msg.chat.id)
    np = await get_now_playing(msg.chat.id)

    if np is None and not queue:
        await searching.delete()
        await increment_user_requests(msg.chat.id, uid, uname)
        await _stream_track(msg.chat.id, track, session)
    else:
        if len(queue) >= MAX_QUEUE_SIZE:
            await searching.edit(f"❌ Queue is full ({MAX_QUEUE_SIZE} max).")
            return
        pos = await add_to_queue(msg.chat.id, track)
        await increment_user_requests(msg.chat.id, uid, uname)
        await searching.edit(f"✅ Added to queue [**#{pos}**]: **{track['title']}**")


async def _play_file(client: Client, msg: Message):
    replied = msg.reply_to_message
    media = replied.audio or replied.voice or replied.video
    progress = await msg.reply("⬇️ Downloading file...")
    file_path = await client.download_media(media)
    track = {
        "id": f"file_{media.file_id}",
        "title": getattr(media, "title", None) or f"File {media.file_id[:8]}",
        "duration": getattr(media, "duration", 0),
        "uploader": msg.from_user.first_name if msg.from_user else "User",
        "url": "",
        "file_path": file_path,
        "thumb": "",
        "requester_id": msg.from_user.id if msg.from_user else 0,
        "requester_name": msg.from_user.first_name if msg.from_user else "User",
    }
    session = await get_session(msg.chat.id)
    np = await get_now_playing(msg.chat.id)
    if np is None:
        await progress.delete()
        await _stream_track(msg.chat.id, track, session)
    else:
        pos = await add_to_queue(msg.chat.id, track)
        await progress.edit(f"✅ Added to queue [**#{pos}**]: **{track['title']}**")


async def _load_playlist(client: Client, msg: Message, url: str, progress_msg):
    await progress_msg.edit("⏳ Loading playlist...")
    tracks = await extract_playlist(url, max_tracks=50)
    if not tracks:
        await progress_msg.edit("❌ Could not load playlist.")
        return
    uid = msg.from_user.id if msg.from_user else 0
    uname = msg.from_user.first_name if msg.from_user else "User"
    for t in tracks:
        t["requester_id"] = uid
        t["requester_name"] = uname
    queue = await get_queue(msg.chat.id)
    remaining = MAX_QUEUE_SIZE - len(queue)
    tracks = tracks[:remaining]
    session = await get_session(msg.chat.id)
    np = await get_now_playing(msg.chat.id)
    if np is None and tracks:
        first = tracks.pop(0)
        for t in tracks:
            await add_to_queue(msg.chat.id, t)
        await progress_msg.delete()
        await _stream_track(msg.chat.id, first, session)
    else:
        for t in tracks:
            await add_to_queue(msg.chat.id, t)
        await progress_msg.edit(f"✅ Added **{len(tracks)}** tracks from playlist to queue!")


# ─── /vplay — video mode ──────────────────────────────────────────────────────

@bot.on_message(filters.command(["vplay", "vp"]) & filters.group)
@not_blacklisted
async def cmd_vplay(client: Client, msg: Message):
    query = " ".join(msg.command[1:])
    if not query:
        await msg.reply("Usage: /vplay <song name or URL>")
        return
    searching = await msg.reply(f"🎬 Searching video for **{query}**...")
    results = await search_youtube(query, 1)
    if not results:
        await searching.edit("❌ No results found.")
        return
    track = results[0]
    track["video_mode"] = True
    uid = msg.from_user.id if msg.from_user else 0
    uname = msg.from_user.first_name if msg.from_user else "User"
    track["requester_id"] = uid
    track["requester_name"] = uname
    session = await get_session(msg.chat.id)
    np = await get_now_playing(msg.chat.id)
    if np is None:
        await searching.delete()
        await _stream_track(msg.chat.id, track, session)
    else:
        pos = await add_to_queue(msg.chat.id, track)
        await searching.edit(f"✅ Added video to queue [**#{pos}**]: **{track['title']}**")


# ─── /radio — live radio stream ───────────────────────────────────────────────

@bot.on_message(filters.command(["radio", "stream"]) & filters.group)
@not_blacklisted
async def cmd_radio(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        await msg.reply("Usage: /radio <stream URL>\nSupports Icecast, HLS, MP3 streams.")
        return
    url = args[0]
    track = {
        "id": f"radio_{hash(url)}",
        "title": f"📻 Radio: {url[:40]}",
        "duration": 0,
        "uploader": "Live Radio",
        "url": url,
        "file_path": url,
        "thumb": "",
        "requester_id": msg.from_user.id if msg.from_user else 0,
        "requester_name": msg.from_user.first_name if msg.from_user else "Radio",
        "is_live": True,
    }
    session = await get_session(msg.chat.id)
    await _stream_track(msg.chat.id, track, session)


# ─── Pause / Resume ───────────────────────────────────────────────────────────

@bot.on_message(filters.command(["pause"]) & filters.group)
@admin_or_dj
async def cmd_pause(client: Client, msg: Message):
    try:
        await call_py.pause_stream(msg.chat.id)
        await msg.reply("⏸ Playback paused.")
    except Exception as e:
        await msg.reply(f"❌ {e}")


@bot.on_message(filters.command(["resume"]) & filters.group)
@admin_or_dj
async def cmd_resume(client: Client, msg: Message):
    try:
        await call_py.resume_stream(msg.chat.id)
        await msg.reply("▶️ Playback resumed.")
    except Exception as e:
        await msg.reply(f"❌ {e}")


# ─── Skip ─────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["skip", "s", "next"]) & filters.group)
@admin_or_dj
async def cmd_skip(client: Client, msg: Message):
    try:
        await call_py.leave_group_call(msg.chat.id)
    except Exception:
        pass
    await _play_next(msg.chat.id)


# ─── Stop ─────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["stop", "end"]) & filters.group)
@admin_or_dj
async def cmd_stop(client: Client, msg: Message):
    try:
        await call_py.leave_group_call(msg.chat.id)
    except Exception:
        pass
    await clear_queue(msg.chat.id)
    await clear_now_playing(msg.chat.id)
    await clear_session(msg.chat.id)
    await msg.reply("⏹ Stopped and left voice chat.")


# ─── Loop ─────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["loop", "repeat"]) & filters.group)
@admin_or_dj
async def cmd_loop(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    modes = ["none", "track", "queue"]
    current = session.get("loop_mode", "none")
    next_mode = modes[(modes.index(current) + 1) % len(modes)]
    session["loop_mode"] = next_mode
    await update_session(msg.chat.id, session)
    icons = {"none": "➡️ Loop off", "track": "🔂 Track loop", "queue": "🔁 Queue loop"}
    await msg.reply(icons[next_mode])


# ─── Shuffle ──────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["shuffle"]) & filters.group)
@admin_or_dj
async def cmd_shuffle(client: Client, msg: Message):
    await shuffle_queue(msg.chat.id)
    await msg.reply("🔀 Queue shuffled!")


# ─── Volume ───────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["volume", "vol", "v"]) & filters.group)
@admin_or_dj
async def cmd_volume(client: Client, msg: Message):
    args = msg.command[1:]
    if not args or not args[0].isdigit():
        session = await get_session(msg.chat.id)
        vol = session.get("volume", DEFAULT_VOLUME)
        await msg.reply(f"🔊 Current volume: **{vol}%**\nUsage: /vol <1-200>")
        return
    vol = max(1, min(200, int(args[0])))
    session = await get_session(msg.chat.id)
    session["volume"] = vol
    await update_session(msg.chat.id, session)
    try:
        await call_py.change_volume_call(msg.chat.id, vol)
    except Exception:
        pass
    await msg.reply(f"🔊 Volume set to **{vol}%**")


# ─── Mute / Unmute ────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["mute"]) & filters.group)
@admin_or_dj
async def cmd_mute(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    session.setdefault("effects", {})["muted"] = True
    await update_session(msg.chat.id, session)
    try:
        await call_py.change_volume_call(msg.chat.id, 0)
    except Exception:
        pass
    await msg.reply("🔇 Bot muted.")


@bot.on_message(filters.command(["unmute"]) & filters.group)
@admin_or_dj
async def cmd_unmute(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    session.setdefault("effects", {})["muted"] = False
    await update_session(msg.chat.id, session)
    vol = session.get("volume", DEFAULT_VOLUME)
    try:
        await call_py.change_volume_call(msg.chat.id, vol)
    except Exception:
        pass
    await msg.reply("🔊 Bot unmuted.")


# ─── Now Playing ─────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["np", "current", "playing"]) & filters.group)
async def cmd_np(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is currently playing.")
        return
    session = await get_session(msg.chat.id)
    start = session.get("start_time", time.time())
    elapsed = int(time.time() - start)
    loop_mode = session.get("loop_mode", "none")
    text = format_now_playing(track, elapsed, loop_mode)
    buttons = _control_buttons(loop_mode, session.get("volume", DEFAULT_VOLUME))
    await msg.reply(text, reply_markup=buttons)


# ─── PyTgCalls event — stream ended ──────────────────────────────────────────

@call_py.on_update()
async def on_stream_end(client, update):
    from pytgcalls.types import StreamEnded
    if not isinstance(update, StreamEnded):
        return
    chat_id = update.chat_id
    session = await get_session(chat_id)
    loop_mode = session.get("loop_mode", "none")

    if loop_mode == "track":
        current = session.get("current")
        if current:
            await _stream_track(chat_id, current, session)
            return

    queue = await get_queue(chat_id)
    if queue:
        await _play_next(chat_id)
    elif loop_mode == "queue":
        await _play_next(chat_id)
    else:
        await clear_now_playing(chat_id)
        await clear_session(chat_id)
        try:
            await bot.send_message(chat_id, "✅ Queue finished. Thanks for listening! 🎵")
        except Exception:
            pass
