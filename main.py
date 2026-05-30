import asyncio
import json
import time
import os
import random
import psutil
import logging
import static_ffmpeg

static_ffmpeg.add_paths()



from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
import pyrogram.errors

try:
    from pyrogram.errors import GroupcallForbidden
except ImportError:
    class GroupcallForbidden(pyrogram.errors.exceptions.forbidden_403.Forbidden):
        pass
    pyrogram.errors.GroupcallForbidden = GroupcallForbidden

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, StreamEnded
from yt_dlp import YoutubeDL
from config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING, OWNER_ID

logging.basicConfig(level=logging.INFO)

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ── Clients ───────────────────────────────────────────────────────────────────
bot = Client("EliteMusico", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("EliteMusicoUser", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call_py = PyTgCalls(user)

# ── yt-dlp config (no cookies needed) ────────────────────────────────────────
YDL_OPTS = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'skip': ['hls', 'dash']
        }
    },
    'http_headers': {
        'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; Android 12; Pixel 6) gzip'
    }
}

# ── State ─────────────────────────────────────────────────────────────────────
QUEUE        = {}   # chat_id -> [{"title", "thumbnail", "file"}, ...]
PLAYING      = {}   # chat_id -> bool
NOW_PLAYING  = {}   # chat_id -> {"title", "thumbnail", "file"}
LOOP         = {}   # chat_id -> "off" | "track" | "queue"
HISTORY      = {}   # chat_id -> [{"title", "thumbnail"}, ...]   (last 10)
SEARCH_CACHE = {}   # user_id -> [{"title", "url", "thumbnail", "duration"}, ...]
TRACKED_CHATS = set()
START_TIME   = time.time()

MAX_HISTORY = 10

# ── Persistence ───────────────────────────────────────────────────────────────
def load_chats():
    if os.path.exists("chats.json"):
        try:
            with open("chats.json") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_chats():
    with open("chats.json", "w") as f:
        json.dump(list(TRACKED_CHATS), f)

TRACKED_CHATS = load_chats()

# ── Helpers ───────────────────────────────────────────────────────────────────
def push_history(chat_id, song: dict):
    HISTORY.setdefault(chat_id, [])
    HISTORY[chat_id].insert(0, {"title": song["title"], "thumbnail": song["thumbnail"]})
    HISTORY[chat_id] = HISTORY[chat_id][:MAX_HISTORY]

def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def get_loop_label(chat_id):
    mode = LOOP.get(chat_id, "off")
    return {"off": "🔁 Loop: Off", "track": "🔂 Loop: Track", "queue": "🔁 Loop: Queue"}[mode]

def get_control_markup(chat_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause",  callback_data="pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="resume"),
        ],
        [
            InlineKeyboardButton("⏭ Skip",   callback_data="skip"),
            InlineKeyboardButton("⏹ Stop",   callback_data="stop"),
        ],
        [
            InlineKeyboardButton(get_loop_label(chat_id), callback_data="loop"),
        ]
    ])

# ── Audio extraction ──────────────────────────────────────────────────────────
async def extract_song(query: str) -> dict:
    def run():
        with YoutubeDL(YDL_OPTS) as ydl:
            sq = query if query.startswith("http") else f"ytsearch1:{query}"
            info = ydl.extract_info(sq, download=True)

            # Unwrap search results safely
            if "entries" in info:
                entries = [e for e in (info["entries"] or []) if e]
                if not entries:
                    raise ValueError("No results found for that query.")
                info = entries[0]

            video_id = info.get("id", "")
            title    = info.get("title", "Unknown")
            thumb    = info.get("thumbnail", "https://telegra.ph/file/default.jpg")

            # prepare_filename can have wrong ext after conversion —
            # find the actual downloaded file by video ID instead.
            base = os.path.join("downloads", video_id)
            filepath = None
            for f in os.listdir("downloads"):
                if f.startswith(video_id):
                    filepath = os.path.abspath(os.path.join("downloads", f))
                    break

            # Fallback to prepare_filename if scan fails
            if not filepath:
                filepath = os.path.abspath(ydl.prepare_filename(info))

            return {
                "title":     title,
                "thumbnail": thumb,
                "file":      filepath,
                "duration":  info.get("duration", 0),
            }
    return await asyncio.to_thread(run)

async def search_songs(query: str, n: int = 5) -> list:
    def run():
        opts = {
            **YDL_OPTS,
            'extract_flat': True,
            'noplaylist': True,
            'quiet': True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            results = []
            for e in (info.get("entries") or [])[:n]:
                vid_id = e.get("id", "")
                results.append({
                    "title":     e.get("title", "Unknown"),
                    "url":       f"https://youtube.com/watch?v={vid_id}" if vid_id else "",
                    "thumbnail": e.get("thumbnail", ""),
                    "duration":  e.get("duration", 0),
                })
            return results
    return await asyncio.to_thread(run)

# ── Playback core ─────────────────────────────────────────────────────────────
async def play_next(chat_id: int):
    mode = LOOP.get(chat_id, "off")

    # Loop track — replay current song
    if mode == "track" and chat_id in NOW_PLAYING:
        song = NOW_PLAYING[chat_id]
        try:
            await call_py.play(
                chat_id,
                MediaStream(song["file"], video_flags=MediaStream.Flags.IGNORE)
            )
            PLAYING[chat_id] = True
            await bot.send_photo(
                chat_id,
                photo=song["thumbnail"],
                caption=f"🔂 **Looping:**\n{song['title']}",
                reply_markup=get_control_markup(chat_id)
            )
        except Exception as e:
            await bot.send_message(chat_id, f"❌ Loop error: {e}")
        return

    # Loop queue — put current song at the back
    if mode == "queue" and chat_id in NOW_PLAYING:
        QUEUE.setdefault(chat_id, []).append(NOW_PLAYING[chat_id])

    if QUEUE.get(chat_id):
        song = QUEUE[chat_id].pop(0)
        push_history(chat_id, song)
        NOW_PLAYING[chat_id] = song
        try:
            await call_py.play(
                chat_id,
                MediaStream(song["file"], video_flags=MediaStream.Flags.IGNORE)
            )
            PLAYING[chat_id] = True
            await bot.send_photo(
                chat_id,
                photo=song["thumbnail"],
                caption=f"▶️ **Now Playing:**\n{song['title']}",
                reply_markup=get_control_markup(chat_id)
            )
        except Exception as e:
            await bot.send_message(chat_id, f"❌ {e}")
            await play_next(chat_id)
    else:
        PLAYING[chat_id] = False
        NOW_PLAYING.pop(chat_id, None)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass

# ── Stream ended handler ──────────────────────────────────────────────────────
@call_py.on_update()
async def stream_handler(client, update):
    if isinstance(update, StreamEnded):
        await play_next(update.chat_id)

# ── Track chats ───────────────────────────────────────────────────────────────
@bot.on_message(filters.group | filters.private, group=1)
async def track_chats(client, message):
    if message.chat:
        cid = message.chat.id
        if cid not in TRACKED_CHATS:
            TRACKED_CHATS.add(cid)
            save_chats()

# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

# ── /start ────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    me = await client.get_me()
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{me.username}?startgroup=true"),
            InlineKeyboardButton("📚 Help", callback_data="show_help"),
        ],
        [
            InlineKeyboardButton("🎵 Play Music", switch_inline_query_current_chat="/play "),
        ]
    ])
    await message.reply_photo(
        photo="https://graph.org/file/4a60754e91eb1bb137fdd.jpg",
        caption=(
            "🎧 **Elite Musico**\n\n"
            "Premium Telegram Voice Chat Music Bot\n\n"
            "• Play music from YouTube\n"
            "• Queue management with loop & shuffle\n"
            "• Volume control & now playing card\n"
            "• Search & pick from top results\n\n"
            "Add me to your group and start a Voice Chat, then use /play!"
        ),
        reply_markup=markup
    )

# ── /help ─────────────────────────────────────────────────────────────────────
HELP_TEXT = """🎧 **Elite Musico — Commands**

**🎵 Playback**
/play `[song/url]` — Play or queue a song
/playforce `[song/url]` — Force play (interrupts current)
/search `[query]` — Pick from top 5 results
/np — Show now playing card
/pause — Pause playback
/resume — Resume playback
/skip — Skip current song
/stop — Stop & leave voice chat

**📋 Queue**
/queue — Show current queue
/remove `[pos]` — Remove song at position
/shuffle — Shuffle the queue
/loop — Toggle loop (Off → Track → Queue)

**🔊 Controls**
/vol `[1-200]` — Set volume

**📊 Info**
/history — Last 10 played songs
/stats — Bot stats (uptime, RAM, CPU)
/ping — Check bot latency
"""

@bot.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    await message.reply_text(HELP_TEXT)

# ── /play ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("play") & filters.group)
async def play(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /play `song name or YouTube URL`")

    query = " ".join(message.command[1:])
    msg   = await message.reply_text("🔎 Searching...")

    try:
        data    = await extract_song(query)
        chat_id = message.chat.id

        if PLAYING.get(chat_id):
            QUEUE.setdefault(chat_id, []).append(data)
            await msg.delete()
            return await message.reply_photo(
                photo=data["thumbnail"],
                caption=f"📝 **Added to Queue** #{len(QUEUE[chat_id])}\n\n{data['title']}"
            )

        await msg.edit_text("🎵 Joining VC...")
        await call_py.play(
            chat_id,
            MediaStream(data["file"], video_flags=MediaStream.Flags.IGNORE)
        )
        PLAYING[chat_id]     = True
        NOW_PLAYING[chat_id] = data
        push_history(chat_id, data)
        await msg.delete()
        await message.reply_photo(
            photo=data["thumbnail"],
            caption=f"▶️ **Now Playing**\n\n{data['title']}",
            reply_markup=get_control_markup(chat_id)
        )

    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

# ── /playforce ────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("playforce") & filters.group)
async def playforce(client, message: Message):
    if len(message.command) < 2:
        return
    query = " ".join(message.command[1:])
    msg   = await message.reply_text("⚡ Force searching...")
    try:
        data    = await extract_song(query)
        chat_id = message.chat.id
        await call_py.play(
            chat_id,
            MediaStream(data["file"], video_flags=MediaStream.Flags.IGNORE)
        )
        PLAYING[chat_id]     = True
        NOW_PLAYING[chat_id] = data
        push_history(chat_id, data)
        await msg.delete()
        await message.reply_photo(
            photo=data["thumbnail"],
            caption=f"⚡ **Force Playing**\n\n{data['title']}",
            reply_markup=get_control_markup(chat_id)
        )
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

# ── /search ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("search") & filters.group)
async def search_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /search `song name`")

    query = " ".join(message.command[1:])
    msg   = await message.reply_text("🔎 Searching top 5 results...")

    try:
        results = await search_songs(query, n=5)
        if not results:
            return await msg.edit_text("❌ No results found.")

        user_id = message.from_user.id
        SEARCH_CACHE[user_id] = results

        buttons = []
        text    = "🎵 **Search Results** — tap to play:\n\n"
        for i, r in enumerate(results, 1):
            dur   = fmt_duration(r["duration"])
            text += f"`{i}.` **{r['title']}** `[{dur}]`\n"
            buttons.append([InlineKeyboardButton(
                f"{i}. {r['title'][:45]}",
                callback_data=f"sp:{user_id}:{i-1}"
            )])

        await msg.delete()
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await msg.edit_text(f"❌ Search error: {e}")

# ── /np (now playing) ─────────────────────────────────────────────────────────
@bot.on_message(filters.command("np") & filters.group)
async def now_playing(client, message: Message):
    chat_id = message.chat.id
    song    = NOW_PLAYING.get(chat_id)
    if not song:
        return await message.reply_text("❌ Nothing is playing right now.")
    await message.reply_photo(
        photo=song["thumbnail"],
        caption=(
            f"🎵 **Now Playing**\n\n"
            f"**{song['title']}**\n\n"
            f"Queue: {len(QUEUE.get(chat_id, []))} songs | "
            f"Loop: {LOOP.get(chat_id, 'off').capitalize()}"
        ),
        reply_markup=get_control_markup(chat_id)
    )

# ── /queue ────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("queue") & filters.group)
async def queue_cmd(client, message: Message):
    chat_id = message.chat.id
    q       = QUEUE.get(chat_id, [])
    current = NOW_PLAYING.get(chat_id)

    if not current and not q:
        return await message.reply_text("📭 Queue is empty.")

    text = ""
    if current:
        text += f"▶️ **Now Playing:**\n{current['title']}\n\n"

    if q:
        text += f"📋 **Up Next** ({len(q)} songs):\n"
        for i, s in enumerate(q[:15], 1):
            text += f"`{i}.` {s['title']}\n"
        if len(q) > 15:
            text += f"\n_...and {len(q)-15} more_"
    else:
        text += "📭 No songs queued."

    await message.reply_text(text)

# ── /remove ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("remove") & filters.group)
async def remove_cmd(client, message: Message):
    chat_id = message.chat.id
    q       = QUEUE.get(chat_id, [])

    if len(message.command) < 2:
        return await message.reply_text("Usage: /remove `[position]`")

    try:
        pos = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Please give a valid number.")

    if not q:
        return await message.reply_text("📭 Queue is empty.")
    if pos < 1 or pos > len(q):
        return await message.reply_text(f"❌ Position must be between 1 and {len(q)}.")

    removed = q.pop(pos - 1)
    await message.reply_text(f"🗑 Removed: **{removed['title']}**")

# ── /shuffle ──────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("shuffle") & filters.group)
async def shuffle_cmd(client, message: Message):
    chat_id = message.chat.id
    q       = QUEUE.get(chat_id, [])
    if not q:
        return await message.reply_text("📭 Nothing in queue to shuffle.")
    random.shuffle(q)
    await message.reply_text(f"🔀 Shuffled {len(q)} songs in queue!")

# ── /loop ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("loop") & filters.group)
async def loop_cmd(client, message: Message):
    chat_id = message.chat.id
    modes   = ["off", "track", "queue"]
    current = LOOP.get(chat_id, "off")
    next_m  = modes[(modes.index(current) + 1) % len(modes)]
    LOOP[chat_id] = next_m
    labels  = {"off": "🔁 Loop Off", "track": "🔂 Loop Track", "queue": "🔁 Loop Queue"}
    await message.reply_text(f"{labels[next_m]} — loop mode changed.")

# ── /vol ──────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("vol") & filters.group)
async def vol_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /vol `[1-200]`")
    try:
        volume = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Please give a number between 1 and 200.")
    if not (1 <= volume <= 200):
        return await message.reply_text("❌ Volume must be between 1 and 200.")
    try:
        await call_py.change_volume_call(message.chat.id, volume)
        await message.reply_text(f"🔊 Volume set to **{volume}%**")
    except Exception as e:
        await message.reply_text(f"❌ {e}")

# ── /skip ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("skip") & filters.group)
async def skip_cmd(client, message: Message):
    LOOP[message.chat.id] = "off"  # force skip overrides loop
    await play_next(message.chat.id)
    await message.reply_text("⏭ Skipped.")

# ── /stop ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("stop") & filters.group)
async def stop_cmd(client, message: Message):
    cid           = message.chat.id
    QUEUE[cid]    = []
    PLAYING[cid]  = False
    LOOP[cid]     = "off"
    NOW_PLAYING.pop(cid, None)
    try:
        await call_py.leave_call(cid)
    except Exception:
        pass
    await message.reply_text("⏹ Stopped & left voice chat.")

# ── /history ──────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("history") & filters.group)
async def history_cmd(client, message: Message):
    chat_id = message.chat.id
    h       = HISTORY.get(chat_id, [])
    if not h:
        return await message.reply_text("📭 No play history yet.")
    text = "🕐 **Recently Played:**\n\n"
    for i, s in enumerate(h, 1):
        text += f"`{i}.` {s['title']}\n"
    await message.reply_text(text)

# ── /ping ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("ping"))
async def ping_cmd(client, message: Message):
    start = time.time()
    m     = await message.reply_text("🏓 Pinging...")
    ms    = round((time.time() - start) * 1000)
    await m.edit_text(f"🏓 **Pong!** `{ms}ms`")

# ── /stats ────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("stats"))
async def stats_cmd(client, message: Message):
    uptime = int(time.time() - START_TIME)
    h, rem = divmod(uptime, 3600)
    m, s   = divmod(rem, 60)
    await message.reply_text(
        f"📊 **Elite Musico Stats**\n\n"
        f"⏱ Uptime: `{h}h {m}m {s}s`\n"
        f"👥 Chats: `{len(TRACKED_CHATS)}`\n"
        f"🎵 Active VC: `{sum(PLAYING.values())}`\n"
        f"💾 RAM: `{psutil.virtual_memory().percent}%`\n"
        f"🖥 CPU: `{psutil.cpu_percent()}%`"
    )

# ══════════════════════════════════════════════════════════════════════════════
# CALLBACK QUERIES
# ══════════════════════════════════════════════════════════════════════════════
@bot.on_callback_query()
async def callback(client, query: CallbackQuery):
    data    = query.data
    cid     = query.message.chat.id
    user_id = query.from_user.id

    # ── Inline control buttons ────────────────────────────────────────────────
    try:
        if data == "pause":
            await call_py.pause_stream(cid)
            await query.answer("⏸ Paused")

        elif data == "resume":
            await call_py.resume_stream(cid)
            await query.answer("▶️ Resumed")

        elif data == "skip":
            LOOP[cid] = "off"
            await play_next(cid)
            await query.answer("⏭ Skipped")

        elif data == "stop":
            QUEUE[cid]   = []
            PLAYING[cid] = False
            LOOP[cid]    = "off"
            NOW_PLAYING.pop(cid, None)
            await call_py.leave_call(cid)
            await query.answer("⏹ Stopped")

        elif data == "loop":
            modes   = ["off", "track", "queue"]
            current = LOOP.get(cid, "off")
            nxt     = modes[(modes.index(current) + 1) % len(modes)]
            LOOP[cid] = nxt
            labels   = {"off": "🔁 Loop Off", "track": "🔂 Loop: Track", "queue": "🔁 Loop: Queue"}
            await query.answer(labels[nxt])
            # Update button text in the message
            try:
                await query.message.edit_reply_markup(get_control_markup(cid))
            except Exception:
                pass

        elif data == "show_help":
            await query.message.reply_text(HELP_TEXT)
            await query.answer()

        # ── Search pick ───────────────────────────────────────────────────────
        elif data.startswith("sp:"):
            _, req_uid, idx_str = data.split(":", 2)
            if str(user_id) != req_uid:
                return await query.answer("❌ This search belongs to someone else.", show_alert=True)

            results = SEARCH_CACHE.get(int(req_uid), [])
            idx     = int(idx_str)
            if not results or idx >= len(results):
                return await query.answer("❌ Result expired. Search again.", show_alert=True)

            chosen = results[idx]
            await query.answer(f"🎵 Loading: {chosen['title'][:40]}...")
            await query.message.delete()

            msg = await query.message.reply_text("🎵 Loading selected song...")
            try:
                data_song = await extract_song(chosen["url"])
                if PLAYING.get(cid):
                    QUEUE.setdefault(cid, []).append(data_song)
                    await msg.edit_text(
                        f"📝 **Added to Queue** #{len(QUEUE[cid])}\n\n{data_song['title']}"
                    )
                else:
                    await call_py.play(
                        cid,
                        MediaStream(data_song["file"], video_flags=MediaStream.Flags.IGNORE)
                    )
                    PLAYING[cid]     = True
                    NOW_PLAYING[cid] = data_song
                    push_history(cid, data_song)
                    await msg.delete()
                    await query.message.reply_photo(
                        photo=data_song["thumbnail"],
                        caption=f"▶️ **Now Playing**\n\n{data_song['title']}",
                        reply_markup=get_control_markup(cid)
                    )
            except Exception as e:
                await msg.edit_text(f"❌ {e}")

        else:
            await query.answer()

    except Exception as e:
        await query.answer(str(e), show_alert=True)

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("🎵 Elite Musico starting...")
    await bot.start()
    await user.start()
    await call_py.start()

    await bot.set_bot_commands([
        BotCommand("play",      "Play music from YouTube"),
        BotCommand("search",    "Search & pick from top 5 results"),
        BotCommand("np",        "Now playing card"),
        BotCommand("queue",     "Show current queue"),
        BotCommand("skip",      "Skip current song"),
        BotCommand("stop",      "Stop & leave voice chat"),
        BotCommand("pause",     "Pause playback"),
        BotCommand("resume",    "Resume playback"),
        BotCommand("loop",      "Toggle loop mode"),
        BotCommand("shuffle",   "Shuffle queue"),
        BotCommand("remove",    "Remove song from queue"),
        BotCommand("vol",       "Set volume (1-200)"),
        BotCommand("history",   "Last 10 played songs"),
        BotCommand("stats",     "Bot statistics"),
        BotCommand("ping",      "Check latency"),
        BotCommand("help",      "All commands"),
    ])

    print("✅ Elite Musico started!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
