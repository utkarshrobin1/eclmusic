"""Community & Vote Features — vote skip, song reactions, leaderboard, lucky, share."""
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from core.client import bot
from core.cache import (
    get_now_playing, get_session, add_vote_skip, clear_vote_skip,
    get_vote_skippers,
)
from core.database import (
    rate_song, get_song_rating, get_leaderboard, get_group_settings,
)
from helpers.formatters import format_leaderboard
from helpers.decorators import not_blacklisted
from core.logger import logger


async def _count_vc_members(client: Client, chat_id: int) -> int:
    try:
        count = await client.get_chat_members_count(chat_id)
        return max(count, 2)
    except Exception:
        return 3


@bot.on_message(filters.command(["voteskip", "vs"]) & filters.group)
@not_blacklisted
async def cmd_vote_skip(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return

    uid = msg.from_user.id if msg.from_user else 0
    voters = await get_vote_skippers(msg.chat.id)
    if str(uid) in voters:
        await msg.reply("❌ You already voted to skip.")
        return

    voters = await add_vote_skip(msg.chat.id, uid)
    settings = await get_group_settings(msg.chat.id)
    threshold_pct = settings.get("vote_skip_percent", 51)
    vc_count = await _count_vc_members(client, msg.chat.id)
    needed = max(2, int(vc_count * threshold_pct / 100))
    current = len(voters)

    if current >= needed:
        await clear_vote_skip(msg.chat.id)
        from core.client import call_py
        from plugins.play import _play_next
        try:
            await call_py.leave_group_call(msg.chat.id)
        except Exception:
            pass
        await msg.reply(f"✅ Vote skip passed! ({current}/{needed}) Skipping...")
        await _play_next(msg.chat.id)
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⬆️ Vote Skip ({current}/{needed})", callback_data="cb_voteskip")]
        ])
        await msg.reply(
            f"🗳 **Vote to Skip**\n{current}/{needed} votes needed ({threshold_pct}% of VC)",
            reply_markup=buttons,
        )


@bot.on_callback_query(filters.regex("^cb_voteskip$"))
async def cb_vote_skip(client, cq):
    uid = cq.from_user.id
    track = await get_now_playing(cq.message.chat.id)
    if not track:
        await cq.answer("❌ Nothing is playing.", show_alert=True)
        return

    voters = await get_vote_skippers(cq.message.chat.id)
    if str(uid) in voters:
        await cq.answer("❌ You already voted.", show_alert=True)
        return

    voters = await add_vote_skip(cq.message.chat.id, uid)
    settings = await get_group_settings(cq.message.chat.id)
    threshold_pct = settings.get("vote_skip_percent", 51)
    vc_count = await _count_vc_members(client, cq.message.chat.id)
    needed = max(2, int(vc_count * threshold_pct / 100))
    current = len(voters)

    if current >= needed:
        await clear_vote_skip(cq.message.chat.id)
        from core.client import call_py
        from plugins.play import _play_next
        try:
            await call_py.leave_group_call(cq.message.chat.id)
        except Exception:
            pass
        await cq.message.edit("✅ Vote skip passed! Skipping...")
        await _play_next(cq.message.chat.id)
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⬆️ Vote Skip ({current}/{needed})", callback_data="cb_voteskip")]
        ])
        try:
            await cq.message.edit_reply_markup(buttons)
        except Exception:
            pass
        await cq.answer(f"✅ Voted! {current}/{needed}")


# ─── Song Reactions ───────────────────────────────────────────────────────────

@bot.on_message(filters.command(["react", "rate"]) & filters.group)
async def cmd_react(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return
    rating_info = await get_song_rating(track.get("id", ""))
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"👍 Like", callback_data=f"react_1_{track.get('id')}"),
            InlineKeyboardButton(f"👎 Dislike", callback_data=f"react_-1_{track.get('id')}"),
        ],
        [InlineKeyboardButton(f"⭐ {rating_info['average']}/5 ({rating_info['count']} votes)", callback_data="react_noop")]
    ])
    await msg.reply(f"🎵 React to **{track.get('title', 'this song')}**:", reply_markup=buttons)


@bot.on_callback_query(filters.regex(r"^react_(-?\d+)_(.+)$"))
async def cb_react(client, cq):
    parts = cq.data.split("_", 2)
    if parts[1] == "noop":
        await cq.answer()
        return
    rating = int(parts[1])
    video_id = parts[2]
    uid = cq.from_user.id
    score = 5 if rating == 1 else 1
    await rate_song(video_id, uid, score)
    rating_info = await get_song_rating(video_id)
    await cq.answer(f"{'👍' if rating == 1 else '👎'} Thanks for rating!")
    try:
        await cq.message.edit_reply_markup(InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👍 Like", callback_data=f"react_1_{video_id}"),
                InlineKeyboardButton("👎 Dislike", callback_data=f"react_-1_{video_id}"),
            ],
            [InlineKeyboardButton(f"⭐ {rating_info['average']}/5 ({rating_info['count']} votes)", callback_data="react_noop")]
        ]))
    except Exception:
        pass


# ─── Leaderboard ─────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["leaderboard", "lb", "top"]) & filters.group)
async def cmd_leaderboard(client: Client, msg: Message):
    args = msg.command[1:]
    limit = 10
    entries = await get_leaderboard(msg.chat.id, limit)
    text = format_leaderboard(entries)
    await msg.reply(text)


# ─── Share ────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["sharenp", "share"]) & filters.group)
async def cmd_share_np(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return
    text = (
        f"🎵 **Elite Musico** — Now Playing\n\n"
        f"**{track.get('title', 'Unknown')}**\n"
        f"👤 {track.get('uploader', '')}\n\n"
        f"🔗 {track.get('url', 'N/A')}"
    )
    await msg.reply(text)
