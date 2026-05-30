import os

# Load .env only if it exists (local dev). On Railway, vars are injected automatically.
try:
    from dotenv import load_dotenv
    if os.path.exists(".env"):
        load_dotenv()
except ImportError:
    pass

# ─── Telegram Credentials ───────────────────────────────────────────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
STRING_SESSION = os.getenv("STRING_SESSION", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ─── Database ────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ─── Bot Settings ────────────────────────────────────────────────────────────
BOT_NAME = "Elite Musico"
BOT_USERNAME = os.getenv("BOT_USERNAME", "EliteMusicoBot")
COMMAND_PREFIXES = ["/", "!"]
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "50"))
AUTO_LEAVE_DELAY = int(os.getenv("AUTO_LEAVE_DELAY", "300"))
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/em_cache")
MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", "512"))

# ─── Audio Defaults ──────────────────────────────────────────────────────────
DEFAULT_VOLUME = int(os.getenv("DEFAULT_VOLUME", "100"))
MAX_VOLUME = 200
MIN_VOLUME = 1

# ─── Vote Skip ───────────────────────────────────────────────────────────────
VOTE_SKIP_PERCENT = int(os.getenv("VOTE_SKIP_PERCENT", "51"))

# ─── APIs (optional) ─────────────────────────────────────────────────────────
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
ACRCLOUD_HOST = os.getenv("ACRCLOUD_HOST", "")
ACRCLOUD_KEY = os.getenv("ACRCLOUD_KEY", "")
ACRCLOUD_SECRET = os.getenv("ACRCLOUD_SECRET", "")

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─── Thumbnail ───────────────────────────────────────────────────────────────
THUMB_THEMES = ["dark", "neon", "gradient", "minimal", "vibrant"]
DEFAULT_THEME = "neon"

os.makedirs(CACHE_DIR, exist_ok=True)
