"""Entry point.

  python -m f1shorts.main                 # check for new races, make + upload Shorts
  python -m f1shorts.main --no-upload     # same, but only save the videos
  python -m f1shorts.main --sample        # offline preview from synthetic data
  python -m f1shorts.main --race 2026 18 Race   # (re)make one specific session
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from . import render, story

STATE = os.environ.get("STATE_FILE", "state.json")
OUT = os.environ.get("OUT_DIR", "out")
HANDLE = os.environ.get("CHANNEL_HANDLE", "")


def load_state() -> dict:
    try:
        with open(STATE) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"posted": {}}


def save_state(state: dict) -> None:
    with open(STATE, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def make_short(race: dict, tag: str, voice: bool = True) -> tuple[str, dict]:
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, tag)
    os.makedirs(work, exist_ok=True)
    f, sentences, meta = story.build(race)
    audio, caps, dur = None, None, None
    if voice:
        try:
            from . import voice as tts
            audio, caps, dur = tts.synthesize(sentences, work)
            dur += 0.6
        except Exception as e:
            print(f"[voice] TTS failed, rendering captions only: {e}")
    if caps is None:
        from .voice import proportional_captions
        dur = 31.0
        caps = proportional_captions(sentences, 0.3, dur - 0.6)
    video = os.path.join(OUT, f"{tag}.mp4")
    render.render(race, caps, video, audio_path=audio, duration=dur, handle=HANDLE, facts=f)
    with open(os.path.join(work, "meta.json"), "w") as fh:
        json.dump({"meta": meta, "script": sentences, "facts": f}, fh, indent=2, default=str)
    print(f"[ok] {video}\n     {meta['title']}")
    return video, meta


def keepalive(state: dict) -> None:
    """GitHub pauses schedules after 60 idle days; touch state monthly in the off-season."""
    last = state.get("heartbeat")
    now = datetime.now(timezone.utc)
    if not last or (now - datetime.fromisoformat(last)).days >= 30:
        state["heartbeat"] = now.isoformat(timespec="seconds")


def run(upload: bool) -> int:
    from . import data

    state = load_state()
    made = 0
    for s in data.recent_sessions():
        tag = f"{s['year']}-R{s['round']:02d}-{s['session']}"
        if tag in state["posted"]:
            continue
        print(f"[new] {s['event']} {s['session']}")
        race = data.load_session(s["year"], s["round"], s["session"])
        if race is None:
            print("      timing data not published yet, will retry next run")
            continue
        video, meta = make_short(race, tag)
        entry = {"title": meta["title"], "made": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if upload:
            from .youtube import upload as yt_upload
            entry["video_id"] = yt_upload(video, meta["title"], meta["description"], meta["tags"])
            print(f"[up] https://youtube.com/shorts/{entry['video_id']}")
            state["last_upload"] = entry["made"]
        state["posted"][tag] = entry
        save_state(state)  # save after each so a later failure can't cause a double post
        made += 1
    if made == 0:
        from .formats import run_extras
        made += run_extras(state, upload)
    keepalive(state)
    save_state(state)
    print(f"[done] {made} new Short(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--race", nargs=3, metavar=("YEAR", "ROUND", "SESSION"))
    ap.add_argument("--format", choices=("champ", "title", "h2h", "preview", "classic"))
    ap.add_argument("--year", type=int)
    a = ap.parse_args()
    if a.format:
        from . import formats
        from .formats import publish
        formats.FORCE = True
        state = load_state()
        ok = publish(a.format, state, upload=not a.no_upload, year=a.year)
        save_state(state)
        return 0 if ok else 1
    if a.sample:
        from .sample import sample_race
        make_short(sample_race(3), "sample", voice=not a.no_voice)
        return 0
    if a.race:
        from . import data
        race = data.load_session(int(a.race[0]), int(a.race[1]), a.race[2])
        if race is None:
            print("No timing data for that session yet.")
            return 1
        video, meta = make_short(race, f"{a.race[0]}-R{int(a.race[1]):02d}-{a.race[2]}", voice=not a.no_voice)
        if not a.no_upload:
            from .youtube import upload as yt_upload
            print(yt_upload(video, meta["title"], meta["description"], meta["tags"]))
        return 0
    return run(upload=not a.no_upload)


if __name__ == "__main__":
    sys.exit(main())
