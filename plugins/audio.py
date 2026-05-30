"""Audio processing & effects — EQ, bass boost, nightcore, karaoke, reverb, speed, pitch, 3D, normalizer."""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from core.client import bot
from core.cache import get_session, update_session, get_now_playing
from helpers.decorators import admin_or_dj
from helpers.ffmpeg import EQ_PRESETS


def _effects_buttons(effects: dict) -> InlineKeyboardMarkup:
    def _icon(key): return "✅" if effects.get(key) else "❌"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{_icon('bass_boost')} Bass", callback_data="fx_bass"),
            InlineKeyboardButton(f"{_icon('nightcore')} Nightcore", callback_data="fx_nightcore"),
            InlineKeyboardButton(f"{_icon('daycore')} Daycore", callback_data="fx_daycore"),
        ],
        [
            InlineKeyboardButton(f"{_icon('reverb')} Reverb", callback_data="fx_reverb"),
            InlineKeyboardButton(f"{_icon('karaoke')} Karaoke", callback_data="fx_karaoke"),
            InlineKeyboardButton(f"{_icon('spatial')} 3D Audio", callback_data="fx_spatial"),
        ],
        [
            InlineKeyboardButton(f"{_icon('normalize')} Normalize", callback_data="fx_normalize"),
            InlineKeyboardButton("🎵 EQ Preset", callback_data="fx_eq_menu"),
        ],
        [InlineKeyboardButton("⚙️ Reset All Effects", callback_data="fx_reset")],
    ])


async def _apply_and_restart(chat_id: int):
    """Restart stream with new effects applied."""
    from core.cache import get_now_playing as _gnp
    from plugins.play import _stream_track
    track = await _gnp(chat_id)
    if not track:
        return
    session = await get_session(chat_id)
    from core.client import call_py
    try:
        await call_py.leave_group_call(chat_id)
    except Exception:
        pass
    await _stream_track(chat_id, track, session)


@bot.on_message(filters.command(["effects", "fx"]) & filters.group)
@admin_or_dj
async def cmd_effects(client: Client, msg: Message):
    np = await get_now_playing(msg.chat.id)
    if not np:
        await msg.reply("❌ Nothing is playing.")
        return
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    await msg.reply("🎛️ **Audio Effects Panel**\nToggle effects below:", reply_markup=_effects_buttons(effects))


@bot.on_callback_query(filters.regex(r"^fx_(.+)$"))
async def cb_effects(client, cq):
    key_map = {
        "bass": "bass_boost",
        "nightcore": "nightcore",
        "daycore": "daycore",
        "reverb": "reverb",
        "karaoke": "karaoke",
        "spatial": "spatial",
        "normalize": "normalize",
    }
    action = cq.data.split("_", 1)[1]

    session = await get_session(cq.message.chat.id)
    effects = session.get("effects", {})

    if action == "reset":
        effects = {}
        session["effects"] = effects
        await update_session(cq.message.chat.id, session)
        await cq.answer("⚙️ All effects reset!")
        await cq.message.edit_reply_markup(_effects_buttons(effects))
        await _apply_and_restart(cq.message.chat.id)
        return

    if action == "eq_menu":
        presets = list(EQ_PRESETS.keys())
        buttons = [
            [InlineKeyboardButton(p.capitalize(), callback_data=f"eq_preset_{p}") for p in presets[i:i+3]]
            for i in range(0, len(presets), 3)
        ]
        buttons.append([InlineKeyboardButton("« Back", callback_data="fx_back")])
        await cq.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        await cq.answer()
        return

    if action == "back":
        await cq.message.edit_reply_markup(_effects_buttons(effects))
        await cq.answer()
        return

    if action in key_map:
        fx_key = key_map[action]
        if fx_key == "bass_boost":
            current_level = effects.get("bass_boost", 0)
            new_level = (current_level + 1) % 4
            effects["bass_boost"] = new_level
        elif fx_key in ("nightcore", "daycore"):
            other = "daycore" if fx_key == "nightcore" else "nightcore"
            effects[other] = False
            effects[fx_key] = not effects.get(fx_key, False)
        else:
            effects[fx_key] = not effects.get(fx_key, False)
        session["effects"] = effects
        await update_session(cq.message.chat.id, session)
        await cq.answer(f"{'✅' if effects.get(fx_key if fx_key != 'bass_boost' else fx_key) else '❌'} {action.capitalize()}")
        await cq.message.edit_reply_markup(_effects_buttons(effects))
        await _apply_and_restart(cq.message.chat.id)


@bot.on_callback_query(filters.regex(r"^eq_preset_(.+)$"))
async def cb_eq_preset(client, cq):
    preset = cq.data.split("eq_preset_")[1]
    session = await get_session(cq.message.chat.id)
    effects = session.get("effects", {})
    effects["eq_preset"] = preset
    session["effects"] = effects
    await update_session(cq.message.chat.id, session)
    await cq.answer(f"🎵 EQ: {preset.capitalize()}")
    await cq.message.edit_reply_markup(_effects_buttons(effects))
    await _apply_and_restart(cq.message.chat.id)


@bot.on_message(filters.command(["bassboost", "bass"]) & filters.group)
@admin_or_dj
async def cmd_bass(client: Client, msg: Message):
    args = msg.command[1:]
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    if args and args[0].isdigit():
        level = max(0, min(3, int(args[0])))
    else:
        level = (effects.get("bass_boost", 0) + 1) % 4
    effects["bass_boost"] = level
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    if level == 0:
        await msg.reply("🔊 Bass boost disabled.")
    else:
        await msg.reply(f"🔊 Bass boost level **{level}** enabled!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["nightcore"]) & filters.group)
@admin_or_dj
async def cmd_nightcore(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["nightcore"] = not effects.get("nightcore", False)
    effects["daycore"] = False
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    status = "enabled" if effects["nightcore"] else "disabled"
    await msg.reply(f"🚀 Nightcore **{status}**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["daycore", "slowmode"]) & filters.group)
@admin_or_dj
async def cmd_daycore(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["daycore"] = not effects.get("daycore", False)
    effects["nightcore"] = False
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    status = "enabled" if effects["daycore"] else "disabled"
    await msg.reply(f"🐢 Daycore **{status}**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["reverb", "echo"]) & filters.group)
@admin_or_dj
async def cmd_reverb(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["reverb"] = not effects.get("reverb", False)
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    status = "enabled" if effects["reverb"] else "disabled"
    await msg.reply(f"🌊 Reverb **{status}**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["karaoke"]) & filters.group)
@admin_or_dj
async def cmd_karaoke(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["karaoke"] = not effects.get("karaoke", False)
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    status = "enabled" if effects["karaoke"] else "disabled"
    await msg.reply(f"🎤 Karaoke mode **{status}**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["3d", "spatial"]) & filters.group)
@admin_or_dj
async def cmd_spatial(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["spatial"] = not effects.get("spatial", False)
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    status = "enabled" if effects["spatial"] else "disabled"
    await msg.reply(f"🎶 3D Spatial Audio **{status}**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["normalize", "norm"]) & filters.group)
@admin_or_dj
async def cmd_normalize(client: Client, msg: Message):
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["normalize"] = not effects.get("normalize", False)
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    status = "enabled" if effects["normalize"] else "disabled"
    await msg.reply(f"🔔 Normalizer **{status}**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["speed"]) & filters.group)
@admin_or_dj
async def cmd_speed(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        await msg.reply("Usage: `/speed <0.5-2.0>` (e.g. `/speed 1.5`)")
        return
    try:
        speed = float(args[0])
        speed = max(0.5, min(2.0, speed))
    except ValueError:
        await msg.reply("❌ Invalid speed value.")
        return
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["speed"] = speed
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    await msg.reply(f"⏩ Speed set to **{speed}×**!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["pitch"]) & filters.group)
@admin_or_dj
async def cmd_pitch(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        await msg.reply("Usage: `/pitch <-12 to 12>` semitones (e.g. `/pitch 2`)")
        return
    try:
        semitones = float(args[0])
        semitones = max(-12, min(12, semitones))
    except ValueError:
        await msg.reply("❌ Invalid pitch value.")
        return
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["pitch"] = semitones
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    await msg.reply(f"🎼 Pitch shifted by **{semitones:+.1f}** semitones!")
    await _apply_and_restart(msg.chat.id)


@bot.on_message(filters.command(["eq"]) & filters.group)
@admin_or_dj
async def cmd_eq(client: Client, msg: Message):
    args = msg.command[1:]
    if not args:
        presets = ", ".join(f"`{p}`" for p in EQ_PRESETS.keys())
        await msg.reply(f"🎵 **EQ Presets:** {presets}\nUsage: `/eq <preset>`")
        return
    preset = args[0].lower()
    if preset not in EQ_PRESETS:
        await msg.reply(f"❌ Unknown preset. Available: {', '.join(EQ_PRESETS.keys())}")
        return
    session = await get_session(msg.chat.id)
    effects = session.get("effects", {})
    effects["eq_preset"] = preset
    session["effects"] = effects
    await update_session(msg.chat.id, session)
    await msg.reply(f"🎵 EQ preset set to **{preset}**!")
    await _apply_and_restart(msg.chat.id)
