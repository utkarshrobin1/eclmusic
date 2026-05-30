from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI
from core.logger import logger

_client: AsyncIOMotorClient = None
_db = None


async def connect_db():
    global _client, _db
    _client = AsyncIOMotorClient(MONGO_URI)
    _db = _client["elite_musico"]
    await _db.command("ping")
    logger.info("MongoDB connected successfully.")


async def disconnect_db():
    if _client:
        _client.close()
        logger.info("MongoDB disconnected.")


def get_db():
    return _db


# ─── Group Settings ───────────────────────────────────────────────────────────

async def get_group_settings(chat_id: int) -> dict:
    db = get_db()
    doc = await db.group_settings.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "language": "en",
            "volume": 100,
            "loop_mode": "none",
            "command_lock": False,
            "dj_mode": False,
            "dj_users": [],
            "blacklisted_users": [],
            "blacklisted_words": [],
            "auto_leave_delay": 300,
            "vote_skip_percent": 51,
            "theme": "neon",
            "pin_np": True,
            "features": {},
        }
        await db.group_settings.insert_one(doc)
    return doc


async def update_group_settings(chat_id: int, update: dict):
    db = get_db()
    await db.group_settings.update_one(
        {"chat_id": chat_id}, {"$set": update}, upsert=True
    )


# ─── Play History ─────────────────────────────────────────────────────────────

async def add_to_history(chat_id: int, track: dict):
    db = get_db()
    await db.history.update_one(
        {"chat_id": chat_id},
        {
            "$push": {
                "tracks": {
                    "$each": [track],
                    "$slice": -50,
                }
            }
        },
        upsert=True,
    )
    await db.global_plays.update_one(
        {"video_id": track.get("id")},
        {
            "$inc": {"plays": 1},
            "$set": {"title": track.get("title"), "thumb": track.get("thumb")},
        },
        upsert=True,
    )


async def get_history(chat_id: int) -> list:
    db = get_db()
    doc = await db.history.find_one({"chat_id": chat_id})
    return doc.get("tracks", []) if doc else []


# ─── Playlists ────────────────────────────────────────────────────────────────

async def save_playlist(user_id: int, name: str, tracks: list):
    db = get_db()
    await db.playlists.update_one(
        {"user_id": user_id, "name": name},
        {"$set": {"tracks": tracks}},
        upsert=True,
    )


async def get_playlist(user_id: int, name: str) -> list:
    db = get_db()
    doc = await db.playlists.find_one({"user_id": user_id, "name": name})
    return doc.get("tracks", []) if doc else []


async def list_playlists(user_id: int) -> list:
    db = get_db()
    cursor = db.playlists.find({"user_id": user_id}, {"name": 1})
    return [d["name"] async for d in cursor]


# ─── Liked Songs ─────────────────────────────────────────────────────────────

async def like_song(user_id: int, track: dict):
    db = get_db()
    await db.liked_songs.update_one(
        {"user_id": user_id, "video_id": track["id"]},
        {"$set": track},
        upsert=True,
    )


async def unlike_song(user_id: int, video_id: str):
    db = get_db()
    await db.liked_songs.delete_one({"user_id": user_id, "video_id": video_id})


async def get_liked_songs(user_id: int) -> list:
    db = get_db()
    cursor = db.liked_songs.find({"user_id": user_id})
    return [d async for d in cursor]


# ─── Trending ─────────────────────────────────────────────────────────────────

async def get_trending(limit: int = 10) -> list:
    db = get_db()
    cursor = db.global_plays.find().sort("plays", -1).limit(limit)
    return [d async for d in cursor]


# ─── Leaderboard ──────────────────────────────────────────────────────────────

async def increment_user_requests(chat_id: int, user_id: int, username: str):
    db = get_db()
    await db.leaderboard.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"requests": 1}, "$set": {"username": username}},
        upsert=True,
    )


async def get_leaderboard(chat_id: int, limit: int = 10) -> list:
    db = get_db()
    cursor = db.leaderboard.find({"chat_id": chat_id}).sort("requests", -1).limit(limit)
    return [d async for d in cursor]


# ─── Stats ────────────────────────────────────────────────────────────────────

async def increment_group_stat(chat_id: int, field: str, amount: float = 1):
    db = get_db()
    await db.group_stats.update_one(
        {"chat_id": chat_id}, {"$inc": {field: amount}}, upsert=True
    )


async def get_group_stats(chat_id: int) -> dict:
    db = get_db()
    return await db.group_stats.find_one({"chat_id": chat_id}) or {}


# ─── Audit Log ────────────────────────────────────────────────────────────────

async def audit_log(chat_id: int, user_id: int, action: str, detail: str = ""):
    db = get_db()
    from datetime import datetime
    await db.audit_logs.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "action": action,
        "detail": detail,
        "timestamp": datetime.utcnow(),
    })


# ─── Scheduled Playback ───────────────────────────────────────────────────────

async def add_scheduled(chat_id: int, scheduled_time, query: str, user_id: int):
    db = get_db()
    await db.scheduled.insert_one({
        "chat_id": chat_id,
        "scheduled_time": scheduled_time,
        "query": query,
        "user_id": user_id,
        "done": False,
    })


async def get_pending_scheduled():
    from datetime import datetime
    db = get_db()
    now = datetime.utcnow()
    cursor = db.scheduled.find({"scheduled_time": {"$lte": now}, "done": False})
    return [d async for d in cursor]


async def mark_scheduled_done(doc_id):
    db = get_db()
    await db.scheduled.update_one({"_id": doc_id}, {"$set": {"done": True}})


# ─── Song Ratings ─────────────────────────────────────────────────────────────

async def rate_song(video_id: str, user_id: int, rating: int):
    db = get_db()
    await db.song_ratings.update_one(
        {"video_id": video_id, "user_id": user_id},
        {"$set": {"rating": rating}},
        upsert=True,
    )


async def get_song_rating(video_id: str) -> dict:
    db = get_db()
    cursor = db.song_ratings.find({"video_id": video_id})
    total, count = 0, 0
    async for d in cursor:
        total += d["rating"]
        count += 1
    return {"average": round(total / count, 1) if count else 0, "count": count}


# ─── Bot Stats ────────────────────────────────────────────────────────────────

async def get_total_chats() -> int:
    db = get_db()
    return await db.group_settings.count_documents({})


async def get_all_chat_ids() -> list:
    db = get_db()
    cursor = db.group_settings.find({}, {"chat_id": 1})
    return [d["chat_id"] async for d in cursor]
