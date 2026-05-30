"""Admin & Permission System — roles, DJ mode, command lock, blacklist, settings, broadcast, audit."""
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from core.client import bot
from core.database import (
    get_group_settings, update_group_settings, get_group_stats,
    audit_log, get_all_chat_ids, get_total_chats,
    add_scheduled,
)
from helpers.formatters import format_stats
from helpers.decorators import admin_only, owner_only, admin_or_dj
from config import OWNER_ID
from core.logger import logger


# ─── Settings Panel ───────────────────────────────────────────────────────────

def _settings_buttons(settings: dict) -> InlineKeyboardMarkup:
    def _icon(key, default=False): return "✅" if settings.get(key, default) else "❌"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{_icon('pin_np', True)} Pin NP", callback_data="set_pin_np"),
            InlineKeyboardButton(f"{_icon('dj_mode')} DJ Mode", callback_data="set_dj_mode"),
        ],
        [
            InlineKeyboardButton(f"{_icon('command_lock')} Cmd Lock", callback_data="set_cmd_lock"),
            InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
        ],
        [
            InlineKeyboardButton("⏰ Auto-Leave", callback_data="set_autoleave"),
            InlineKeyboardButton("🗳 Vote %", callback_data="set_votepcnt"),
        ],
        [
            InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
        ],
    ])


@bot.on_message(filters.command(["settings", "config"]) & filters.group)
@admin_only
async def cmd_settings(client: Client, msg: Message):
    settings = await get_group_settings(msg.chat.id)
    text = (
        f"⚙️ **Group Settings**\n\n"
        f"🌐 Language: `{settings.get('language', 'en')}`\n"
        f"🔊 Volume: `{settings.get('volume', 100)}%`\n"
        f"⏰ Auto-leave: `{settings.get('auto_leave_delay', 300)}s`\n"
        f"🗳 Vote skip: `{settings.get('vote_skip_percent', 51)}%`\n"
        f"🎨 Theme: `{settings.get('theme', 'neon')}`\n"
    )
    await msg.reply(text, reply_markup=_settings_buttons(settings))


@bot.on_callback_query(filters.regex(r"^set_(.+)$"))
async def cb_settings(client, cq):
    action = cq.data.split("set_")[1]
    settings = await get_group_settings(cq.message.chat.id)

    toggle_keys = {"pin_np": True, "dj_mode": False, "cmd_lock": False}
    key_map = {"pin_np": "pin_np", "dj_mode": "dj_mode", "cmd_lock": "command_lock"}

    if action in key_map:
        db_key = key_map[action]
        current = settings.get(db_key, toggle_keys.get(action, False))
        await update_group_settings(cq.message.chat.id, {db_key: not current})
        await cq.answer(f"{'✅' if not current else '❌'} {action.replace('_', ' ').title()}")
        settings = await get_group_settings(cq.message.chat.id)
        await cq.message.edit_reply_markup(_settings_buttons(settings))

    elif action == "lang":
        langs = ["en", "ar", "es", "fr", "de", "hi", "ru", "tr", "pt", "id", "zh", "ja", "ko", "it", "nl"]
        buttons = [
            [InlineKeyboardButton(l.upper(), callback_data=f"lang_{l}") for l in langs[i:i+5]]
            for i in range(0, len(langs), 5)
        ]
        buttons.append([InlineKeyboardButton("« Back", callback_data="lang_back")])
        await cq.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        await cq.answer()

    elif action == "theme":
        themes = ["neon", "dark", "gradient", "minimal", "vibrant"]
        buttons = [[InlineKeyboardButton(t.capitalize(), callback_data=f"theme_{t}") for t in themes]]
        buttons.append([InlineKeyboardButton("« Back", callback_data="theme_back")])
        await cq.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        await cq.answer()

    elif action == "autoleave":
        await cq.answer()
        await cq.message.reply(
            "⏰ Send new auto-leave delay in seconds (e.g. `300` = 5 minutes):",
        )
    elif action == "votepcnt":
        await cq.answer()
        await cq.message.reply("🗳 Send new vote-skip percentage (e.g. `51` for 51%):")


@bot.on_callback_query(filters.regex(r"^lang_(.+)$"))
async def cb_lang(client, cq):
    lang = cq.data.split("lang_")[1]
    if lang == "back":
        settings = await get_group_settings(cq.message.chat.id)
        await cq.message.edit_reply_markup(_settings_buttons(settings))
        await cq.answer()
        return
    await update_group_settings(cq.message.chat.id, {"language": lang})
    await cq.answer(f"🌐 Language set to {lang.upper()}")
    settings = await get_group_settings(cq.message.chat.id)
    await cq.message.edit_reply_markup(_settings_buttons(settings))


@bot.on_callback_query(filters.regex(r"^theme_(.+)$"))
async def cb_theme(client, cq):
    theme = cq.data.split("theme_")[1]
    if theme == "back":
        settings = await get_group_settings(cq.message.chat.id)
        await cq.message.edit_reply_markup(_settings_buttons(settings))
        await cq.answer()
        return
    await update_group_settings(cq.message.chat.id, {"theme": theme})
    await cq.answer(f"🎨 Theme set to {theme.capitalize()}")
    settings = await get_group_settings(cq.message.chat.id)
    await cq.message.edit_reply_markup(_settings_buttons(settings))


# ─── DJ Management ────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["adddj"]) & filters.group)
@admin_only
async def cmd_add_dj(client: Client, msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target:
        await msg.reply("Reply to a user to add them as DJ.")
        return
    settings = await get_group_settings(msg.chat.id)
    dj_users = settings.get("dj_users", [])
    if target.id in dj_users:
        await msg.reply(f"🎧 {target.mention} is already a DJ.")
        return
    dj_users.append(target.id)
    await update_group_settings(msg.chat.id, {"dj_users": dj_users})
    await msg.reply(f"🎧 {target.mention} is now a DJ!")
    await audit_log(msg.chat.id, msg.from_user.id, "add_dj", str(target.id))


@bot.on_message(filters.command(["removedj", "rmdj"]) & filters.group)
@admin_only
async def cmd_remove_dj(client: Client, msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target:
        await msg.reply("Reply to a user to remove their DJ role.")
        return
    settings = await get_group_settings(msg.chat.id)
    dj_users = settings.get("dj_users", [])
    if target.id not in dj_users:
        await msg.reply(f"❌ {target.mention} is not a DJ.")
        return
    dj_users.remove(target.id)
    await update_group_settings(msg.chat.id, {"dj_users": dj_users})
    await msg.reply(f"🎧 {target.mention} is no longer a DJ.")
    await audit_log(msg.chat.id, msg.from_user.id, "remove_dj", str(target.id))


@bot.on_message(filters.command(["djlist"]) & filters.group)
async def cmd_dj_list(client: Client, msg: Message):
    settings = await get_group_settings(msg.chat.id)
    dj_users = settings.get("dj_users", [])
    if not dj_users:
        await msg.reply("🎧 No DJs assigned.")
        return
    lines = ["🎧 **DJs in this group:**"]
    for uid in dj_users:
        try:
            user = await client.get_users(uid)
            lines.append(f"• {user.mention}")
        except Exception:
            lines.append(f"• `{uid}`")
    await msg.reply("\n".join(lines))


# ─── Blacklist ────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["blacklist", "bl"]) & filters.group)
@admin_only
async def cmd_blacklist_user(client: Client, msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target:
        await msg.reply("Reply to a user to blacklist them.")
        return
    settings = await get_group_settings(msg.chat.id)
    bl = settings.get("blacklisted_users", [])
    if target.id in bl:
        await msg.reply(f"🚫 {target.mention} is already blacklisted.")
        return
    bl.append(target.id)
    await update_group_settings(msg.chat.id, {"blacklisted_users": bl})
    await msg.reply(f"🚫 {target.mention} has been blacklisted from using the bot.")
    await audit_log(msg.chat.id, msg.from_user.id, "blacklist_user", str(target.id))


@bot.on_message(filters.command(["unblacklist", "ubl"]) & filters.group)
@admin_only
async def cmd_unblacklist_user(client: Client, msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target:
        await msg.reply("Reply to a user to unblacklist them.")
        return
    settings = await get_group_settings(msg.chat.id)
    bl = settings.get("blacklisted_users", [])
    if target.id not in bl:
        await msg.reply(f"❌ {target.mention} is not blacklisted.")
        return
    bl.remove(target.id)
    await update_group_settings(msg.chat.id, {"blacklisted_users": bl})
    await msg.reply(f"✅ {target.mention} unblacklisted.")
    await audit_log(msg.chat.id, msg.from_user.id, "unblacklist_user", str(target.id))


@bot.on_message(filters.command(["blword"]) & filters.group)
@admin_only
async def cmd_blacklist_word(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        await msg.reply("Usage: `/blword <word>`")
        return
    word = args[0].lower()
    settings = await get_group_settings(msg.chat.id)
    bw = settings.get("blacklisted_words", [])
    if word in bw:
        await msg.reply(f"🚫 `{word}` is already blacklisted.")
        return
    bw.append(word)
    await update_group_settings(msg.chat.id, {"blacklisted_words": bw})
    await msg.reply(f"🚫 Word `{word}` added to blacklist.")


@bot.on_message(filters.command(["unblword"]) & filters.group)
@admin_only
async def cmd_unblacklist_word(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        await msg.reply("Usage: `/unblword <word>`")
        return
    word = args[0].lower()
    settings = await get_group_settings(msg.chat.id)
    bw = settings.get("blacklisted_words", [])
    if word not in bw:
        await msg.reply(f"❌ `{word}` is not blacklisted.")
        return
    bw.remove(word)
    await update_group_settings(msg.chat.id, {"blacklisted_words": bw})
    await msg.reply(f"✅ Word `{word}` removed from blacklist.")


# ─── Stats Dashboard ──────────────────────────────────────────────────────────

@bot.on_message(filters.command(["stats"]) & filters.group)
async def cmd_stats(client: Client, msg: Message):
    stats = await get_group_stats(msg.chat.id)
    text = format_stats(stats)
    await msg.reply(text)


@bot.on_message(filters.command(["botstats"]) & (filters.private | filters.group))
@owner_only
async def cmd_bot_stats(client: Client, msg: Message):
    total = await get_total_chats()
    await msg.reply(
        f"📊 **Elite Musico Bot Stats**\n\n"
        f"🏠 Total groups: `{total}`\n"
    )


# ─── Broadcast ────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["broadcast", "bc"]) & filters.private)
@owner_only
async def cmd_broadcast(client: Client, msg: Message):
    text = " ".join(msg.command[1:])
    if not text and not msg.reply_to_message:
        await msg.reply("Usage: `/broadcast <message>` or reply to a message.")
        return
    if msg.reply_to_message:
        text = msg.reply_to_message.text or msg.reply_to_message.caption or text
    if not text:
        await msg.reply("❌ No message to broadcast.")
        return
    chat_ids = await get_all_chat_ids()
    progress = await msg.reply(f"📢 Broadcasting to **{len(chat_ids)}** groups...")
    sent, failed = 0, 0
    for cid in chat_ids:
        try:
            await client.send_message(cid, f"📢 **Elite Musico Announcement:**\n\n{text}")
            sent += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1
    await progress.edit(f"✅ Broadcast sent to **{sent}** groups. Failed: **{failed}**.")


# ─── Audit Log ────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["auditlog", "logs"]) & filters.group)
@admin_only
async def cmd_audit_log(client: Client, msg: Message):
    from core.database import get_db
    from datetime import datetime
    db = get_db()
    cursor = db.audit_logs.find({"chat_id": msg.chat.id}).sort("timestamp", -1).limit(10)
    entries = [d async for d in cursor]
    if not entries:
        await msg.reply("📝 No audit log entries yet.")
        return
    lines = ["📝 **Audit Log** (last 10)\n"]
    for e in entries:
        ts = e.get("timestamp", datetime.utcnow()).strftime("%m/%d %H:%M")
        lines.append(f"`{ts}` — `{e.get('action')}` by `{e.get('user_id')}`\n  _{e.get('detail','')[:50]}_")
    await msg.reply("\n".join(lines))


# ─── Auto-Leave Timer ─────────────────────────────────────────────────────────

@bot.on_message(filters.command(["autoleave"]) & filters.group)
@admin_only
async def cmd_autoleave(client: Client, msg: Message):
    args = msg.command[1:]
    if not args or not args[0].isdigit():
        await msg.reply("Usage: `/autoleave <seconds>` (0 = disable)")
        return
    delay = int(args[0])
    await update_group_settings(msg.chat.id, {"auto_leave_delay": delay})
    if delay == 0:
        await msg.reply("⏰ Auto-leave disabled.")
    else:
        await msg.reply(f"⏰ Auto-leave set to **{delay}** seconds of inactivity.")


# ─── Scheduled Playback ───────────────────────────────────────────────────────

@bot.on_message(filters.command(["schedule"]) & filters.group)
@admin_only
async def cmd_schedule(client: Client, msg: Message):
    args = msg.command[1:]
    if len(args) < 2:
        await msg.reply(
            "Usage: `/schedule <HH:MM> <song name>`\n"
            "Example: `/schedule 20:00 Blinding Lights`"
        )
        return
    time_str = args[0]
    query = " ".join(args[1:])
    try:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        sched = datetime.strptime(time_str, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if sched < now:
            sched += timedelta(days=1)
    except ValueError:
        await msg.reply("❌ Invalid time format. Use `HH:MM` (24h).")
        return
    uid = msg.from_user.id if msg.from_user else 0
    await add_scheduled(msg.chat.id, sched, query, uid)
    await msg.reply(f"📅 Scheduled **{query}** for `{time_str}` UTC.")
