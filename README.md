# 🎵 Elite Musico — Telegram Music Bot

A full-featured Telegram Voice Chat music bot — 90+ features, audio effects, smart queues, playlists, and rich now-playing cards.

---

## 🚂 Deploy on Railway (Recommended)

Railway automatically installs FFmpeg and all Python packages — no manual setup needed.

### Step 1 — Push to GitHub

Upload this folder to a GitHub repository (public or private).

### Step 2 — Create a Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repository
3. Railway will detect `nixpacks.toml` and auto-install FFmpeg + Python packages

### Step 3 — Add environment variables

In your Railway project → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `API_ID` | Your Telegram API ID |
| `API_HASH` | Your Telegram API Hash |
| `BOT_TOKEN` | Your bot token from @BotFather |
| `STRING_SESSION` | Your Pyrogram string session |
| `OWNER_ID` | Your Telegram user ID |
| `MONGO_URI` | MongoDB connection string |
| `REDIS_URL` | Redis connection string |

> ✅ No `.env` file needed on Railway — variables set in the dashboard are injected automatically.

### Step 4 — Add MongoDB & Redis on Railway

In your Railway project click **+ New** and add:

- **MongoDB** plugin → copies `MONGO_URI` automatically
- **Redis** plugin → copies `REDIS_URL` automatically

Or use free external services:
- MongoDB: [MongoDB Atlas](https://www.mongodb.com/atlas) (free tier)
- Redis: [Upstash Redis](https://upstash.com) (free tier) or [Redis Cloud](https://redis.com/try-free/)

### Step 5 — Deploy

Railway auto-deploys on every push. Check the **Logs** tab to confirm the bot started.

---

## 💻 Local Development

### Prerequisites

- Python 3.11+
- FFmpeg: `sudo apt install ffmpeg`
- MongoDB & Redis running locally

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python bot.py
```

### Generate String Session (one-time)

```bash
python gen_session.py
```

Enter your `API_ID`, `API_HASH`, phone number, and OTP. Copy the printed session string into your `.env` or Railway variables.

---

## 📋 All Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_ID` | ✅ | — | Telegram API ID from https://my.telegram.org |
| `API_HASH` | ✅ | — | Telegram API Hash |
| `BOT_TOKEN` | ✅ | — | Bot token from @BotFather |
| `STRING_SESSION` | ✅ | — | Pyrogram userbot session |
| `OWNER_ID` | ✅ | — | Your Telegram user ID |
| `MONGO_URI` | ✅ | localhost | MongoDB connection string |
| `REDIS_URL` | ✅ | localhost | Redis connection string |
| `GENIUS_TOKEN` | ⬜ | — | Genius API for lyrics |
| `SPOTIFY_CLIENT_ID` | ⬜ | — | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | ⬜ | — | Spotify app client secret |
| `ACRCLOUD_HOST` | ⬜ | — | ACRCloud host for song recognition |
| `ACRCLOUD_KEY` | ⬜ | — | ACRCloud access key |
| `ACRCLOUD_SECRET` | ⬜ | — | ACRCloud access secret |
| `MAX_QUEUE_SIZE` | ⬜ | 50 | Max tracks in queue |
| `AUTO_LEAVE_DELAY` | ⬜ | 300 | Seconds idle before leaving VC |
| `VOTE_SKIP_PERCENT` | ⬜ | 51 | % of VC members needed to vote skip |
| `DEFAULT_VOLUME` | ⬜ | 100 | Default playback volume |
| `LOG_CHANNEL` | ⬜ | 0 | Telegram channel ID for logs |
| `LOG_LEVEL` | ⬜ | INFO | Logging level |

---

## 🎵 Features

### Playback Core (12)
- Play from YouTube (search or URL)
- Play from Spotify (maps to YouTube audio)
- Apple Music / SoundCloud support
- Direct file play (audio/video messages)
- Pause / Resume
- Skip / Force Skip
- Stop & Leave
- Loop modes (track, queue, off)
- Shuffle queue
- Volume control (1–200%)
- Video mode
- Live radio streams (Icecast, HLS, MP3)

### Queue Management (9)
- Add to queue
- Play Next (priority insert)
- Paginated queue view
- Remove specific song by position
- Clear queue
- Playlist import (YouTube/Spotify URLs)
- Save & Load named playlists
- Reorder queue (move from X to Y)
- Jump to position

### Audio Effects (11)
- 10-band EQ with presets (Pop, Rock, Jazz, Classical, Hip-Hop, Lo-Fi, Flat, Bass, Treble, Vocal)
- Bass Boost (3 intensity levels)
- Reverb / Echo
- Nightcore (speed up + pitch)
- Daycore (slow down)
- Vocal Remover (Karaoke)
- Loudness Normalizer
- 3D / Spatial Audio
- Playback Speed (0.5×–2.0×)
- Pitch Shift (−12 to +12 semitones)
- Mute / Unmute

### Search & Discovery (8)
- Inline search (@botname in any chat)
- Smart search (top 5 results with thumbnail, duration, views)
- Recent Played History (50 tracks per group)
- Liked Songs / Favorites
- Trending Tracks (global)
- Lyrics (Genius API)
- Song Recognition (ACRCloud)
- Share Now Playing

### Admin & Permissions (10)
- Role system: Owner > Admin > DJ > Member
- DJ Mode
- Command Lock
- User & Keyword Blacklisting
- Usage Stats Dashboard
- Auto-Leave Timer (configurable)
- Scheduled Playback (HH:MM)
- Broadcast to all groups (owner only)
- Per-Group Settings (language, theme, volume, etc.)
- Audit Log

### Community & Vote (6)
- Vote Skip (configurable threshold)
- Song Reactions (👍/👎 rating system)
- Leaderboard (top requesters weekly/monthly)
- Random / Lucky Pick
- Share Now Playing
- Song Requests

### Now Playing UI
- Rich image card (Pillow) with 5 themes: neon, dark, gradient, minimal, vibrant
- Inline control buttons ⏮⏸⏭🔁🔀⏹
- Live Unicode progress bar
- Auto-pin NP message
- Full track metadata (/songinfo)

---

## 📋 Commands

```
/play <name/URL>       Play from YouTube or search
/vplay <name/URL>      Play in video mode
/radio <stream URL>    Live radio stream
/pause                 Pause
/resume                Resume
/skip                  Skip current track
/stop                  Stop & leave VC
/np                    Now playing info
/volume <1-200>        Set volume
/mute / /unmute        Mute/unmute bot
/loop                  Cycle loop modes
/shuffle               Shuffle queue

/queue                 View queue (paginated)
/playnext <song>       Insert as next track
/remove <pos>          Remove by position
/clearqueue            Clear queue
/reorder <from> <to>   Move track
/jump <pos>            Jump to position
/saveplaylist <name>   Save queue as playlist
/loadplaylist <name>   Load saved playlist
/myplaylists           List your playlists

/effects               Audio effects panel (buttons)
/bass [0-3]            Bass boost levels
/nightcore             Nightcore mode toggle
/daycore               Daycore mode toggle
/reverb                Reverb/echo toggle
/karaoke               Vocal remover toggle
/3d                    3D Spatial audio toggle
/normalize             Auto-gain toggle
/speed <0.5-2.0>       Playback speed
/pitch <-12 to 12>     Pitch shift semitones
/eq <preset>           EQ preset

/search <query>        Smart search (5 results)
/history               Recent played
/like                  Like current song
/liked                 View liked songs
/trending              Global trending
/random                Lucky pick
/lyrics [song]         Get lyrics
/recognize             Reply to voice to ID song
/songinfo              Full track metadata
/share                 Share now playing
/react                 Rate current song
/voteskip              Vote to skip

/settings              Group settings panel
/adddj / /removedj     Manage DJ roles
/djlist                List DJs
/blacklist             Block a user (reply)
/unblacklist           Unblock a user (reply)
/blword <word>         Block a keyword
/unblword <word>       Unblock a keyword
/stats                 Group playback stats
/leaderboard           Top requesters
/autoleave <secs>      Auto-leave timer
/schedule <HH:MM> <s>  Schedule playback
/auditlog              Admin action log

/broadcast <msg>       Broadcast to all groups (owner)
/botstats              Bot-wide statistics (owner)
/ping                  Latency check
/help                  Full command list
```

---

## 🗂 Project Structure

```
elite_musico/
├── bot.py                  Main entry point
├── config.py               Configuration (reads env vars)
├── gen_session.py          String session generator (local use)
├── requirements.txt        Python dependencies
├── nixpacks.toml           Railway build config (installs FFmpeg)
├── railway.toml            Railway deploy config
├── Procfile                Process definition
├── .env.example            Local dev template
├── README.md
├── core/
│   ├── client.py           Pyrogram + PyTgCalls clients
│   ├── database.py         MongoDB (history, playlists, stats, audit)
│   ├── cache.py            Redis (queue, session, vote skip)
│   └── logger.py           Logging
├── plugins/
│   ├── start.py            /start, /help, /ping
│   ├── play.py             Playback core
│   ├── queue.py            Queue management + playlists
│   ├── audio.py            Audio effects (11 modes)
│   ├── search.py           Search, history, liked, trending, lyrics
│   ├── admin.py            Admin controls
│   ├── vote.py             Vote skip, ratings, leaderboard
│   ├── callbacks.py        Inline button handlers
│   └── autoleave.py        Background tasks (auto-leave, scheduler)
├── helpers/
│   ├── downloader.py       yt-dlp wrapper + Spotify resolver
│   ├── ffmpeg.py           FFmpeg audio processing + effects
│   ├── thumbnail.py        Pillow now-playing cards (5 themes)
│   ├── formatters.py       Message text formatters
│   └── decorators.py       Permission decorators
└── strings/
    ├── __init__.py         Language loader
    └── en.py               English strings
```
