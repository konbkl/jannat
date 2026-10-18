# ===========================================================
# SMART AUTOPLAY ENGINE
#
# Sources (run in parallel):
#   1. YouTube Mix ("RD"+id) for the last played song AND the one before
#   2. Same-artist search
#   3. Same-language / same-vibe search
#   4. Title-similarity search
# Then: hard filters (shorts, mashups, jukeboxes, live, too long/short),
# no-repeat history, near-duplicate title removal, artist-streak limit,
# weighted scoring, and a prefetch cache so the next song starts instantly.
# ===========================================================

import asyncio
import glob
import os
import random
import re
import unicodedata
from collections import deque
from difflib import SequenceMatcher

import yt_dlp
from py_yt import VideosSearch

from ShiviMusic.utils.chatsettings import get_setting

_HISTORY_LIMIT = 150
_SESSION_LIMIT = 6
MIN_SEC, MAX_SEC = 60, 600
MAX_SAME_ARTIST_STREAK = 2

_played_history: dict[int, list] = {}
_session: dict[int, deque] = {}
_prefetch: dict[int, tuple] = {}
_prefetch_tasks: dict[int, asyncio.Task] = {}

BAD_WORDS = (
    "mashup", "jukebox", "nonstop", "non stop", "podcast", "interview", "trailer",
    "teaser", "reaction", "full album", "#shorts", "shorts", "karaoke", "tutorial",
    "status video", "whatsapp status", "scene", "making of", "behind the scenes",
    "1 hour", "2 hours", "10 hours", "hour loop", "audiobook", "full movie",
    "live stream", "livestream", "news", "review", "unboxing", "lesson",
)
LANGS = {
    "hindi": ("hindi", "bollywood"), "punjabi": ("punjabi",), "haryanvi": ("haryanvi",),
    "bhojpuri": ("bhojpuri",), "tamil": ("tamil",), "telugu": ("telugu",),
    "malayalam": ("malayalam",), "kannada": ("kannada",), "bengali": ("bengali",),
    "marathi": ("marathi",), "gujarati": ("gujarati",), "korean": ("korean", "k-pop", "kpop"),
    "arabic": ("arabic",), "english": ("english",),
}
SCRIPTS = {"DEVANAGARI": "hindi", "GURMUKHI": "punjabi", "TAMIL": "tamil",
           "TELUGU": "telugu", "MALAYALAM": "malayalam", "KANNADA": "kannada",
           "BENGALI": "bengali", "GUJARATI": "gujarati", "HANGUL": "korean",
           "ARABIC": "arabic"}
VIBES = ("lofi", "slowed", "reverb", "sad", "romantic", "party", "acoustic",
         "unplugged", "bhajan", "devotional", "remix", "item", "dj")
NOISE = ("official", "video", "lyrical", "lyrics", "audio", "song", "full", "hd",
         "4k", "music", "new", "latest", "ft", "feat", "with", "out now")
LABELS = ("t-series", "zee music", "sony music", "saregama", "tips", "speed records",
          "times music", "yrf", "lahari", "venus", "eros", "sa re ga ma", "vevo")


# ---------------------------------------------------------------- history
def remember_played(chat_id: int, vidid: str, title: str = None, channel: str = None):
    if not vidid:
        return
    hist = _played_history.setdefault(chat_id, [])
    if vidid in hist:
        hist.remove(vidid)
    hist.append(vidid)
    if len(hist) > _HISTORY_LIMIT:
        del hist[: len(hist) - _HISTORY_LIMIT]
    if title:
        sess = _session.setdefault(chat_id, deque(maxlen=_SESSION_LIMIT))
        if not sess or sess[-1]["vidid"] != vidid:
            sess.append({"vidid": vidid, "title": title,
                         "artist": guess_artist(title, channel)})


def clear_history(chat_id: int):
    _played_history.pop(chat_id, None)
    _session.pop(chat_id, None)
    _prefetch.pop(chat_id, None)


def _history(chat_id: int) -> list:
    return _played_history.get(chat_id, [])


# ---------------------------------------------------------------- parsing
def _parse_dur(d) -> int:
    if isinstance(d, (int, float)):
        return int(d)
    if not d or not isinstance(d, str):
        return 0
    try:
        sec = 0
        for p in d.split(":"):
            sec = sec * 60 + int(p)
        return sec
    except Exception:
        return 0


def _fmt_dur(sec: int) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _norm(t: str) -> str:
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", (t or "").lower())
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    words = [w for w in t.split() if w not in NOISE]
    return " ".join(words)


def guess_artist(title: str, channel: str = None) -> str:
    ch = (channel or "").strip()
    if ch.endswith("- Topic"):
        return ch[:-7].strip().lower()
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", title or "")
    chunks = [c.strip() for c in re.split(r"\||–|—| - |\bft\.?\b|\bfeat\.?\b|\bx\b", t) if c.strip()]
    chunks = [c for c in chunks if not any(n == c.lower() for n in NOISE)]
    if len(chunks) >= 2:
        cand = chunks[1] if "|" in (title or "") else chunks[0]
        if len(cand.split()) <= 4:
            return cand.lower()
    if ch and not any(l in ch.lower() for l in LABELS):
        return ch.lower()
    return ""


def detect_language(*texts) -> str:
    blob = " ".join(t for t in texts if t)
    low = blob.lower()
    for lang, keys in LANGS.items():
        if any(k in low for k in keys):
            return lang
    for ch in blob:
        if ch.isalpha():
            try:
                name = unicodedata.name(ch).split()[0]
            except ValueError:
                continue
            if name in SCRIPTS:
                return SCRIPTS[name]
    return ""


def detect_vibe(text: str) -> str:
    low = (text or "").lower()
    for v in VIBES:
        if v in low:
            return v
    return ""


# ---------------------------------------------------------------- fetchers
def _cookie_file():
    folder = os.path.join(os.getcwd(), "ShiviMusic", "assets")
    txt = glob.glob(os.path.join(folder, "*.txt"))
    return random.choice(txt) if txt else None


def _mix_sync(video_id: str, limit: int = 25) -> list:
    opts = {"quiet": True, "extract_flat": True, "skip_download": True,
            "playlistend": limit, "no_warnings": True}
    cf = _cookie_file()
    if cf:
        opts["cookiefile"] = cf
    url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return (info or {}).get("entries") or []


async def _src_mix(vidid: str, weight: float):
    if not vidid:
        return []
    try:
        entries = await asyncio.get_event_loop().run_in_executor(None, _mix_sync, vidid)
    except Exception as e:
        print(f"[AUTOPLAY MIX] {e}")
        return []
    out = []
    for rank, e in enumerate(entries):
        if not e or not e.get("id") or not e.get("title"):
            continue
        out.append({
            "vidid": e["id"], "title": e["title"],
            "channel": e.get("channel") or e.get("uploader") or "",
            "dur": _parse_dur(e.get("duration")),
            "thumb": e.get("thumbnail") or f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg",
            "views": e.get("view_count") or 0,
            "src": "mix", "score": weight - rank * 0.08,
        })
    return out


async def _src_search(query: str, src: str, weight: float):
    if not query:
        return []
    try:
        data = await VideosSearch(query, limit=20).next()
        results = data.get("result", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"[AUTOPLAY SEARCH:{src}] {e}")
        return []
    out = []
    for rank, v in enumerate(results):
        if not (v.get("id") and v.get("title") and v.get("duration")):
            continue
        thumbs = v.get("thumbnails") or []
        views = 0
        try:
            views = int(re.sub(r"\D", "", (v.get("viewCount") or {}).get("text", "") or "0") or 0)
        except Exception:
            pass
        out.append({
            "vidid": v["id"], "title": v["title"],
            "channel": (v.get("channel") or {}).get("name", ""),
            "dur": _parse_dur(v.get("duration")),
            "thumb": thumbs[0].get("url", "").split("?")[0] if thumbs else
            f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
            "views": views, "src": src, "score": weight - rank * 0.05,
        })
    return out


# ---------------------------------------------------------------- ranking
def _bad(title: str) -> bool:
    low = (title or "").lower()
    return any(w in low for w in BAD_WORDS)


def _song_name(title: str) -> str:
    first = re.split(r"\||–|—| - ", title or "")[0]
    return _norm(first)


def _too_similar(norm_title: str, known: list) -> bool:
    if not norm_title:
        return False
    for k in known:
        if not k:
            continue
        if k == norm_title or SequenceMatcher(None, k, norm_title).ratio() > 0.82:
            return True
    return False


def _weights(mode: str):
    # (mix_seed, mix_prev, artist, language, similar)
    return {
        "smart":    (3.0, 2.2, 2.4, 2.0, 1.4),
        "artist":   (1.2, 0.6, 4.0, 0.8, 0.8),
        "language": (1.6, 1.0, 1.0, 4.0, 1.0),
        "similar":  (1.0, 0.5, 0.8, 0.8, 4.0),
    }.get(mode, (3.0, 2.2, 2.4, 2.0, 1.4))


async def _gather_candidates(chat_id: int, mode: str):
    sess = list(_session.get(chat_id, []))
    if not sess:
        return []
    cur = sess[-1]
    prev = sess[-2] if len(sess) > 1 else None
    w_mix, w_prev, w_art, w_lang, w_sim = _weights(mode)

    lang = detect_language(*(s["title"] for s in sess[-3:]))
    vibe = detect_vibe(cur["title"])
    artist = cur.get("artist") or ""
    tasks = [_src_mix(cur["vidid"], w_mix)]
    if prev:
        tasks.append(_src_mix(prev["vidid"], w_prev))
    if artist:
        tasks.append(_src_search(f"{artist} songs", "artist", w_art))
    lq = " ".join(x for x in (lang, vibe, "songs") if x)
    tasks.append(_src_search(lq, "language", w_lang))
    tasks.append(_src_search(_norm(cur["title"]) or cur["title"], "similar", w_sim))
    groups = await asyncio.gather(*tasks, return_exceptions=True)
    flat = []
    for g in groups:
        if isinstance(g, list):
            flat.extend(g)
    return flat


def _rank(chat_id: int, cands: list, mode: str, ignore_history=False):
    sess = list(_session.get(chat_id, []))
    played = set() if ignore_history else set(_history(chat_id))
    known_norms = [_norm(s["title"]) for s in sess] + [_song_name(s["title"]) for s in sess]
    cur_artist = sess[-1]["artist"] if sess else ""
    recent_artists = [s["artist"] for s in sess[-MAX_SAME_ARTIST_STREAK:] if s["artist"]]
    streak_full = (len(recent_artists) >= MAX_SAME_ARTIST_STREAK
                   and len(set(recent_artists)) == 1)
    lang = detect_language(*(s["title"] for s in sess[-3:]))

    best: dict[str, dict] = {}
    for c in cands:
        if c["vidid"] in played or c["vidid"] in best and best[c["vidid"]]["score"] >= c["score"]:
            continue
        if not (MIN_SEC <= c["dur"] <= MAX_SEC) or _bad(c["title"]):
            continue
        if _too_similar(_norm(c["title"]), known_norms) or _too_similar(
            _song_name(c["title"]), known_norms
        ):
            continue
        art = guess_artist(c["title"], c["channel"])
        c = dict(c)
        c["artist"] = art
        if art and art == cur_artist:
            c["score"] += 0.8 if mode == "artist" else (-1.5 if streak_full else 0.3)
        if lang and detect_language(c["title"], c["channel"]) == lang:
            c["score"] += 0.7
        if c["views"] > 1_000_000:
            c["score"] += 0.4
        c["score"] += random.uniform(0, 0.6)
        best[c["vidid"]] = c
    return sorted(best.values(), key=lambda x: x["score"], reverse=True)


def _to_track(c: dict) -> dict:
    return {"vidid": c["vidid"], "title": c["title"], "link": f"https://www.youtube.com/watch?v={c['vidid']}",
            "duration_min": _fmt_dur(c["dur"]), "thumb": c["thumb"],
            "channel": c.get("channel", ""), "src": c["src"]}


# ---------------------------------------------------------------- public API
async def fetch_autoplay_tracks(chat_id: int, seed_title: str, seed_vidid: str = None, limit: int = 3):
    """Ranked list of up to `limit` fallback-ready tracks (best first)."""
    if seed_vidid:
        remember_played(chat_id, seed_vidid, seed_title)
    elif seed_title and not _session.get(chat_id):
        _session.setdefault(chat_id, deque(maxlen=_SESSION_LIMIT)).append(
            {"vidid": "", "title": seed_title, "artist": guess_artist(seed_title)})

    # prefetched result still valid for this seed?
    pre = _prefetch.pop(chat_id, None)
    if pre and pre[0] == (seed_vidid or ""):
        pre = [c for c in pre[1] if c["vidid"] not in _history(chat_id)]
        if pre:
            return [_to_track(c) for c in pre[:limit]]
    elif pre:
        pre = None

    try:
        mode = await get_setting(chat_id, "autoplay_mode")
    except Exception:
        mode = "smart"

    cands = await _gather_candidates(chat_id, mode)
    ranked = _rank(chat_id, cands, mode)
    if not ranked:  # everything already played -> soft reset, keep session context
        _played_history.pop(chat_id, None)
        remember_played(chat_id, seed_vidid, seed_title) if seed_vidid else None
        ranked = _rank(chat_id, cands, mode, ignore_history=True)
    if not ranked:
        return []
    top = ranked[: max(limit + 2, 5)]
    # weighted pick for the first slot (variety), rest stay score-ordered
    first = random.choices(top, weights=[max(t["score"], 0.1) for t in top], k=1)[0]
    ordered = [first] + [t for t in ranked if t is not first]
    return [_to_track(c) for c in ordered[:limit]]


async def fetch_autoplay_track(chat_id: int, seed_title: str, seed_vidid: str = None):
    tracks = await fetch_autoplay_tracks(chat_id, seed_title, seed_vidid, limit=1)
    return tracks[0] if tracks else None


def schedule_prefetch(chat_id: int):
    """Warm the cache while the current song plays so the next one starts instantly."""
    old = _prefetch_tasks.get(chat_id)
    if old and not old.done():
        return

    seed = (list(_session.get(chat_id, [])) or [{"vidid": ""}])[-1]["vidid"]

    async def _job():
        try:
            mode = await get_setting(chat_id, "autoplay_mode")
            cands = await _gather_candidates(chat_id, mode)
            ranked = _rank(chat_id, cands, mode)
            if ranked:
                _prefetch[chat_id] = (seed, ranked[:6])
        except Exception as e:
            print(f"[AUTOPLAY PREFETCH] {e}")

    _prefetch_tasks[chat_id] = asyncio.create_task(_job())
