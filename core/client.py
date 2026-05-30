from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped, AudioParameters
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, BOT_NAME
from core.logger import logger

# ─── Bot Client ──────────────────────────────────────────────────────────────
bot = Client(
    "elite_musico_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ─── Userbot (Assistant) Client ──────────────────────────────────────────────
userbot = Client(
    "elite_musico_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)

# ─── PyTgCalls ───────────────────────────────────────────────────────────────
call_py = PyTgCalls(userbot)


async def start_clients():
    logger.info(f"Starting {BOT_NAME}...")
    await userbot.start()
    logger.info("Assistant client started.")
    await bot.start()
    logger.info("Bot client started.")
    await call_py.start()
    logger.info("PyTgCalls started.")


async def stop_clients():
    await call_py.stop()
    await bot.stop()
    await userbot.stop()
    logger.info(f"{BOT_NAME} stopped.")
