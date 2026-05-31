"""Elite Musico — Main entry point."""
import asyncio
import importlib
import traceback

from core.logger import logger
from config import BOT_NAME

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


async def main():
    logger.info(f"{'='*50}")
    logger.info(f" {BOT_NAME} Starting Up")
    logger.info(f"{'='*50}")

    from core.client import bot, start_clients
    from core.database import connect_db
    from core.cache import connect_redis

    await connect_db()
    await connect_redis()
    await start_clients()

    for plugin in PLUGINS:
        try:
            importlib.import_module(plugin)
            logger.info(f"Loaded: {plugin}")
        except Exception as e:
            logger.error(f"Failed to load {plugin}: {e}")
            logger.error(traceback.format_exc())
            raise

    try:
        from plugins.autoleave import auto_leave_loop, scheduled_play_loop
        asyncio.create_task(auto_leave_loop())
        asyncio.create_task(scheduled_play_loop())
        logger.info("Background tasks started.")
    except Exception as e:
        logger.error(f"Background task error: {e}")
        logger.error(traceback.format_exc())

    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username} ({me.id})")
    logger.info(f"{BOT_NAME} is ready! Entering keep-alive loop.")

    # Keep alive
    count = 0
    while True:
        await asyncio.sleep(60)
        count += 1
        logger.info(f"[Heartbeat] Bot alive — {count} min uptime")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"FATAL: {e}")
        logger.error(traceback.format_exc())
