"""Start, help, ping, and general commands."""
import time
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from core.client import bot
from core.database import get_group_settings, get_total_chats
from config import OWNER_ID, BOT_NAME


HELP_TEXT = """
🎵 **Elite Musico** — Full Command Reference

━━━ 🎵 PLAYBACK ━━━
`/play <name/URL>` — Play a song
`/vplay <name/URL>` — Play in video mode
`/radio <stream URL>` — Live radio
`/pause` — Pause playback
`/resume` — Resume playback
`/skip` — Skip current track
`/stop` — Stop & leave VC
`/np` — Now playing info
`/volume <1-200>` — Set volume
`/mute` / `/unmute` — Mute/unmute bot
`/loop` — Cycle loop modes
`/shuffle` — Shuffle queue

━━━ 📋 QUEUE ━━━
`/queue` — View queue
`/playnext <song>` — Play next (priority)
`/remove <pos>` — Remove from queue
`/clearqueue` — Clear entire queue
`/reorder <from> <to>` — Move track
`/jump <pos>` — Jump to position
`/saveplaylist <name>` — Save queue as playlist
`/loadplaylist <name>` — Load a saved playlist
`/myplaylists` — List your playlists

━━━ 🎛 AUDIO EFFECTS ━━━
`/effects` — Effects panel (buttons)
`/bass [0-3]` — Bass boost
`/nightcore` — Nightcore mode
`/daycore` — Daycore mode
`/reverb` — Reverb/echo
`/karaoke` — Vocal remover
`/3d` — Spatial/3D audio
`/normalize` — Auto-gain
`/speed <0.5-2.0>` — Playback speed
`/pitch <-12 to 12>` — Pitch shift
`/eq <preset>` — EQ preset

━━━ 🔍 SEARCH & DISCOVERY ━━━
`/search <query>` — Smart search (5 results)
`/history` — Recent played (50 tracks)
`/like` — Like current song
`/liked` — View liked songs
`/trending` — Global trending tracks
`/random` — Random/lucky pick
`/lyrics [song]` — Get lyrics
`/recognize` — Reply to voice to ID song
`/songinfo` — Full track metadata
`/share` — Share now playing

━━━ 🛡 ADMIN ━━━
`/settings` — Group settings panel
`/adddj` / `/removedj` — Manage DJs
`/djlist` — List DJs
`/blacklist` / `/unblacklist` — Block users
`/blword` / `/unblword` — Block keywords
`/stats` — Group playback stats
`/leaderboard` — Top requesters
`/voteskip` — Vote to skip
`/react` — Rate current song
`/autoleave <secs>` — Auto-leave timer
`/schedule <HH:MM> <song>` — Schedule playback
`/auditlog` — View admin actions

━━━ 👑 OWNER ONLY ━━━
`/broadcast <msg>` — Broadcast to all groups
`/botstats` — Bot-wide statistics
`/ping` — Latency check
"""


@bot.on_message(filters.command(["start"]) & filters.private)
async def cmd_start(client: Client, msg: Message):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true"),
            InlineKeyboardButton("📖 Help", callback_data="show_help"),
        ],
        [
            InlineKeyboardButton("🎵 Features", callback_data="show_features"),
        ],
    ])
    await msg.reply(
        f"🎵 **Welcome to {BOT_NAME}!**\n\n"
        "Your ultimate Telegram Voice Chat Music Bot with:\n"
        "• 90+ features & 10 audio effect modes\n"
        "• YouTube, Spotify, SoundCloud support\n"
        "• Smart queue, playlists & more\n\n"
        "Add me to your group and start jamming! 🎶",
        reply_markup=buttons,
    )


@bot.on_message(filters.command(["start"]) & filters.group)
async def cmd_start_group(client: Client, msg: Message):
    await msg.reply(
        f"🎵 **{BOT_NAME}** is ready!\nUse `/help` to see all commands.",
    )


@bot.on_callback_query(filters.regex("^show_help$"))
async def cb_show_help(client, cq):
    await cq.answer()
    await cq.message.reply(HELP_TEXT)


@bot.on_callback_query(filters.regex("^show_features$"))
async def cb_show_features(client, cq):
    await cq.answer()
    await cq.message.reply(
        "🎵 **Elite Musico Features**\n\n"
        "**Playback:** YouTube, Spotify, SoundCloud, Apple Music, Direct files, Live radio, Video mode\n\n"
        "**Effects:** 10-band EQ, Bass boost (3 levels), Nightcore, Daycore, Reverb, Karaoke, 3D Spatial, "
        "Pitch shift, Speed control, Normalizer\n\n"
        "**Queue:** Playlists (save/load), Priority queue, Jump, Reorder, Shuffle, Loop\n\n"
        "**Search:** Inline search, Smart search, History, Liked songs, Trending, Lyrics, Song ID\n\n"
        "**Community:** Vote skip, Ratings, Leaderboard, Lucky pick\n\n"
        "**Admin:** DJ system, Blacklisting, Scheduled playback, Broadcast, Audit log, Per-group settings"
    )


@bot.on_message(filters.command(["help", "h"]))
async def cmd_help(client: Client, msg: Message):
    await msg.reply(HELP_TEXT, disable_web_page_preview=True)


@bot.on_message(filters.command(["ping"]))
async def cmd_ping(client: Client, msg: Message):
    start = time.time()
    reply = await msg.reply("🏓 Pong!")
    latency = round((time.time() - start) * 1000)
    await reply.edit(f"🏓 Pong! `{latency}ms`")


@bot.on_message(filters.command(["invite"]) & filters.private)
async def cmd_invite(client: Client, msg: Message):
    me = await client.get_me()
    await msg.reply(
        f"➕ **Add {BOT_NAME} to your group:**\n"
        f"https://t.me/{me.username}?startgroup=true"
    )
