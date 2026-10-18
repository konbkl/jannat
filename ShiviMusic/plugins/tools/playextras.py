# ===========================================================
# Player extras: MORE panel, /effect, /vmute, /vunmute, /vcinfo,
# /thumb, /vclogger.
# ===========================================================

import asyncio
import os

from pyrogram import enums, filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton as IKB,
    InlineKeyboardMarkup,
    Message,
)

from ShiviMusic import app
from ShiviMusic.core.call import Shivi
from ShiviMusic.misc import SUDOERS, db
from ShiviMusic.utils.chatsettings import get_setting, panel_open, set_setting
from ShiviMusic.utils.database import (
    autoplay_off,
    autoplay_on,
    get_authuser_names,
    get_loop,
    is_active_chat,
    is_autoplay_on,
    is_nonadmin_chat,
    set_loop,
)
from ShiviMusic.utils.formatters import int_to_alpha
from ShiviMusic.utils.inline.play import stream_markup
from config import BANNED_USERS
from strings import get_string

# key, label  (same order/layout as the equalizer screenshot)
EQ_LAYOUT = [
    [("normal", "ɴᴏʀᴍᴀʟ"), ("clear", "ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ")],
    [("dj", "ᴅᴊ ʙᴀss"), ("bassboost", "ʙᴀss ʙᴏᴏsᴛ")],
    [("deepbass", "ᴅᴇᴇᴘ ʙᴀss"), ("8d", "8ᴅ ᴀᴜᴅɪᴏ")],
    [("lofi", "ʟᴏ-ꜰɪ"), ("vocal", "ᴠᴏᴄᴀʟ")],
    [("treble", "ᴛʀᴇʙʟᴇ"), ("soft", "sᴏꜰᴛ")],
    [("party", "ᴘᴀʀᴛʏ"), ("nightcore", "ɴɪɢʜᴛᴄᴏʀᴇ")],
    [("slowedreverb", "sʟᴏᴡᴇᴅ+ʀᴇᴠᴇʀʙ")],
]
EQ_LABEL = {k: v for row in EQ_LAYOUT for k, v in row}
EFFECTS = tuple(k for k in EQ_LABEL if k != "normal")
VOLUMES = (50, 75, 100, 150, 200)

# ------------------------------------------------------------------ helpers
async def can_control(chat_id: int, user_id: int) -> bool:
    if user_id in SUDOERS:
        return True
    if await is_nonadmin_chat(chat_id):
        return True
    try:
        m = await app.get_chat_member(chat_id, user_id)
        if m.status == enums.ChatMemberStatus.OWNER:
            return True
        if m.privileges and m.privileges.can_manage_video_chats:
            return True
    except Exception:
        pass
    return (await int_to_alpha(user_id)) in await get_authuser_names(chat_id)


def _lang(_=None):
    return get_string("en")


def _status(title: str, by) -> str:
    return f"<blockquote><b>❖ {title}</b>\n└ <b>ʙʏ ▸</b> {by}</blockquote>"


def _close():
    return InlineKeyboardMarkup([[IKB("ᴄʟσsє ⌫", callback_data="close")]])


def _panel(chat_id: int, first_row=None):
    rows = []
    if first_row:
        rows.append(first_row)
    rows += [
        [
            IKB("🔇", callback_data=f"PX_mute|{chat_id}"),
            IKB("🔁", callback_data=f"PX_loop|{chat_id}"),
            IKB("🎚", callback_data=f"PX_fx|{chat_id}"),
            IKB("📡", callback_data=f"PX_vclog|{chat_id}"),
            IKB("🔊", callback_data=f"PX_unmute|{chat_id}"),
        ],
        [
            IKB("♻️ ᴀυᴛσᴘʟᴧʏ", callback_data=f"PX_auto|{chat_id}"),
            IKB("🖼 ᴛʜυϻʙηᴧɪʟ", callback_data=f"PX_thumb|{chat_id}"),
        ],
        [IKB("ʙᴧᴄᴋ ⟲", callback_data=f"PX_back|{chat_id}")],
    ]
    return InlineKeyboardMarkup(rows)


def _eq_state(chat_id: int):
    entry = (db.get(chat_id) or [{}])[0]
    return entry.get("effect") or "normal", int(entry.get("volume") or 100)


def _eq_text(chat_id: int) -> str:
    cur, vol = _eq_state(chat_id)
    return (
        "<blockquote><b>🎵 ᴇϙυᴀʟɪᴢᴇʀ ᴘᴧηєʟ</b>\n"
        f"└ <b>ᴄυʀʀєηᴛ :</b> {EQ_LABEL[cur]} • {vol}%\n"
        "<b>ᴘɪᴄᴋ ᴧη єғғєᴄᴛ — ᴛʀᴧᴄᴋ ᴋєєᴘs ᴘʟᴧʏɪηɢ ғʀσϻ ᴛʜє sᴧϻє ᴛɪϻє-sᴛᴧϻᴘ.</b></blockquote>"
    )


def _fx_panel(chat_id: int):
    cur, vol = _eq_state(chat_id)
    rows = []
    for row in EQ_LAYOUT:
        rows.append(
            [
                IKB(
                    ("🎼 " + label + (" · ᴏɴ" if key == cur else "")),
                    callback_data=f"PX_eq|{chat_id}|{key}",
                    style=ButtonStyle.SUCCESS if key == cur else ButtonStyle.PRIMARY,
                )
                for key, label in row
            ]
        )
    rows.append(
        [IKB(f"🗄 ᴠσʟυϻє · {vol}%", callback_data=f"PX_vol|{chat_id}", style=ButtonStyle.PRIMARY)]
    )
    rows.append(
        [IKB("❌ ᴄʟσsє ❌", callback_data="close", style=ButtonStyle.DANGER)]
    )
    return InlineKeyboardMarkup(rows)


async def _apply_effect(chat_id: int, effect: str, volume: int = None):
    playing = db.get(chat_id)
    if not playing:
        raise ValueError("ησ sσηɢ ᴘʟᴧʏɪηɢ...!")
    entry = playing[0]
    if volume is None:
        volume = int(entry.get("volume") or 100)
    if entry.get("streamtype") == "video" and (effect != "normal" or volume != 100):
        raise ValueError("ᴇϙ ᴏɴʟʏ ᴡᴏʀᴋs ᴏɴ ᴀᴜᴅɪᴏ sᴛʀᴇᴀᴍs.")
    file_path = entry.get("file")
    if not file_path or not os.path.isfile(str(file_path)):
        raise ValueError("ᴛʜɪs ᴛʀᴧᴄᴋ ᴄᴧη'ᴛ ʜᴧᴠє ᴇϙ (ʟɪᴠє / ʀєϻσᴛє sᴛʀєᴧϻ).")
    await Shivi.effect_stream(chat_id, file_path, effect, playing, volume)


# ------------------------------------------------------------------ callbacks
@app.on_callback_query(filters.regex(r"^MORE\|") & ~BANNED_USERS)
async def more_panel(client, q: CallbackQuery):
    chat_id = int(q.data.split("|")[1])
    if not await can_control(chat_id, q.from_user.id):
        return await q.answer("ᴏɴʟʏ ᴀᴅϻɪηs / ᴀυᴛʜ υsєʀs ᴄᴧη υsє ᴛʜɪs.", show_alert=True)
    panel_open[chat_id] = True
    rows = (q.message.reply_markup.inline_keyboard if q.message.reply_markup else [])
    first = rows[0] if rows and len(rows[0]) == 1 else None
    try:
        await q.edit_message_reply_markup(_panel(chat_id, first))
    except Exception:
        pass
    await q.answer()


@app.on_callback_query(filters.regex(r"^PX_") & ~BANNED_USERS)
async def px_router(client, q: CallbackQuery):
    action, rest = q.data[3:].split("|", 1)
    parts = rest.split("|")
    chat_id = int(parts[0])
    mention = q.from_user.mention

    if not await can_control(chat_id, q.from_user.id):
        return await q.answer("ᴏɴʟʏ ᴀᴅϻɪηs / ᴀυᴛʜ υsєʀs ᴄᴧη υsє ᴛʜɪs.", show_alert=True)

    if action == "back":
        panel_open[chat_id] = False
        try:
            await q.edit_message_reply_markup(
                InlineKeyboardMarkup(stream_markup(_lang(), chat_id))
            )
        except Exception:
            pass
        return await q.answer()

    if action == "fx":
        if not await is_active_chat(chat_id):
            return await q.answer("🔁 ησ sσηɢ ᴘʟᴧʏɪηɢ...!", show_alert=True)
        await q.answer()
        return await q.message.reply_text(_eq_text(chat_id), reply_markup=_fx_panel(chat_id))

    if not await is_active_chat(chat_id) and action in ("mute", "unmute", "eq", "vol", "loop"):
        return await q.answer("🔁 ησ sσηɢ ᴘʟᴧʏɪηɢ...!", show_alert=True)

    if action in ("mute", "unmute"):
        try:
            if action == "mute":
                await Shivi.mute_assistant(chat_id)
                await q.answer("🔇 ᴧssɪsᴛᴧηᴛ ϻυᴛєᴅ ɪη ᴠɪᴅєσ ᴄʜᴧᴛ..!", show_alert=True)
            else:
                await Shivi.unmute_assistant(chat_id)
                await q.answer("🔊 ᴧssɪsᴛᴧηᴛ υηϻυᴛєᴅ ɪη ᴠɪᴅєσ ᴄʜᴧᴛ..!", show_alert=True)
        except Exception as e:
            await q.answer(f"❌ {str(e)[:150]}", show_alert=True)
        return

    if action in ("eq", "vol"):
        cur, vol = _eq_state(chat_id)
        if action == "eq":
            cur = parts[1]
            if cur not in EQ_LABEL:
                return await q.answer()
        else:
            vol = VOLUMES[(VOLUMES.index(vol) + 1) % len(VOLUMES)] if vol in VOLUMES else 100
        await q.answer("⏳ ᴧᴘᴘʟʏɪηɢ...")
        try:
            await _apply_effect(chat_id, cur, vol)
        except ValueError as e:
            return await q.answer(str(e), show_alert=True)
        except Exception as e:
            return await q.answer(f"❌ {str(e)[:150]}", show_alert=True)
        try:
            await q.message.edit_text(_eq_text(chat_id), reply_markup=_fx_panel(chat_id))
        except Exception:
            pass
        return

    if action == "loop":
        await set_loop(chat_id, 5)
        await q.answer("🔁 ʟσσᴘ єηᴧʙʟєᴅ (5 ᴛɪϻєs)", show_alert=True)
        return await q.message.reply_text(
            _status("ʟσσᴘ єηᴧʙʟєᴅ (5 ᴛɪϻєs) 🎄", mention), reply_markup=_close()
        )

    if action == "vclog":
        new = not await get_setting(chat_id, "vclogger")
        await set_setting(chat_id, "vclogger", new)
        await q.answer(f"📡 ᴠᴄ ʟσɢɢєʀ {'ᴏɴ' if new else 'ᴏғғ'}", show_alert=True)
        return

    if action == "auto":
        if await is_autoplay_on(chat_id):
            await autoplay_off(chat_id)
            txt = "ᴧυᴛσᴘʟᴧʏ ᴅɪsᴧʙʟєᴅ ❌"
        else:
            await autoplay_on(chat_id)
            txt = "ᴧυᴛσᴘʟᴧʏ єηᴧʙʟєᴅ ✅"
        await q.answer(txt, show_alert=True)
        return await q.message.reply_text(_status(txt, mention), reply_markup=_close())

    if action == "thumb":
        new = not await get_setting(chat_id, "thumb")
        await set_setting(chat_id, "thumb", new)
        txt = "ᴛʜυϻʙηᴧɪʟ єηᴧʙʟєᴅ ✅" if new else "ᴛʜυϻʙηᴧɪʟ ᴅɪsᴧʙʟєᴅ ❌"
        await q.answer(txt, show_alert=True)
        return await q.message.reply_text(_status(txt, mention), reply_markup=_close())


# ------------------------------------------------------------------ commands
async def _guard(message: Message) -> bool:
    if not message.from_user:
        return False
    if not await can_control(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **ᴏɴʟʏ ᴀᴅϻɪηs / ᴀυᴛʜ υsєʀs ᴄᴧη υsє ᴛʜɪs.**")
        return False
    return True


@app.on_message(filters.command(["effect", "fx", "eq", "equalizer"]) & filters.group & ~BANNED_USERS)
async def effect_cmd(client, message: Message):
    if not await _guard(message):
        return
    chat_id = message.chat.id
    if not await is_active_chat(chat_id):
        return await message.reply_text("🔁 **ησ sσηɢ ᴘʟᴧʏɪηɢ...!**")
    if len(message.command) < 2:
        return await message.reply_text(_eq_text(chat_id), reply_markup=_fx_panel(chat_id))
    key = message.command[1].lower()
    key = {"off": "normal", "bass": "bassboost", "reverb": "slowedreverb", "slow": "slowedreverb"}.get(key, key)
    if key not in EQ_LABEL:
        return await message.reply_text(
            "**ᴜsᴧɢє :** `/eq` ᴏʀ `/eq " + "|".join(EQ_LABEL) + "`"
        )
    m = await message.reply_text("⏳ ᴧᴘᴘʟʏɪηɢ ᴇϙ...")
    try:
        await _apply_effect(chat_id, key)
    except ValueError as e:
        return await m.edit_text(str(e))
    except Exception as e:
        return await m.edit_text(f"❌ {str(e)[:200]}")
    await m.edit_text(_eq_text(chat_id), reply_markup=_fx_panel(chat_id))


@app.on_message(filters.command(["vmute", "vunmute"]) & filters.group & ~BANNED_USERS)
async def vmute_cmd(client, message: Message):
    if not await _guard(message):
        return
    chat_id = message.chat.id
    if not await is_active_chat(chat_id):
        return await message.reply_text("🔁 **ησ sσηɢ ᴘʟᴧʏɪηɢ...!**")
    try:
        if message.command[0] == "vmute":
            await Shivi.mute_assistant(chat_id)
            await message.reply_text(_status("ᴧssɪsᴛᴧηᴛ ϻυᴛєᴅ ɪη ᴠɪᴅєσ ᴄʜᴧᴛ 🔇", message.from_user.mention))
        else:
            await Shivi.unmute_assistant(chat_id)
            await message.reply_text(_status("ᴧssɪsᴛᴧηᴛ υηϻυᴛєᴅ ɪη ᴠɪᴅєσ ᴄʜᴧᴛ 🔊", message.from_user.mention))
    except Exception as e:
        await message.reply_text(f"❌ {str(e)[:200]}")


@app.on_message(filters.command(["vcinfo"]) & filters.group & ~BANNED_USERS)
async def vcinfo_cmd(client, message: Message):
    chat_id = message.chat.id
    if not await is_active_chat(chat_id):
        return await message.reply_text("🔁 **ησ sσηɢ ᴘʟᴧʏɪηɢ...!**")
    count = "?"
    try:
        from ShiviMusic.utils.database import group_assistant

        assistant = await group_assistant(Shivi, chat_id)
        count = len(await assistant.get_participants(chat_id))
    except Exception:
        pass
    loop = await get_loop(chat_id)
    await message.reply_text(
        "<blockquote><b>📡 ᴠᴄ ɪηғσ</b>\n"
        f"• <b>ᴘᴧʀᴛɪᴄɪᴘᴧηᴛs :</b> {count}\n"
        f"• <b>ᴧυᴛσᴘʟᴧʏ :</b> {'✅' if await is_autoplay_on(chat_id) else '❌'}\n"
        f"• <b>ʟσσᴘ :</b> {loop}\n"
        f"• <b>ᴛʜυϻʙηᴧɪʟ :</b> {'✅' if await get_setting(chat_id, 'thumb') else '❌'}\n"
        f"• <b>ᴇғғᴇᴄᴛ :</b> {(db.get(chat_id) or [{}])[0].get('effect') or 'ᴏғғ'}</blockquote>"
    )


async def _toggle_cmd(message: Message, key: str, on_txt: str, off_txt: str):
    if not await _guard(message):
        return
    chat_id = message.chat.id
    if len(message.command) > 1 and message.command[1].lower() in ("on", "off"):
        new = message.command[1].lower() == "on"
    else:
        new = not await get_setting(chat_id, key)
    await set_setting(chat_id, key, new)
    await message.reply_text(_status(on_txt if new else off_txt, message.from_user.mention),
                             reply_markup=_close())


@app.on_message(filters.command(["thumb", "thumbnail"]) & filters.group & ~BANNED_USERS)
async def thumb_cmd(client, message: Message):
    await _toggle_cmd(message, "thumb", "ᴛʜυϻʙηᴧɪʟ єηᴧʙʟєᴅ ✅", "ᴛʜυϻʙηᴧɪʟ ᴅɪsᴧʙʟєᴅ ❌")


@app.on_message(filters.command(["vclogger"]) & filters.group & ~BANNED_USERS)
async def vclogger_cmd(client, message: Message):
    await _toggle_cmd(message, "vclogger", "ᴠᴄ ʟσɢɢєʀ єηᴧʙʟєᴅ ✅", "ᴠᴄ ʟσɢɢєʀ ᴅɪsᴧʙʟєᴅ ❌")
