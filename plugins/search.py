"""Search & Discovery — inline search, smart search, history, liked songs, trending, lyrics, recognition."""
import asyncio
from hydrogram import Client, filters
from hydrogram.types import (
    Message, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent,
)

from core.client import bot
from core.cache import get_queue, add_to_queue, get_now_playing, get_session, update_session
from core.database import (
    get_history, like_song, unlike_song, get_liked_songs, get_trending,
    get_group_settings,
)
from helpers.downloader import search_youtube, extract_info
from helpers.formatters import (
    format_search_results, format_history, format_liked_songs, format_trending,
    format_track_info,
)
from helpers.decorators import not_blacklisted
from config import GENIUS_TOKEN
from core.logger import logger


# ─── Smart Search ─────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["search", "find"]) & filters.group)
@not_blacklisted
async def cmd_search(client: Client, msg: Message):
    query = " ".join(msg.command[1:])
    if not query:
        await msg.reply("Usage: '/search <song name>'")
        return
    progress = await msg.reply(f"🔍 Searching for **{query}**...")
    results = await search_youtube(query, 5)
    if not results:
        await progress.edit("❌ No results found.")
        return
    text = format_search_results(results)
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{i+1}. {r['title'][:30]}", callback_data=f"sr_play_{r['id']}")]
        for i, r in enumerate(results)
    ])
    await progress.edit(text, reply_markup=buttons)


@bot.on_callback_query(filters.regex(r"^sr_play_(.+)$"))
async def cb_search_play(client, cq):
    video_id = cq.data.split("sr_play_")[1]
    await cq.answer("🎵 Adding to queue...")
    url = f"https://www.youtube.com/watch?v={video_id}"
    results = await search_youtube(url, 1)
    if results:
        track = results[0]
    else:
        info = await extract_info(url, download=False)
        if not info:
            await cq.answer("❌ Could not fetch track.", show_alert=True)
            return
        track = info
    uid = cq.from_user.id if cq.from_user else 0
    track["requester_id"] = uid
    track["requester_name"] = cq.from_user.first_name if cq.from_user else "User"
    np = await get_now_playing(cq.message.chat.id)
    if np is None:
        from plugins.play import _stream_track
        session = await get_session(cq.message.chat.id)
        await _stream_track(cq.message.chat.id, track, session)
    else:
        pos = await add_to_queue(cq.message.chat.id, track)
        await cq.message.edit(f"✅ Added **{track['title']}** to queue [**#{pos}**]!")


# ─── Inline Search ────────────────────────────────────────────────────────────

@bot.on_inline_query()
async def inline_search(client: Client, query):
    if not query.query.strip():
        return
    results_raw = await search_youtube(query.query, 5)
    articles = []
    for r in results_raw:
        from helpers.ffmpeg import format_duration
        dur = format_duration(r.get("duration", 0))
        articles.append(
            InlineQueryResultArticle(
                title=r.get("title", "Unknown"),
                description=f"⏱ {dur} | 👤 {r.get('uploader', '')}",
                input_message_content=InputTextMessageContent(
                    f"🎵 **{r.get('title')}**\n{r.get('url')}"
                ),
                thumb_url=r.get("thumb", ""),
            )
        )
    await query.answer(articles, cache_time=30)


# ─── History ──────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["history", "recent"]) & filters.group)
async def cmd_history(client: Client, msg: Message):
    tracks = await get_history(msg.chat.id)
    text = format_history(tracks)
    if tracks:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"▶️ {t.get('title', 'Track')[:25]}", callback_data=f"hist_play_{t.get('id')}")]
            for t in reversed(tracks[-10:])
        ])
        await msg.reply(text, reply_markup=buttons)
    else:
        await msg.reply(text)


@bot.on_callback_query(filters.regex(r"^hist_play_(.+)$"))
async def cb_history_play(client, cq):
    video_id = cq.data.split("hist_play_")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    results = await search_youtube(url, 1)
    track = results[0] if results else None
    if not track:
        await cq.answer("❌ Track not found.", show_alert=True)
        return
    uid = cq.from_user.id
    track["requester_id"] = uid
    track["requester_name"] = cq.from_user.first_name
    np = await get_now_playing(cq.message.chat.id)
    if np is None:
        from plugins.play import _stream_track
        session = await get_session(cq.message.chat.id)
        await _stream_track(cq.message.chat.id, track, session)
    else:
        pos = await add_to_queue(cq.message.chat.id, track)
    await cq.answer("✅ Added!")


# ─── Liked Songs ─────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["like"]) & filters.group)
async def cmd_like(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return
    uid = msg.from_user.id if msg.from_user else 0
    await like_song(uid, track)
    await msg.reply(f"❤️ Added **{track.get('title')}** to your liked songs!")


@bot.on_message(filters.command(["unlike"]) & filters.group)
async def cmd_unlike(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return
    uid = msg.from_user.id if msg.from_user else 0
    await unlike_song(uid, track.get("id", ""))
    await msg.reply("💔 Removed from liked songs.")


@bot.on_message(filters.command(["liked", "favorites"]) & (filters.private | filters.group))
async def cmd_liked(client: Client, msg: Message):
    uid = msg.from_user.id if msg.from_user else 0
    tracks = await get_liked_songs(uid)
    text = format_liked_songs(tracks)
    await msg.reply(text)


# ─── Trending ─────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["trending", "hot"]) & filters.group)
async def cmd_trending(client: Client, msg: Message):
    tracks = await get_trending(10)
    text = format_trending(tracks)
    await msg.reply(text)


# ─── Random / Lucky Pick ──────────────────────────────────────────────────────

@bot.on_message(filters.command(["random", "lucky"]) & filters.group)
@not_blacklisted
async def cmd_random(client: Client, msg: Message):
    import random
    tracks = await get_history(msg.chat.id)
    if not tracks:
        trending = await get_trending(20)
        if not trending:
            await msg.reply("❌ No history or trending data available.")
            return
        pick = random.choice(trending)
    else:
        pick = random.choice(tracks)
    query = pick.get("url", pick.get("title", ""))
    results = await search_youtube(query, 1)
    track = results[0] if results else pick
    uid = msg.from_user.id if msg.from_user else 0
    track["requester_id"] = uid
    track["requester_name"] = msg.from_user.first_name if msg.from_user else "User"
    np = await get_now_playing(msg.chat.id)
    if np is None:
        from plugins.play import _stream_track
        session = await get_session(msg.chat.id)
        await _stream_track(msg.chat.id, track, session)
    else:
        pos = await add_to_queue(msg.chat.id, track)
        await msg.reply(f"🎲 Random pick: **{track['title']}** added to queue [**#{pos}**]!")


# ─── Song Info ────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["songinfo", "info", "si"]) & filters.group)
async def cmd_song_info(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return
    text = format_track_info(track)
    await msg.reply(text, disable_web_page_preview=False)


# ─── Share Now Playing ────────────────────────────────────────────────────────

@bot.on_message(filters.command(["share"]) & filters.group)
async def cmd_share(client: Client, msg: Message):
    track = await get_now_playing(msg.chat.id)
    if not track:
        await msg.reply("❌ Nothing is playing.")
        return
    text = (
        f"🎵 **Elite Musico** is playing:\n\n"
        f"**{track.get('title')}**\n"
        f"👤 {track.get('uploader')}\n"
        f"🔗 {track.get('url')}"
    )
    await msg.reply(text)


# ─── Lyrics ───────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["lyrics", "ly"]) & filters.group)
async def cmd_lyrics(client: Client, msg: Message):
    args = msg.command[1:]
    if args:
        query = " ".join(args)
    else:
        track = await get_now_playing(msg.chat.id)
        if not track:
            await msg.reply("Usage: '/lyrics <song name>' or use while playing.")
            return
        query = track.get("title", "")

    progress = await msg.reply(f"🎼 Fetching lyrics for **{query}**...")

    if not GENIUS_TOKEN:
        await progress.edit(
            "⚠️ Genius API token not configured.\n"
            "Add `GENIUS_TOKEN` to your `.env` to enable lyrics."
        )
        return

    try:
        import lyricsgenius
        genius = lyricsgenius.Genius(GENIUS_TOKEN, verbose=False, remove_section_headers=True)
        loop = asyncio.get_event_loop()
        song = await loop.run_in_executor(None, lambda: genius.search_song(query))
        if not song or not song.lyrics:
            await progress.edit("❌ Lyrics not found.")
            return
        lyrics = song.lyrics[:4000]
        await progress.edit(f"🎼 **{song.title}** by **{song.artist}**\n\n{lyrics}")
    except Exception as e:
        await progress.edit(f"❌ Lyrics error: {e}")


# ─── Song Recognition ─────────────────────────────────────────────────────────

@bot.on_message(filters.command(["recognize", "shazam", "identify"]) & filters.group)
async def cmd_recognize(client: Client, msg: Message):
    if not msg.reply_to_message or not (msg.reply_to_message.voice or msg.reply_to_message.audio):
        await msg.reply("Reply to a voice message or audio to identify it.")
        return
    from config import ACRCLOUD_HOST, ACRCLOUD_KEY, ACRCLOUD_SECRET
    if not ACRCLOUD_HOST:
        await msg.reply("⚠️ ACRCloud not configured. Add 'ACRCLOUD_*' vars to '.env'.")
        return
    progress = await msg.reply("🎙️ Identifying track...")
    try:
        import acrcloud
        file_path = await client.download_media(msg.reply_to_message.voice or msg.reply_to_message.audio)
        from acrcloud.recognizer import ACRCloudRecognizer
        config = {
            "host": ACRCLOUD_HOST,
            "access_key": ACRCLOUD_KEY,
            "access_secret": ACRCLOUD_SECRET,
            "timeout": 10,
        }
        acr = ACRCloudRecognizer(config)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: acr.recognize_by_file(file_path, 0))
        import json
        data = json.loads(result)
        if data.get("status", {}).get("code") == 0:
            music = data["metadata"]["music"][0]
            title = music.get("title", "Unknown")
            artist = music["artists"][0]["name"] if music.get("artists") else "Unknown"
            album = music.get("album", {}).get("name", "")
            await progress.edit(f"🎙️ **Identified:**\n🎵 {title}\n👤 {artist}\n💿 {album}")
        else:
            await progress.edit("❌ Could not identify the track.")
    except Exception as e:
        await progress.edit(f"❌ Recognition error: {e}")
