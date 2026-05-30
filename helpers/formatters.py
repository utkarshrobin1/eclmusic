from helpers.ffmpeg import format_duration


def format_track_line(index: int, track: dict) -> str:
    dur = format_duration(track.get("duration", 0))
    title = track.get("title", "Unknown")[:45]
    return f"`{index}.` **{title}** — `{dur}`"


def format_queue_page(queue: list, page: int = 0, per_page: int = 8) -> str:
    if not queue:
        return "📭 Queue is empty."
    total = len(queue)
    start = page * per_page
    end = min(start + per_page, total)
    lines = [f"📋 **Queue** — {total} tracks\n"]
    for i, track in enumerate(queue[start:end], start=start + 1):
        lines.append(format_track_line(i, track))
    pages = (total + per_page - 1) // per_page
    if pages > 1:
        lines.append(f"\nPage {page + 1}/{pages}")
    return "\n".join(lines)


def format_now_playing(track: dict, elapsed: int = 0, loop_mode: str = "none") -> str:
    from helpers.ffmpeg import build_progress_bar
    dur = format_duration(track.get("duration", 0))
    bar = build_progress_bar(elapsed, track.get("duration", 0))
    loop_icons = {"none": "➡️", "track": "🔂", "queue": "🔁"}
    loop_icon = loop_icons.get(loop_mode, "➡️")

    text = (
        f"🎵 **Now Playing**\n\n"
        f"**{track.get('title', 'Unknown')}**\n"
        f"👤 {track.get('uploader', 'Unknown')}\n"
        f"⏱ {dur}\n\n"
        f"{bar}\n\n"
        f"{loop_icon} Loop: `{loop_mode}` | 🎚 Vol: `{track.get('volume', 100)}%`"
    )
    return text


def format_search_results(results: list) -> str:
    lines = ["🔍 **Search Results** — choose a number:\n"]
    for i, r in enumerate(results, 1):
        dur = format_duration(r.get("duration", 0))
        title = r.get("title", "Unknown")[:40]
        views = r.get("views", 0)
        views_str = f"{views:,}" if views else "N/A"
        lines.append(
            f"`{i}.` **{title}**\n"
            f"    ⏱ `{dur}` | 👁 `{views_str}`"
        )
    return "\n".join(lines)


def format_history(tracks: list) -> str:
    if not tracks:
        return "📭 No history yet."
    lines = ["🕒 **Recent History** (last 10)\n"]
    for i, t in enumerate(reversed(tracks[-10:]), 1):
        lines.append(f"`{i}.` {t.get('title', 'Unknown')[:50]}")
    return "\n".join(lines)


def format_liked_songs(tracks: list) -> str:
    if not tracks:
        return "💔 No liked songs yet."
    lines = [f"❤️ **Liked Songs** — {len(tracks)} tracks\n"]
    for i, t in enumerate(tracks, 1):
        lines.append(f"`{i}.` {t.get('title', 'Unknown')[:50]}")
    return "\n".join(lines)


def format_trending(tracks: list) -> str:
    if not tracks:
        return "📭 No trending data yet."
    lines = ["🔥 **Trending Tracks**\n"]
    for i, t in enumerate(tracks, 1):
        lines.append(f"`{i}.` **{t.get('title', 'Unknown')[:40]}** — {t.get('plays', 0)} plays")
    return "\n".join(lines)


def format_leaderboard(entries: list) -> str:
    if not entries:
        return "🏆 No data yet."
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 **Top Requesters**\n"]
    for i, e in enumerate(entries, 1):
        medal = medals[i - 1] if i <= 3 else f"`{i}.`"
        name = e.get("username") or str(e.get("user_id"))
        lines.append(f"{medal} **{name}** — {e.get('requests', 0)} songs")
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    return (
        f"📊 **Group Stats**\n\n"
        f"🎵 Songs played: `{int(stats.get('songs_played', 0))}`\n"
        f"⏱ Total streamed: `{format_duration(int(stats.get('total_seconds', 0)))}`\n"
        f"👥 Unique requesters: `{int(stats.get('unique_requesters', 0))}`"
    )


def format_track_info(track: dict) -> str:
    dur = format_duration(track.get("duration", 0))
    views = track.get("views", 0)
    return (
        f"ℹ️ **Track Info**\n\n"
        f"🎵 **{track.get('title', 'Unknown')}**\n"
        f"👤 Uploader: `{track.get('uploader', 'N/A')}`\n"
        f"⏱ Duration: `{dur}`\n"
        f"👁 Views: `{views:,}`\n"
        f"📅 Released: `{track.get('release_date', 'N/A')}`\n"
        f"🎸 Genre: `{track.get('genre', 'N/A')}`\n"
        f"🔗 [YouTube]({track.get('url', '')})"
    )
