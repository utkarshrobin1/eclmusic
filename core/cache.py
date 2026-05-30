import json
import redis.asyncio as aioredis
from config import REDIS_URL
from core.logger import logger

_redis: aioredis.Redis = None


async def connect_redis():
    global _redis
    _redis = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await _redis.ping()
    logger.info("Redis connected successfully.")


async def disconnect_redis():
    if _redis:
        await _redis.close()
        logger.info("Redis disconnected.")


def get_redis() -> aioredis.Redis:
    return _redis


# ─── Queue ────────────────────────────────────────────────────────────────────

QUEUE_KEY = "em:queue:{}"
NOW_PLAYING_KEY = "em:np:{}"
VOTE_SKIP_KEY = "em:voteskip:{}"
SESSION_KEY = "em:session:{}"


async def get_queue(chat_id: int) -> list:
    r = get_redis()
    data = await r.get(QUEUE_KEY.format(chat_id))
    return json.loads(data) if data else []


async def set_queue(chat_id: int, queue: list):
    r = get_redis()
    await r.set(QUEUE_KEY.format(chat_id), json.dumps(queue), ex=86400)


async def clear_queue(chat_id: int):
    r = get_redis()
    await r.delete(QUEUE_KEY.format(chat_id))


async def add_to_queue(chat_id: int, track: dict) -> int:
    queue = await get_queue(chat_id)
    queue.append(track)
    await set_queue(chat_id, queue)
    return len(queue)


async def add_next_to_queue(chat_id: int, track: dict):
    queue = await get_queue(chat_id)
    queue.insert(0, track)
    await set_queue(chat_id, queue)


async def pop_queue(chat_id: int) -> dict | None:
    queue = await get_queue(chat_id)
    if not queue:
        return None
    track = queue.pop(0)
    await set_queue(chat_id, queue)
    return track


async def remove_from_queue(chat_id: int, index: int) -> dict | None:
    queue = await get_queue(chat_id)
    if index < 0 or index >= len(queue):
        return None
    track = queue.pop(index)
    await set_queue(chat_id, queue)
    return track


async def shuffle_queue(chat_id: int):
    import random
    queue = await get_queue(chat_id)
    random.shuffle(queue)
    await set_queue(chat_id, queue)


async def reorder_queue(chat_id: int, from_pos: int, to_pos: int) -> bool:
    queue = await get_queue(chat_id)
    if from_pos < 0 or from_pos >= len(queue) or to_pos < 0 or to_pos >= len(queue):
        return False
    track = queue.pop(from_pos)
    queue.insert(to_pos, track)
    await set_queue(chat_id, queue)
    return True


# ─── Now Playing ─────────────────────────────────────────────────────────────

async def set_now_playing(chat_id: int, track: dict):
    r = get_redis()
    await r.set(NOW_PLAYING_KEY.format(chat_id), json.dumps(track), ex=86400)


async def get_now_playing(chat_id: int) -> dict | None:
    r = get_redis()
    data = await r.get(NOW_PLAYING_KEY.format(chat_id))
    return json.loads(data) if data else None


async def clear_now_playing(chat_id: int):
    r = get_redis()
    await r.delete(NOW_PLAYING_KEY.format(chat_id))


# ─── Vote Skip ────────────────────────────────────────────────────────────────

async def add_vote_skip(chat_id: int, user_id: int) -> set:
    r = get_redis()
    key = VOTE_SKIP_KEY.format(chat_id)
    await r.sadd(key, str(user_id))
    await r.expire(key, 120)
    return set(await r.smembers(key))


async def clear_vote_skip(chat_id: int):
    r = get_redis()
    await r.delete(VOTE_SKIP_KEY.format(chat_id))


async def get_vote_skippers(chat_id: int) -> set:
    r = get_redis()
    return set(await r.smembers(VOTE_SKIP_KEY.format(chat_id)))


# ─── Session ─────────────────────────────────────────────────────────────────

async def set_session(chat_id: int, data: dict):
    r = get_redis()
    await r.set(SESSION_KEY.format(chat_id), json.dumps(data), ex=86400)


async def get_session(chat_id: int) -> dict:
    r = get_redis()
    data = await r.get(SESSION_KEY.format(chat_id))
    return json.loads(data) if data else {}


async def update_session(chat_id: int, update: dict):
    session = await get_session(chat_id)
    session.update(update)
    await set_session(chat_id, session)


async def clear_session(chat_id: int):
    r = get_redis()
    await r.delete(SESSION_KEY.format(chat_id))


# ─── Generic Cache ─────────────────────────────────────────────────────────────

async def cache_set(key: str, value, ttl: int = 3600):
    r = get_redis()
    await r.set(f"em:cache:{key}", json.dumps(value), ex=ttl)


async def cache_get(key: str):
    r = get_redis()
    data = await r.get(f"em:cache:{key}")
    return json.loads(data) if data else None


async def cache_delete(key: str):
    r = get_redis()
    await r.delete(f"em:cache:{key}")
