"""Central inline button callbacks — NP controls, queue nav, like."""
import time
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from core.client import bot, call_py
from core.cache import (
    get_now_playing, get_session, update_session, get_queue,
)
from core.database import like_song, get_group_settings
from helpers.formatters import format_now_playing, format_queue_page
from config import DEFAULT_VOLUME


@bot.on_callback_query(filters.regex("^cb_pause$"))
async def cb_pause(client: Client, cq: CallbackQuery):
    try:
        await call_py.pause_stream(cq.message.chat.id)
        await cq.answer("⏸ Paused")
    except Exception as e:
        await cq.answer(f"❌ {e}", show_alert=True)


@bot.on_callback_query(filters.regex("^cb_resume$"))
async def cb_resume(client: Client, cq: CallbackQuery):
    try:
        await call_py.resume_stream(cq.message.chat.id)
        await cq.answer("▶️ Resumed")
    except Exception as e:
        await cq.answer(f"❌ {e}", show_alert=True)


@bot.on_callback_query(filters.regex("^cb_skip$"))
async def cb_skip(client: Client, cq: CallbackQuery):
    await cq.answer("⏭ Skipping...")
    from plugins.play import _play_next
    try:
        await call_py.leave_group_call(cq.message.chat.id)
    except Exception:
        pass
    await _play_next(cq.message.chat.id)


@bot.on_callback_query(filters.regex("^cb_stop$"))
async def cb_stop(client: Client, cq: CallbackQuery):
    from core.cache import clear_queue, clear_now_playing, clear_session
    try:
        await call_py.leave_group_call(cq.message.chat.id)
    except Exception:
        pass
    await clear_queue(cq.message.chat.id)
    await clear_now_playing(cq.message.chat.id)
    await clear_session(cq.message.chat.id)
    await cq.answer("⏹ Stopped")
    try:
        await cq.message.edit("⏹ Playback stopped.")
    except Exception:
        pass


@bot.on_callback_query(filters.regex("^cb_loop$"))
async def cb_loop(client: Client, cq: CallbackQuery):
    session = await get_session(cq.message.chat.id)
    modes = ["none", "track", "queue"]
    current = session.get("loop_mode", "none")
    next_mode = modes[(modes.index(current) + 1) % len(modes)]
    session["loop_mode"] = next_mode
    await update_session(cq.message.chat.id, session)
    icons = {"none": "➡️ Off", "track": "🔂 Track", "queue": "🔁 Queue"}
    await cq.answer(f"Loop: {icons[next_mode]}")


@bot.on_callback_query(filters.regex("^cb_shuffle$"))
async def cb_shuffle(client: Client, cq: CallbackQuery):
    from core.cache import shuffle_queue
    await shuffle_queue(cq.message.chat.id)
    await cq.answer("🔀 Queue shuffled!")


@bot.on_callback_query(filters.regex("^cb_vol_(up|down|info)$"))
async def cb_volume(client: Client, cq: CallbackQuery):
    action = cq.data.split("cb_vol_")[1]
    session = await get_session(cq.message.chat.id)
    vol = session.get("volume", DEFAULT_VOLUME)
    if action == "up":
        vol = min(200, vol + 10)
    elif action == "down":
        vol = max(1, vol - 10)
    session["volume"] = vol
    await update_session(cq.message.chat.id, session)
    try:
        await call_py.change_volume_call(cq.message.chat.id, vol)
    except Exception:
        pass
    await cq.answer(f"🔊 Volume: {vol}%")


@bot.on_callback_query(filters.regex("^cb_like$"))
async def cb_like(client: Client, cq: CallbackQuery):
    track = await get_now_playing(cq.message.chat.id)
    if not track:
        await cq.answer("❌ Nothing playing.", show_alert=True)
        return
    uid = cq.from_user.id
    await like_song(uid, track)
    await cq.answer(f"❤️ Liked: {track.get('title', '')[:30]}")


@bot.on_callback_query(filters.regex("^cb_queue$"))
async def cb_queue(client: Client, cq: CallbackQuery):
    queue = await get_queue(cq.message.chat.id)
    np = await get_now_playing(cq.message.chat.id)
    text = ""
    if np:
        text = f"🎵 **Now:** {np.get('title', 'Unknown')[:40]}\n\n"
    text += format_queue_page(queue, page=0)
    await cq.answer()
    await cq.message.reply(text)


@bot.on_callback_query(filters.regex("^cb_info$"))
async def cb_info(client: Client, cq: CallbackQuery):
    track = await get_now_playing(cq.message.chat.id)
    if not track:
        await cq.answer("❌ Nothing playing.", show_alert=True)
        return
    from helpers.formatters import format_track_info
    await cq.answer()
    await cq.message.reply(format_track_info(track), disable_web_page_preview=False)


@bot.on_callback_query(filters.regex("^cb_prev$"))
async def cb_prev(client: Client, cq: CallbackQuery):
    await cq.answer("⏮ No previous track support yet.")
