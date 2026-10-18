from pyrogram.enums import ParseMode

from ShiviMusic import app
from ShiviMusic.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if await is_on_off(2):
        # Safely get play query
        if message.text:
            parts = message.text.split(None, 1)
            query = parts[1] if len(parts) > 1 else "No Query"
        else:
            query = "No Query"

        # Safely get chat/user information
        chat_id = message.chat.id
        chat_title = message.chat.title or "Private Chat"
        chat_username = (
            f"@{message.chat.username}"
            if message.chat.username
            else "None"
        )

        user_id = message.from_user.id if message.from_user else "Unknown"
        user_mention = (
            message.from_user.mention
            if message.from_user
            else "Unknown"
        )
        user_username = (
            f"@{message.from_user.username}"
            if message.from_user and message.from_user.username
            else "None"
        )

        logger_text = f"""
<b>❖ {app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>● ᴄʜᴀᴛ ɪᴅ ➠</b> <code>{chat_id}</code>
<b>● ᴄʜᴀᴛ ɴᴀᴍᴇ ➠</b> {chat_title}
<b>● ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ ➠</b> {chat_username}

<b>● ᴜsᴇʀ ɪᴅ ➠</b> <code>{user_id}</code>
<b>● ɴᴀᴍᴇ ➠</b> {user_mention}
<b>● ᴜsᴇʀɴᴀᴍᴇ ➠</b> {user_username}

<b>● ǫᴜᴇʀʏ ➠</b> {query}
<b>● sᴛʀᴇᴀᴍᴛʏᴘᴇ ➠</b> {streamtype}"""

        if chat_id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass

        return
