"""Auto-leave timer & reconnect logic — runs as background task."""
import asyncio
import time
from core.client import bot, call_py
from core.cache import get_now_playing, get_session, clear_now_playing, clear_session, get_queue
from core.database import get_group_settings, get_all_chat_ids
from core.logger import logger


_last_activity: dict[int, float] = {}


def record_activity(chat_id: int):
    _last_activity[chat_id] = time.time()


async def auto_leave_loop():
    """Checks all active chats for inactivity and leaves if needed."""
    while True:
        await asyncio.sleep(30)
        try:
            chat_ids = list(_last_activity.keys())
            for chat_id in chat_ids:
                np = await get_now_playing(chat_id)
                if np:
                    _last_activity[chat_id] = time.time()
                    continue
                settings = await get_group_settings(chat_id)
                delay = settings.get("auto_leave_delay", 300)
                if delay == 0:
                    continue
                idle = time.time() - _last_activity.get(chat_id, time.time())
                if idle >= delay:
                    try:
                        await call_py.leave_group_call(chat_id)
                    except Exception:
                        pass
                    await clear_now_playing(chat_id)
                    await clear_session(chat_id)
                    _last_activity.pop(chat_id, None)
                    try:
                        await bot.send_message(
                            chat_id,
                            f"🔇 Left voice chat due to **{delay}s** of inactivity."
                        )
                    except Exception:
                        pass
                    logger.info(f"Auto-left VC in {chat_id} after {idle:.0f}s idle.")
        except Exception as e:
            logger.error(f"auto_leave_loop error: {e}")


async def scheduled_play_loop():
    """Checks scheduled playback tasks."""
    while True:
        await asyncio.sleep(20)
        try:
            from core.database import get_pending_scheduled, mark_scheduled_done
            from helpers.downloader import search_youtube
            from core.cache import add_to_queue
            from plugins.play import _stream_track

            tasks = await get_pending_scheduled()
            for task in tasks:
                chat_id = task["chat_id"]
                query = task["query"]
                results = await search_youtube(query, 1)
                if results:
                    track = results[0]
                    track["requester_id"] = task["user_id"]
                    track["requester_name"] = "Scheduler"
                    np = await get_now_playing(chat_id)
                    session = await get_session(chat_id)
                    if np is None:
                        await _stream_track(chat_id, track, session)
                    else:
                        await add_to_queue(chat_id, track)
                        await bot.send_message(chat_id, f"📅 Scheduled track added: **{track['title']}**")
                await mark_scheduled_done(task["_id"])
        except Exception as e:
            logger.error(f"scheduled_play_loop error: {e}")
