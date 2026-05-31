"""Elite Musico — Main entry point."""
import asyncio
import importlib

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

    # Import clients first
    from core.client import bot, userbot, call_py, start_clients, stop_clients
    from core.database import connect_db, disconnect_db
    from core.cache import connect_redis, disconnect_redis

    # Connect DB and cache
    await connect_db()
    await connect_redis()

    # Start clients BEFORE loading plugins so handlers register on active client
    await start_clients()

    # NOW load plugins after clients are started
    for plugin in PLUGINS:
        try:
            importlib.import_module(plugin)
            logger.info(f"Loaded: {plugin}")
        except Exception as e:
            logger.error(f"Failed to load {plugin}: {e}")
            raise

    # Start background tasks
    from plugins.autoleave import auto_leave_loop, scheduled_play_loop
    asyncio.create_task(auto_leave_loop())
    asyncio.create_task(scheduled_play_loop())

    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username} ({me.id})")
    logger.info(f"{BOT_NAME} is ready!")

    # Keep running forever
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
