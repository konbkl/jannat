# ===========================================================
# Per-chat settings: autoplay mode, thumbnail on/off, vc-logger,
# effect state. Small cached wrapper over one Mongo collection.
# ===========================================================

from ShiviMusic import app
from ShiviMusic.core.mongo import mongodb

_col = mongodb.chatsettings
_cache: dict[int, dict] = {}
panel_open: dict[int, bool] = {}  # chats whose player shows the MORE panel (timer loop must not overwrite)

DEFAULTS = {
    "autoplay_mode": "smart",  # smart | artist | language | similar
    "thumb": True,             # True = artwork card, False = minimalist text
    "vclogger": False,
}
AUTOPLAY_MODES = ("smart", "artist", "language", "similar")


async def _load(chat_id: int) -> dict:
    data = _cache.get(chat_id)
    if data is None:
        doc = await _col.find_one({"chat_id": chat_id}) or {}
        data = {**DEFAULTS, **{k: v for k, v in doc.items() if k in DEFAULTS}}
        _cache[chat_id] = data
    return data


async def get_setting(chat_id: int, key: str):
    return (await _load(chat_id))[key]


async def set_setting(chat_id: int, key: str, value):
    data = await _load(chat_id)
    data[key] = value
    await _col.update_one(
        {"chat_id": chat_id}, {"$set": {key: value, "chat_id": chat_id}}, upsert=True
    )


async def send_card(*args, **kwargs):
    """Drop-in for app.send_photo used for now-playing cards.

    Thumbnail ON  -> normal photo card.
    Thumbnail OFF -> minimalist text card (same caption + buttons).
    """
    chat_id = args[0] if args else kwargs.get("chat_id")
    try:
        thumb_on = await get_setting(chat_id, "thumb")
    except Exception:
        thumb_on = True
    if thumb_on:
        return await app.send_photo(*args, **kwargs)
    caption = kwargs.get("caption")
    return await app.send_message(
        chat_id,
        caption or "▶️",
        reply_markup=kwargs.get("reply_markup"),
        disable_web_page_preview=True,
    )
