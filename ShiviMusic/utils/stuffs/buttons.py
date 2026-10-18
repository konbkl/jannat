from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram import Client, filters, enums 
import config

class BUTTONS(object):
    ABUTTON = [
    [
        InlineKeyboardButton("˹ sυᴘᴘσʀᴛ ˼", url="https://t.me/annu_support"),
        InlineKeyboardButton("˹ υᴘᴅᴧᴛєs ˼", url="https://t.me/annu_updates")
    ],
    [
        InlineKeyboardButton("˹ ❍ᴡηєʀ ˼", user_id=config.OWNER_ID),
        InlineKeyboardButton("˹  ʙᴧᴄᴋ ˼", callback_data="settingsback_helper")
    ]
]

    INFO_BUTTON = [
    [
        InlineKeyboardButton("˹ ʀєᴘσ ˼", callback_data="gib_source"),
        InlineKeyboardButton("˹ ʏᴛ-ᴀᴘɪ ˼", callback_data="bot_info_data"),
        InlineKeyboardButton("˹ ʟᴧηɢᴜᴧɢє ˼", callback_data="LG"),
    ],
    [
        
        InlineKeyboardButton("˹ ᴘʀɪᴠᴧᴄʏ ˼", url="https://files.catbox.moe/u21pts.jpg"),
        InlineKeyboardButton("⌯ ʙᴧᴄᴋ ⌯", callback_data="settingsback_helper"),
    ]
    ]
    


    INFO_NEW = [
    [
        InlineKeyboardButton("⌯ ʙᴧᴄᴋ ⌯", callback_data="settings_back_helper")
    ],
    ]
    
    
