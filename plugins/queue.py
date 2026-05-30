"""Queue management — view, add-next, remove, clear, reorder, jump, playlist save/load."""
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from core.client import bot
from core.cache import (
    get_queue, set_queue, add_next_to_queue, remove_from_queue,
    clear_queue, reorder_queue, get_now_playing,
)
from core.database import save_playlist, get_playlist, list_playlists
from helpers.formatters import format_queue_page, format_track_line
from helpers.downloader import search_youtube, extract_playlist
from helpers.decorators import admin_or_dj
from config import MAX_QUEUE_SIZE, OWNER_ID


def _queue_nav_buttons(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀ Prev", callback_data=f"qpage_{page - 1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("Next ▶", callback_data=f"qpage_{page + 1}"))
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons) if buttons else None


@bot.on_message(filters.command(["queue", "q"]) & filters.group)
async def cmd_queue(client: Client, msg: Message):
    queue = await get_queue(msg.chat.id)
    np = await get_now_playing(msg.chat.id)
    text = ""
    if np:
        text = f"🎵 **Now Playing:** {np.get('title', 'Unknown')}\n\n"
    text += format_queue_page(queue, page=0)
    total_pages = max(1, (len(queue) + 7) // 8)
    markup = _queue_nav_buttons(0, total_pages)
    await msg.reply(text, reply_markup=markup)


@bot.on_callback_query(filters.regex(r"^qpage_(\d+)$"))
async def cb_queue_page(client: Client, cq):
    page = int(cq.data.split("_")[1])
    queue = await get_queue(cq.message.chat.id)
    text = format_queue_page(queue, page=page)
    total_pages = max(1, (len(queue) + 7) // 8)
    markup = _queue_nav_buttons(page, total_pages)
    try:
        await cq.message.edit(text, reply_markup=markup)
    except Exception:
        pass
    await cq.answer()


@bot.on_message(filters.command(["playnext", "pn"]) & filters.group)
@admin_or_dj
async def cmd_play_next(client: Client, msg: Message):
    query = " ".join(msg.command[1:])
    if not query:
        await msg.reply("Usage: `/pn <song name>`")
        return
    results = await search_youtube(query, 1)
    if not results:
        await msg.reply("❌ No results found.")
        return
    track = results[0]
    uid = msg.from_user.id if msg.from_user else 0
    track["requester_id"] = uid
    track["requester_name"] = msg.from_user.first_name if msg.from_user else "User"
    await add_next_to_queue(msg.chat.id, track)
    await msg.reply(f"⚡ **{track['title']}** will play next!")


@bot.on_message(filters.command(["remove", "rm"]) & filters.group)
@admin_or_dj
async def cmd_remove(client: Client, msg: Message):
    args = msg.command[1:]
    if not args or not args[0].isdigit():
        await msg.reply("Usage: `/remove <position>`")
        return
    pos = int(args[0]) - 1
    track = await remove_from_queue(msg.chat.id, pos)
    if not track:
        await msg.reply("❌ Invalid queue position.")
        return
    await msg.reply(f"🗑️ Removed: **{track.get('title', 'Unknown')}**")


@bot.on_message(filters.command(["clearqueue", "cq"]) & filters.group)
@admin_or_dj
async def cmd_clear_queue(client: Client, msg: Message):
    await clear_queue(msg.chat.id)
    await msg.reply("🗑️ Queue cleared.")


@bot.on_message(filters.command(["reorder", "move"]) & filters.group)
@admin_or_dj
async def cmd_reorder(client: Client, msg: Message):
    args = msg.command[1:]
    if len(args) < 2 or not all(a.isdigit() for a in args[:2]):
        await msg.reply("Usage: `/reorder <from_pos> <to_pos>`")
        return
    from_pos = int(args[0]) - 1
    to_pos = int(args[1]) - 1
    ok = await reorder_queue(msg.chat.id, from_pos, to_pos)
    if ok:
        await msg.reply(f"↕️ Moved track from position **{from_pos+1}** to **{to_pos+1}**.")
    else:
        await msg.reply("❌ Invalid positions.")


@bot.on_message(filters.command(["jump"]) & filters.group)
@admin_or_dj
async def cmd_jump(client: Client, msg: Message):
    args = msg.command[1:]
    if not args or not args[0].isdigit():
        await msg.reply("Usage: `/jump <position>`")
        return
    pos = int(args[0]) - 1
    queue = await get_queue(msg.chat.id)
    if pos < 0 or pos >= len(queue):
        await msg.reply("❌ Invalid queue position.")
        return
    # Pop everything before pos
    from core.cache import set_queue as _sq
    new_queue = queue[pos:]
    await _sq(msg.chat.id, new_queue)
    # Trigger skip
    from core.client import call_py
    from plugins.play import _play_next
    try:
        await call_py.leave_group_call(msg.chat.id)
    except Exception:
        pass
    await _play_next(msg.chat.id)


# ─── Playlist save/load ───────────────────────────────────────────────────────

@bot.on_message(filters.command(["saveplaylist", "sp"]) & (filters.private | filters.group))
async def cmd_save_playlist(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        await msg.reply("Usage: `/saveplaylist <name>`")
        return
    name = args[0]
    queue = await get_queue(msg.chat.id)
    np = await get_now_playing(msg.chat.id)
    tracks = []
    if np:
        tracks.append(np)
    tracks.extend(queue)
    if not tracks:
        await msg.reply("❌ Nothing in queue to save.")
        return
    uid = msg.from_user.id if msg.from_user else 0
    await save_playlist(uid, name, tracks)
    await msg.reply(f"💾 Playlist **{name}** saved with **{len(tracks)}** tracks!")


@bot.on_message(filters.command(["loadplaylist", "lp"]) & filters.group)
async def cmd_load_playlist(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        uid = msg.from_user.id if msg.from_user else 0
        names = await list_playlists(uid)
        if not names:
            await msg.reply("📭 You have no saved playlists.")
            return
        text = "💾 **Your Playlists:**\n" + "\n".join(f"`{i+1}.` {n}" for i, n in enumerate(names))
        await msg.reply(text)
        return
    name = args[0]
    uid = msg.from_user.id if msg.from_user else 0
    tracks = await get_playlist(uid, name)
    if not tracks:
        await msg.reply(f"❌ Playlist **{name}** not found.")
        return
    remaining = MAX_QUEUE_SIZE - len(await get_queue(msg.chat.id))
    for t in tracks[:remaining]:
        t["requester_id"] = uid
        t["requester_name"] = msg.from_user.first_name if msg.from_user else "User"
        from core.cache import add_to_queue
        await add_to_queue(msg.chat.id, t)
    await msg.reply(f"📦 Loaded **{min(len(tracks), remaining)}** tracks from playlist **{name}**!")


@bot.on_message(filters.command(["myplaylists", "playlists"]) & (filters.private | filters.group))
async def cmd_my_playlists(client: Client, msg: Message):
    uid = msg.from_user.id if msg.from_user else 0
    names = await list_playlists(uid)
    if not names:
        await msg.reply("📭 You have no saved playlists.")
        return
    text = "💾 **Your Playlists:**\n" + "\n".join(f"`{i+1}.` {n}" for i, n in enumerate(names))
    await msg.reply(text)
