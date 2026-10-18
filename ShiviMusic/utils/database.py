# ===========================================================
# ©️ 2025-26 All Rights Reserved by Purvi Bots (Im-Notcoder) 🚀
#
# This source code is under MIT License 📜
# ===========================================================

import random
from typing import Dict, List, Union

from ShiviMusic import userbot
from ShiviMusic.core.mongo import mongodb

authdb = mongodb.adminauth
authuserdb = mongodb.authuser
autoenddb = mongodb.autoend
assdb = mongodb.assistants
blacklist_chatdb = mongodb.blacklistChat
blockeddb = mongodb.blockedusers
chatsdb = mongodb.chats
channeldb = mongodb.cplaymode
countdb = mongodb.upcount
gbansdb = mongodb.gban
langdb = mongodb.language
onoffdb = mongodb.onoffper
playmodedb = mongodb.playmode
playtypedb = mongodb.playtypedb
skipdb = mongodb.skipmode
sudoersdb = mongodb.sudoers
usersdb = mongodb.tgusersdb
playlistdb = mongodb.playlist
autoplaydb = mongodb.autoplaymode


# ===========================================================
# MEMORY CACHE
# ===========================================================

active = []
activevideo = []
assistantdict = {}
autoend = {}
count = {}
channelconnect = {}
langm = {}
loop = {}
autoplaycache = {}
maintenance = []
nonadmin = {}
pause = {}
playmode = {}
playtype = {}
skipmode = {}
playlist = []


# ===========================================================
# PLAYLIST
# ===========================================================

async def _get_playlists(chat_id: int) -> Dict[str, int]:
    notes = await playlistdb.find_one({"chat_id": chat_id})

    if not notes:
        return {}

    return notes.get("notes", {})


async def get_playlist_names(chat_id: int) -> List[str]:
    return list((await _get_playlists(chat_id)).keys())


async def get_playlist(chat_id: int, name: str) -> Union[bool, dict]:
    notes = await _get_playlists(chat_id)

    if name in notes:
        return notes[name]

    return False


async def save_playlist(chat_id: int, name: str, note: dict):
    notes = await _get_playlists(chat_id)
    notes[name] = note

    await playlistdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"notes": notes}},
        upsert=True,
    )


async def delete_playlist(chat_id: int, name: str) -> bool:
    notes = await _get_playlists(chat_id)

    if name in notes:
        del notes[name]

        await playlistdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notes}},
            upsert=True,
        )

        return True

    return False


# ===========================================================
# ASSISTANT SYSTEM - FIXED
# ===========================================================

async def get_assistant_number(chat_id: int) -> str:
    return assistantdict.get(chat_id)


async def get_client(assistant: int):
    try:
        assistant = int(assistant)
    except (TypeError, ValueError):
        return None

    if assistant == 1:
        return userbot.one

    elif assistant == 2:
        return userbot.two

    elif assistant == 3:
        return userbot.three

    elif assistant == 4:
        return userbot.four

    elif assistant == 5:
        return userbot.five

    return None


async def set_assistant_new(chat_id, number):
    try:
        number = int(number)
    except (TypeError, ValueError):
        return None

    if number not in range(1, 6):
        return None

    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": number}},
        upsert=True,
    )

    assistantdict[chat_id] = number
    return number


async def _get_valid_assistants():
    """
    Return only valid started assistants.
    Prevents:
        IndexError: Cannot choose from an empty sequence
    """

    from ShiviMusic.core.userbot import assistants

    if not assistants:
        return []

    valid = []

    for assistant in assistants:
        try:
            assistant = int(assistant)

            if assistant in range(1, 6):
                client = await get_client(assistant)

                if client is not None:
                    valid.append(assistant)

        except (TypeError, ValueError):
            continue

    return list(dict.fromkeys(valid))


async def set_assistant(chat_id):
    assistants = await _get_valid_assistants()

    # IMPORTANT:
    # random.choice([]) se crash nahi hoga.
    if not assistants:
        return None

    ran_assistant = random.choice(assistants)

    assistantdict[chat_id] = ran_assistant

    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )

    return await get_client(ran_assistant)


async def get_assistant(chat_id: int):
    assistants = await _get_valid_assistants()

    # Assistant abhi ready nahi hai.
    if not assistants:
        return None

    # -------------------------------------------------------
    # MEMORY
    # -------------------------------------------------------

    assistant = assistantdict.get(chat_id)

    if assistant is not None:

        try:
            assistant = int(assistant)
        except (TypeError, ValueError):
            assistant = None

        if assistant in assistants:
            client = await get_client(assistant)

            if client is not None:
                return client

    # -------------------------------------------------------
    # MONGO
    # -------------------------------------------------------

    dbassistant = await assdb.find_one({"chat_id": chat_id})

    if dbassistant:

        try:
            got_assis = int(dbassistant.get("assistant"))
        except (TypeError, ValueError):
            got_assis = None

        if got_assis in assistants:

            assistantdict[chat_id] = got_assis

            client = await get_client(got_assis)

            if client is not None:
                return client

    # -------------------------------------------------------
    # RANDOM ASSISTANT
    # -------------------------------------------------------

    return await set_assistant(chat_id)


async def set_calls_assistant(chat_id):
    assistants = await _get_valid_assistants()

    # Prevent empty sequence error.
    if not assistants:
        return None

    ran_assistant = random.choice(assistants)

    assistantdict[chat_id] = ran_assistant

    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )

    return ran_assistant


async def group_assistant(self, chat_id: int):
    assistants = await _get_valid_assistants()

    if not assistants:
        return None

    assistant = assistantdict.get(chat_id)

    try:
        if assistant is not None:
            assistant = int(assistant)
    except (TypeError, ValueError):
        assistant = None

    # -------------------------------------------------------
    # DATABASE ASSISTANT
    # -------------------------------------------------------

    if assistant not in assistants:

        dbassistant = await assdb.find_one({"chat_id": chat_id})

        if dbassistant:

            try:
                assistant = int(dbassistant.get("assistant"))
            except (TypeError, ValueError):
                assistant = None

        if assistant not in assistants:
            assistant = await set_calls_assistant(chat_id)

    # -------------------------------------------------------
    # NO ASSISTANT
    # -------------------------------------------------------

    if not assistant:
        return None

    assistantdict[chat_id] = assistant

    # -------------------------------------------------------
    # RETURN CLIENT
    # -------------------------------------------------------

    if int(assistant) == 1:
        return self.one

    elif int(assistant) == 2:
        return self.two

    elif int(assistant) == 3:
        return self.three

    elif int(assistant) == 4:
        return self.four

    elif int(assistant) == 5:
        return self.five

    return None


# ===========================================================
# SKIP MODE
# ===========================================================

async def is_skipmode(chat_id: int) -> bool:
    mode = skipmode.get(chat_id)

    if mode is not None:
        return mode

    user = await skipdb.find_one({"chat_id": chat_id})

    if not user:
        skipmode[chat_id] = True
        return True

    skipmode[chat_id] = False
    return False


async def skip_on(chat_id: int):
    skipmode[chat_id] = True

    user = await skipdb.find_one({"chat_id": chat_id})

    if user:
        return await skipdb.delete_one({"chat_id": chat_id})


async def skip_off(chat_id: int):
    skipmode[chat_id] = False

    user = await skipdb.find_one({"chat_id": chat_id})

    if not user:
        return await skipdb.insert_one({"chat_id": chat_id})


# ===========================================================
# UPVOTES
# ===========================================================

async def get_upvote_count(chat_id: int) -> int:
    mode = count.get(chat_id)

    if mode is not None:
        return mode

    data = await countdb.find_one({"chat_id": chat_id})

    if not data:
        return 5

    count[chat_id] = data["mode"]

    return data["mode"]


async def set_upvotes(chat_id: int, mode: int):
    count[chat_id] = mode

    await countdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True,
    )


# ===========================================================
# AUTO END
# ===========================================================

async def is_autoend() -> bool:
    chat_id = 1234

    user = await autoenddb.find_one({"chat_id": chat_id})

    return bool(user)


async def autoend_on():
    chat_id = 1234

    await autoenddb.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id}},
        upsert=True,
    )


async def autoend_off():
    chat_id = 1234

    await autoenddb.delete_one({"chat_id": chat_id})


# ===========================================================
# LOOP
# ===========================================================

async def get_loop(chat_id: int) -> int:
    return loop.get(chat_id, 0)


async def set_loop(chat_id: int, mode: int):
    loop[chat_id] = mode


# ===========================================================
# AUTOPLAY
# ===========================================================

async def is_autoplay_on(chat_id: int) -> bool:

    cached = autoplaycache.get(chat_id)

    if cached is not None:
        return cached

    data = await autoplaydb.find_one({"chat_id": chat_id})

    status = bool(data)

    autoplaycache[chat_id] = status

    return status


async def autoplay_on(chat_id: int):

    autoplaycache[chat_id] = True

    await autoplaydb.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id}},
        upsert=True,
    )


async def autoplay_off(chat_id: int):

    autoplaycache[chat_id] = False

    await autoplaydb.delete_one({"chat_id": chat_id})


# ===========================================================
# CHANNEL MODE
# ===========================================================

async def get_cmode(chat_id: int) -> int:

    mode = channelconnect.get(chat_id)

    if mode is not None:
        return mode

    data = await channeldb.find_one({"chat_id": chat_id})

    if not data:
        return None

    channelconnect[chat_id] = data["mode"]

    return data["mode"]


async def set_cmode(chat_id: int, mode: int):

    channelconnect[chat_id] = mode

    await channeldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True,
    )


# ===========================================================
# PLAY TYPE
# ===========================================================

async def get_playtype(chat_id: int) -> str:

    mode = playtype.get(chat_id)

    if mode is not None:
        return mode

    data = await playtypedb.find_one({"chat_id": chat_id})

    if not data:
        playtype[chat_id] = "Everyone"
        return "Everyone"

    playtype[chat_id] = data["mode"]

    return data["mode"]


async def set_playtype(chat_id: int, mode: str):

    playtype[chat_id] = mode

    await playtypedb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True,
    )


# ===========================================================
# PLAY MODE
# ===========================================================

async def get_playmode(chat_id: int) -> str:

    mode = playmode.get(chat_id)

    if mode is not None:
        return mode

    data = await playmodedb.find_one({"chat_id": chat_id})

    if not data:
        playmode[chat_id] = "Direct"
        return "Direct"

    playmode[chat_id] = data["mode"]

    return data["mode"]


async def set_playmode(chat_id: int, mode: str):

    playmode[chat_id] = mode

    await playmodedb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True,
    )


# ===========================================================
# LANGUAGE
# ===========================================================

async def get_lang(chat_id: int) -> str:

    mode = langm.get(chat_id)

    if mode is not None:
        return mode

    data = await langdb.find_one({"chat_id": chat_id})

    if not data:
        langm[chat_id] = "en"
        return "en"

    langm[chat_id] = data["lang"]

    return data["lang"]


async def set_lang(chat_id: int, lang: str):

    langm[chat_id] = lang

    await langdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"lang": lang}},
        upsert=True,
    )


# ===========================================================
# MUSIC STATE
# ===========================================================

async def is_music_playing(chat_id: int) -> bool:
    return pause.get(chat_id, False)


async def music_on(chat_id: int):
    pause[chat_id] = True


async def music_off(chat_id: int):
    pause[chat_id] = False


# ===========================================================
# ACTIVE CHATS
# ===========================================================

async def get_active_chats() -> list:
    return active


async def is_active_chat(chat_id: int) -> bool:
    return chat_id in active


async def add_active_chat(chat_id: int):
    if chat_id not in active:
        active.append(chat_id)


async def remove_active_chat(chat_id: int):
    if chat_id in active:
        active.remove(chat_id)


# ===========================================================
# ACTIVE VIDEO CHATS
# ===========================================================

async def get_active_video_chats() -> list:
    return activevideo


async def is_active_video_chat(chat_id: int) -> bool:
    return chat_id in activevideo


async def add_active_video_chat(chat_id: int):
    if chat_id not in activevideo:
        activevideo.append(chat_id)


async def remove_active_video_chat(chat_id: int):
    if chat_id in activevideo:
        activevideo.remove(chat_id)


# ===========================================================
# NON ADMIN
# ===========================================================

async def check_nonadmin_chat(chat_id: int) -> bool:

    user = await authdb.find_one({"chat_id": chat_id})

    return bool(user)


async def is_nonadmin_chat(chat_id: int) -> bool:

    mode = nonadmin.get(chat_id)

    if mode is not None:
        return mode

    user = await authdb.find_one({"chat_id": chat_id})

    if not user:
        nonadmin[chat_id] = False
        return False

    nonadmin[chat_id] = True

    return True


async def add_nonadmin_chat(chat_id: int):

    nonadmin[chat_id] = True

    is_admin = await check_nonadmin_chat(chat_id)

    if is_admin:
        return

    return await authdb.insert_one({"chat_id": chat_id})


async def remove_nonadmin_chat(chat_id: int):

    nonadmin[chat_id] = False

    is_admin = await check_nonadmin_chat(chat_id)

    if not is_admin:
        return

    return await authdb.delete_one({"chat_id": chat_id})


# ===========================================================
# ON / OFF
# ===========================================================

async def is_on_off(on_off: int) -> bool:

    onoff = await onoffdb.find_one({"on_off": on_off})

    return bool(onoff)


async def add_on(on_off: int):

    if await is_on_off(on_off):
        return

    return await onoffdb.insert_one({"on_off": on_off})


async def add_off(on_off: int):

    if not await is_on_off(on_off):
        return

    return await onoffdb.delete_one({"on_off": on_off})


# ===========================================================
# MAINTENANCE
# ===========================================================

async def is_maintenance():

    if not maintenance:

        data = await onoffdb.find_one({"on_off": 1})

        maintenance.clear()

        if not data:
            maintenance.append(2)
            return True

        maintenance.append(1)
        return False

    return 1 not in maintenance


async def maintenance_off():

    maintenance.clear()
    maintenance.append(2)

    is_off = await is_on_off(1)

    if not is_off:
        return

    return await onoffdb.delete_one({"on_off": 1})


async def maintenance_on():

    maintenance.clear()
    maintenance.append(1)

    is_on = await is_on_off(1)

    if is_on:
        return

    return await onoffdb.insert_one({"on_off": 1})


# ===========================================================
# SERVED USERS
# ===========================================================

async def is_served_user(user_id: int) -> bool:

    user = await usersdb.find_one({"user_id": user_id})

    return bool(user)


async def get_served_users() -> list:

    users_list = []

    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(user)

    return users_list


async def add_served_user(user_id: int):

    if await is_served_user(user_id):
        return

    return await usersdb.insert_one({"user_id": user_id})


# ===========================================================
# SERVED CHATS
# ===========================================================

async def get_served_chats() -> list:

    chats_list = []

    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat)

    return chats_list


async def is_served_chat(chat_id: int) -> bool:

    chat = await chatsdb.find_one({"chat_id": chat_id})

    return bool(chat)


async def add_served_chat(chat_id: int):

    if await is_served_chat(chat_id):
        return

    return await chatsdb.insert_one({"chat_id": chat_id})


# ===========================================================
# BLACKLIST
# ===========================================================

async def blacklisted_chats() -> list:

    chats_list = []

    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat["chat_id"])

    return chats_list


async def blacklist_chat(chat_id: int) -> bool:

    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):

        await blacklist_chatdb.insert_one({"chat_id": chat_id})

        return True

    return False


async def whitelist_chat(chat_id: int) -> bool:

    if await blacklist_chatdb.find_one({"chat_id": chat_id}):

        await blacklist_chatdb.delete_one({"chat_id": chat_id})

        return True

    return False


# ===========================================================
# AUTH USERS
# ===========================================================

async def _get_authusers(chat_id: int) -> Dict[str, int]:

    notes = await authuserdb.find_one({"chat_id": chat_id})

    if not notes:
        return {}

    return notes.get("notes", {})


async def get_authuser_names(chat_id: int) -> List[str]:

    return list((await _get_authusers(chat_id)).keys())


async def get_authuser(chat_id: int, name: str) -> Union[bool, dict]:

    notes = await _get_authusers(chat_id)

    if name in notes:
        return notes[name]

    return False


async def save_authuser(chat_id: int, name: str, note: dict):

    notes = await _get_authusers(chat_id)

    notes[name] = note

    await authuserdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"notes": notes}},
        upsert=True,
    )


async def delete_authuser(chat_id: int, name: str) -> bool:

    notes = await _get_authusers(chat_id)

    if name not in notes:
        return False

    del notes[name]

    await authuserdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"notes": notes}},
        upsert=True,
    )

    return True


# ===========================================================
# GBAN
# ===========================================================

async def get_gbanned() -> list:

    results = []

    async for user in gbansdb.find({"user_id": {"$gt": 0}}):
        results.append(user["user_id"])

    return results


async def is_gbanned_user(user_id: int) -> bool:

    user = await gbansdb.find_one({"user_id": user_id})

    return bool(user)


async def add_gban_user(user_id: int):

    if await is_gbanned_user(user_id):
        return

    return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):

    if not await is_gbanned_user(user_id):
        return

    return await gbansdb.delete_one({"user_id": user_id})


# ===========================================================
# SUDOERS
# ===========================================================

async def get_sudoers() -> list:

    sudoers = await sudoersdb.find_one({"sudo": "sudo"})

    if not sudoers:
        return []

    return sudoers.get("sudoers", [])


async def add_sudo(user_id: int) -> bool:

    sudoers = await get_sudoers()

    if user_id not in sudoers:
        sudoers.append(user_id)

    await sudoersdb.update_one(
        {"sudo": "sudo"},
        {"$set": {"sudoers": sudoers}},
        upsert=True,
    )

    return True


async def remove_sudo(user_id: int) -> bool:

    sudoers = await get_sudoers()

    if user_id not in sudoers:
        return False

    sudoers.remove(user_id)

    await sudoersdb.update_one(
        {"sudo": "sudo"},
        {"$set": {"sudoers": sudoers}},
        upsert=True,
    )

    return True


# ===========================================================
# BANNED USERS
# ===========================================================

async def get_banned_users() -> list:

    results = []

    async for user in blockeddb.find({"user_id": {"$gt": 0}}):
        results.append(user["user_id"])

    return results


async def get_banned_count() -> int:

    users = blockeddb.find({"user_id": {"$gt": 0}})

    users = await users.to_list(length=100000)

    return len(users)


async def is_banned_user(user_id: int) -> bool:

    user = await blockeddb.find_one({"user_id": user_id})

    return bool(user)


async def add_banned_user(user_id: int):

    if await is_banned_user(user_id):
        return

    return await blockeddb.insert_one({"user_id": user_id})


async def remove_banned_user(user_id: int):

    if not await is_banned_user(user_id):
        return

    return await blockeddb.delete_one({"user_id": user_id})


# ===========================================================
# ©️ 2025-26 Purvi Bots / ShiviMusic
# ===========================================================
