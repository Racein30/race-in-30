"""Make and schedule the extra formats.

Auto mode posts at most one extra video per run and keeps at least
MIN_GAP_HOURS between uploads, so the channel gets a steady stream
instead of a burst:
  preview   - when the next race is within 3 days
  champ     - after each new round (current season)
  title     - after champ for that round has gone out
  h2h       - after title for that round has gone out
  classic   - one famous race per day otherwise
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from . import cards, extras

OUT = os.environ.get("OUT_DIR", "out")
HANDLE = os.environ.get("CHANNEL_HANDLE", "")
MIN_GAP_HOURS = float(os.environ.get("MIN_GAP_HOURS", "5"))
FORCE = False  # manual runs remake even if already posted
FORMATS = ("champ", "title", "h2h", "preview", "predict", "classic")


def _voice(sentences: list[str], work: str):
    try:
        from . import voice as tts
        audio, caps, dur = tts.synthesize(sentences, work)
        return audio, caps, dur + 0.6
    except Exception as e:
        print(f"[voice] TTS failed, captions only: {e}")
        from .voice import proportional_captions
        return None, proportional_captions(sentences, 0.3, 27.4), 28.0


def _photos(drivers: list[dict]):
    from .photos import headshot
    imgs, credits = {}, []
    for d in drivers:
        if not d.get("url"):
            continue
        img, credit = headshot(d["url"])
        if img is not None:
            imgs[d["id"]] = img
            credits.append(credit)
    return imgs, credits


def build(fmt: str, state: dict, year: int | None = None, now: datetime | None = None):
    """Return (key, video_path, meta) or None if there's nothing to make."""
    now = now or datetime.now(timezone.utc)
    year = year or now.year
    seed = year * 1000 + now.timetuple().tm_yday

    if fmt == "classic":
        from .data import load_session
        from .main import make_short
        for season, circuit in extras.CLASSICS:
            key = f"classic-{season}-{circuit}"
            if key in state["posted"]:
                continue
            rnd = extras.classic_round(season, circuit)
            if not rnd:
                state["posted"][key] = {"skipped": "not found"}
                continue
            race = load_session(season, rnd, "Race")
            if race is None:
                state["posted"][key] = {"skipped": "no lap data"}
                continue
            video, meta = make_short(race, key)
            return key, video, meta
        return None

    os.makedirs(OUT, exist_ok=True)
    if fmt == "champ":
        c = extras.championship(year)
        if not c:
            return None
        key = f"champ-{year}-R{len(c['rounds'])}"
        if key in state["posted"] and not FORCE:
            return None
        sentences, meta = extras.championship_story(c, seed)
        work = os.path.join(OUT, key)
        os.makedirs(work, exist_ok=True)
        top = sorted(c["drivers"], key=lambda d: -max(d["cum"]))[:12]
        imgs, credits = _photos(top)
        audio, caps, dur = _voice(sentences, work)
        video = os.path.join(OUT, f"{key}.mp4")
        cards.championship(c, caps, video, audio, dur, HANDLE, photos=imgs)
    elif fmt == "title":
        t = extras.title_maths(year, now)
        if not t:
            return None
        key = f"title-{year}-R{t['round']}"
        if key in state["posted"] and not FORCE:
            return None
        sentences, meta = extras.title_story(t, seed)
        work = os.path.join(OUT, key)
        os.makedirs(work, exist_ok=True)
        credits = []
        audio, caps, dur = _voice(sentences, work)
        video = os.path.join(OUT, f"{key}.mp4")
        cards.title_maths(t, caps, video, audio, dur, HANDLE)
    elif fmt == "h2h":
        t = extras.teammates(year)
        if not t:
            return None
        key = f"h2h-{year}-R{t['rounds']}"
        if key in state["posted"] and not FORCE:
            return None
        sentences, meta = extras.teammates_story(t, seed)
        work = os.path.join(OUT, key)
        os.makedirs(work, exist_ok=True)
        credits = []
        audio, caps, dur = _voice(sentences, work)
        video = os.path.join(OUT, f"{key}.mp4")
        cards.teammates(t, caps, video, audio, dur, HANDLE)
    elif fmt == "preview":
        p = extras.preview(year, now)
        if not p:
            return None
        key = f"preview-{year}-R{p['round']}"
        if key in state["posted"] and not FORCE:
            return None
        sentences, meta = extras.preview_story(p, seed)
        work = os.path.join(OUT, key)
        os.makedirs(work, exist_ok=True)
        credits = []
        audio, caps, dur = _voice(sentences, work)
        video = os.path.join(OUT, f"{key}.mp4")
        cards.preview(p, caps, video, audio, dur, HANDLE)
    elif fmt == "predict":
        p = extras.prediction(year, now)
        if not p:
            return None
        if not FORCE and p["date"] - now > timedelta(days=2):
            return None
        key = f"predict-{year}-R{p['round']}"
        if key in state["posted"] and not FORCE:
            return None
        sentences, meta = extras.prediction_story(p, seed)
        work = os.path.join(OUT, key)
        os.makedirs(work, exist_ok=True)
        imgs, credits = _photos(p["podium"])
        audio, caps, dur = _voice(sentences, work)
        video = os.path.join(OUT, f"{key}.mp4")
        cards.prediction(p, caps, video, audio, dur, HANDLE, photos=imgs)
    else:
        raise ValueError(f"unknown format {fmt}")

    if credits:
        meta["description"] += "\n\nPhotos:\n" + "\n".join(credits)
    with open(os.path.join(work, "meta.json"), "w") as fh:
        json.dump({"meta": meta, "script": sentences}, fh, indent=2, default=str)
    print(f"[ok] {video}\n     {meta['title']}")
    return key, video, meta


def publish(fmt: str, state: dict, upload: bool, year: int | None = None) -> bool:
    got = build(fmt, state, year)
    if not got:
        print(f"[{fmt}] nothing new to make")
        return False
    key, video, meta = got
    entry = {"title": meta["title"], "made": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if upload:
        from .youtube import upload as yt_upload
        entry["video_id"] = yt_upload(video, meta["title"], meta["description"], meta["tags"])
        print(f"[up] https://youtube.com/shorts/{entry['video_id']}")
        state["last_upload"] = entry["made"]
    state["posted"][key] = entry
    if fmt == "classic":
        state["classic_day"] = datetime.now(timezone.utc).date().isoformat()
    return True


def run_extras(state: dict, upload: bool, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    last = state.get("last_upload")
    if last and now - datetime.fromisoformat(last) < timedelta(hours=MIN_GAP_HOURS):
        print("[extras] waiting for the gap between uploads")
        return 0
    year = now.year
    posted = state["posted"]
    order = ["preview", "predict", "champ", "title", "h2h"]
    if state.get("classic_day") != now.date().isoformat():
        order.append("classic")
    for fmt in order:
        try:
            if fmt == "title" and not any(k.startswith(f"champ-{year}-") for k in posted):
                continue
            if fmt in ("title", "h2h"):
                c_keys = sorted(k for k in posted if k.startswith(f"champ-{year}-"))
                prev = "champ"
                latest = c_keys[-1].split("-R")[-1] if c_keys else None
                if latest and f"{prev}-{year}-R{latest}" not in posted:
                    continue
            if publish(fmt, state, upload, year):
                return 1
        except Exception as e:
            print(f"[extras] {fmt} failed: {type(e).__name__}: {e}")
    return 0
