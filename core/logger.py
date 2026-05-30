import logging
import sys
from config import LOG_LEVEL, BOT_NAME

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("elite_musico.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(BOT_NAME)
