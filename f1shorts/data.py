"""Load race data from official F1 timing (via FastF1) into a plain dict.

The dict format is the contract between this module and the renderer, so the
renderer can also be driven by sample data (see sample.py) with no network.

{
  "event": "Singapore Grand Prix", "year": 2026, "round": 18,
  "session": "Race" | "Sprint", "total_laps": 62,
  "drivers": [
    {"code": "VER", "name": "Max Verstappen", "last": "Verstappen",
     "team": "Red Bull Racing", "color": "#3671C6",
     "grid": 3, "finish": 1, "status": "Finished", "classified": True,
     "positions": [3, 3, 2, ...]}   # index = lap (0 = grid); None = not running
  ],
  "fastest_lap": {"code": "NOR", "time": "1:34.123", "lap": 55} | None,
}
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pandas as pd

FINISHED_STATUSES = {"Finished", "Lapped"}


def _fastf1():
    import fastf1  # imported lazily so sample mode works without it

    cache = os.environ.get("FASTF1_CACHE", ".fastf1-cache")
    os.makedirs(cache, exist_ok=True)
    fastf1.Cache.enable_cache(cache)
    return fastf1


def _utc(ts) -> datetime:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.to_pydatetime()


def recent_sessions(now: datetime | None = None, min_age_hours: float = 2.0,
                    max_age_days: float = 6.0) -> list[dict]:
    """Races and sprints that finished recently enough to post, oldest first.

    min_age_hours gives the timing data time to be published; max_age_days stops
    a first run from back-filling the whole season.
    """
    ff1 = _fastf1()
    now = now or datetime.now(timezone.utc)
    sched = ff1.get_event_schedule(now.year, include_testing=False)
    found = []
    for _, ev in sched.iterrows():
        for i in range(1, 6):
            name = ev.get(f"Session{i}")
            when = ev.get(f"Session{i}DateUtc")
            if name not in ("Race", "Sprint") or pd.isna(when):
                continue
            start = _utc(when)
            # races run ~2h; wait for that plus the publishing delay
            if start + timedelta(hours=2 + min_age_hours) <= now <= start + timedelta(days=max_age_days):
                found.append({"year": now.year, "round": int(ev["RoundNumber"]),
                              "session": name, "event": str(ev["EventName"]), "start": start})
    found.sort(key=lambda s: s["start"])
    return found


def _is_classified_finisher(status: str) -> bool:
    status = (status or "").strip()
    return status in FINISHED_STATUSES or status.startswith("+")


def _fmt_laptime(td) -> str:
    total = td.total_seconds()
    m, s = divmod(total, 60)
    return f"{int(m)}:{s:06.3f}"


def load_session(year: int, rnd: int, session: str) -> dict | None:
    """Return the race dict, or None if lap data isn't published yet."""
    ff1 = _fastf1()
    s = ff1.get_session(year, rnd, session)
    s.load(laps=True, telemetry=False, weather=False, messages=False)
    laps, res = s.laps, s.results
    if laps is None or laps.empty or res is None or res.empty:
        return None

    total = int(laps["LapNumber"].max())
    n_cars = len(res)
    drivers = []
    for _, r in res.iterrows():
        code = str(r["Abbreviation"])
        status = str(r.get("Status", "") or "")
        grid = r.get("GridPosition")
        grid = int(grid) if pd.notna(grid) and grid > 0 else n_cars  # 0 = pit-lane start
        finish = r.get("Position")
        finish = int(finish) if pd.notna(finish) else None
        classified = _is_classified_finisher(status)

        pos: list[int | None] = [None] * (total + 1)
        pos[0] = grid
        dl = laps[laps["Driver"] == code]
        for _, lap in dl.iterrows():
            if pd.notna(lap["Position"]) and pd.notna(lap["LapNumber"]):
                pos[int(lap["LapNumber"])] = int(lap["Position"])
        # forward-fill gaps while running; lapped finishers run to the flag
        last = max((i for i, p in enumerate(pos) if p is not None), default=0)
        end = total if classified else last
        for i in range(1, end + 1):
            if pos[i] is None:
                pos[i] = pos[i - 1] if pos[i - 1] is not None else (finish or grid)
        if classified and finish:
            pos[total] = finish

        color = str(r.get("TeamColor", "") or "").strip().lstrip("#")
        first = str(r.get("FirstName", "") or "")
        last_name = str(r.get("LastName", "") or code)
        drivers.append({
            "code": code, "name": f"{first} {last_name}".strip(), "last": last_name,
            "team": str(r.get("TeamName", "")),
            "color": f"#{color}" if len(color) == 6 else "#9AA0A6",
            "grid": grid, "finish": finish, "status": status,
            "classified": classified, "positions": pos,
        })

    fastest = None
    try:
        fl = laps.pick_fastest()
        if fl is not None and pd.notna(fl["LapTime"]):
            fastest = {"code": str(fl["Driver"]), "time": _fmt_laptime(fl["LapTime"]),
                       "lap": int(fl["LapNumber"])}
    except Exception:
        pass

    return {"event": str(s.event["EventName"]), "year": year, "round": rnd,
            "session": session, "total_laps": total, "drivers": drivers,
            "fastest_lap": fastest}
