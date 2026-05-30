"""Elite Musico — Main entry point."""
import asyncio
import importlib
import signal

from core.client import bot, userbot, call_py, start_clients, stop_clients
from core.database import connect_db, disconnect_db
from core.cache import connect_redis, disconnect_redis
from core.logger import logger
from config import BOT_NAME

# ─── Load all plugins ─────────────────────────────────────────────────────────
PLUGINS = [
    "plugins.start",
    "plugins.play",
    "plugins.queue",
    "plugins.audio",
    "plugins.search",
    "plugins.admin",
    "plugins.vote",
    "plugins.callbacks",
    "plugins.autoleave",
]

for plugin in PLUGINS:
    try:
        importlib.import_module(plugin)
        logger.info(f"Loaded: {plugin}")
    except Exception as e:
        logger.error(f"Failed to load {plugin}: {e}")
        raise


async def main():
    logger.info(f"{'='*50}")
    logger.info(f" {BOT_NAME} Starting Up")
    logger.info(f"{'='*50}")

    await connect_db()
    await connect_redis()
    await start_clients()

    from plugins.autoleave import auto_leave_loop, scheduled_play_loop
    asyncio.create_task(auto_leave_loop())
    asyncio.create_task(scheduled_play_loop())

    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username} ({me.id})")
    logger.info(f"{BOT_NAME} is ready! Press Ctrl+C to stop.")

    stop_event = asyncio.Event()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()

    logger.info("Shutting down...")
    await stop_clients()
    await disconnect_db()
    await disconnect_redis()
    logger.info(f"{BOT_NAME} stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
