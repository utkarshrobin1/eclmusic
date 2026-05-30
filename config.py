import os

# ── Telegram API Credentials ──────────────────────────────────────────────────
# Set these as environment variables (or in a .env file).
# NEVER hardcode real values here.
API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Pyrogram String Session for the user account that joins Voice Chats.
# Generate with: python genrate_season.py
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Command prefix
PREFIX = os.getenv("PREFIX", "/")

# Bot owner Telegram user ID
OWNER_ID = int(os.getenv("OWNER_ID", ""))

# ─────────────────────────────────────────────────────────────────────────────
# Validate required config at import time so the bot fails fast with a clear
# message instead of crashing later with a confusing error.
_missing = [
    name for name, val in [
        ("API_ID", API_ID),
        ("API_HASH", API_HASH),
        ("BOT_TOKEN", BOT_TOKEN),
        ("SESSION_STRING", SESSION_STRING),
        ("OWNER_ID", OWNER_ID),
    ] if not val
]
if _missing:
    raise SystemExit(
        f"❌ Missing required environment variables: {', '.join(_missing)}\n"
        "Set them in your environment or a .env file."
    )
