from functools import wraps
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from core.database import get_group_settings, audit_log
from config import OWNER_ID
from core.logger import logger


def owner_only(func):
    @wraps(func)
    async def wrapper(client: Client, update, *args, **kwargs):
        uid = update.from_user.id if update.from_user else 0
        if uid != OWNER_ID:
            if isinstance(update, Message):
                await update.reply("❌ Owner only command.")
            return
        return await func(client, update, *args, **kwargs)
    return wrapper


def admin_or_dj(func):
    @wraps(func)
    async def wrapper(client: Client, msg: Message, *args, **kwargs):
        uid = msg.from_user.id if msg.from_user else 0
        if uid == OWNER_ID:
            return await func(client, msg, *args, **kwargs)
        settings = await get_group_settings(msg.chat.id)
        dj_users = settings.get("dj_users", [])
        if uid in dj_users:
            return await func(client, msg, *args, **kwargs)
        member = await client.get_chat_member(msg.chat.id, uid)
        if member.status.name in ("OWNER", "ADMINISTRATOR"):
            return await func(client, msg, *args, **kwargs)
        await msg.reply("❌ You need to be an admin or DJ to use this.")
    return wrapper


def admin_only(func):
    @wraps(func)
    async def wrapper(client: Client, msg: Message, *args, **kwargs):
        uid = msg.from_user.id if msg.from_user else 0
        if uid == OWNER_ID:
            return await func(client, msg, *args, **kwargs)
        member = await client.get_chat_member(msg.chat.id, uid)
        if member.status.name in ("OWNER", "ADMINISTRATOR"):
            return await func(client, msg, *args, **kwargs)
        await msg.reply("❌ Admins only.")
    return wrapper


def not_blacklisted(func):
    @wraps(func)
    async def wrapper(client: Client, msg: Message, *args, **kwargs):
        uid = msg.from_user.id if msg.from_user else 0
        settings = await get_group_settings(msg.chat.id)
        if uid in settings.get("blacklisted_users", []):
            await msg.reply("🚫 You are blacklisted from using this bot in this group.")
            return
        # Check blacklisted words
        text = msg.text or ""
        for word in settings.get("blacklisted_words", []):
            if word.lower() in text.lower():
                await msg.reply("🚫 That song/keyword is blacklisted in this group.")
                return
        return await func(client, msg, *args, **kwargs)
    return wrapper


def log_action(action: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(client: Client, msg: Message, *args, **kwargs):
            result = await func(client, msg, *args, **kwargs)
            uid = msg.from_user.id if msg.from_user else 0
            detail = msg.text or ""
            await audit_log(msg.chat.id, uid, action, detail[:200])
            return result
        return wrapper
    return decorator
