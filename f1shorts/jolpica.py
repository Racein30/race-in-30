"""Backup data source: the Jolpica (Ergast-compatible) F1 API.

Used when F1's live-timing server won't serve lap data (it sometimes refuses
cloud machines). Provides lap-by-lap positions for races; sprints have no lap
data there, so those return None.
"""
from __future__ import annotations

import json
import time
import urllib.request

BASE = "https://api.jolpi.ca/ergast/f1"

TEAM_COLORS = {
    "mclaren": "#FF8000", "ferrari": "#E8002D", "red_bull": "#3671C6", "mercedes": "#27F4D2",
    "aston_martin": "#229971", "williams": "#64C4FF", "rb": "#6692FF", "racing_bulls": "#6692FF",
    "haas": "#B6BABD", "sauber": "#BB0A30", "audi": "#BB0A30", "alpine": "#0093CC",
    "cadillac": "#C0C0C0",
    # older team names, for classic races
    "alphatauri": "#4E7C9B", "toro_rosso": "#469BFF", "alfa": "#9B0000", "racing_point": "#F596C8",
    "force_india": "#F596C8", "renault": "#FFF500", "lotus_f1": "#FFB800", "manor": "#ED1C24",
    "marussia": "#6E0000", "caterham": "#005030", "virgin": "#CC0000", "hrt": "#B2945E",
    "brawn": "#B8FD6E", "toyota": "#CC0000", "bmw_sauber": "#2C5FA8", "honda": "#FFFFFF",
    "super_aguri": "#E2001A", "spyker": "#FF6600", "jordan": "#F5E32D", "minardi": "#191919",
    "jaguar": "#00573F", "bar": "#E8E8E8", "prost": "#0033A0", "arrows": "#FF8000",
    "benetton": "#00A0E3", "stewart": "#FFFFFF", "tyrrell": "#003399",
}


def _get(path: str, params: str = "") -> dict:
    url = f"{BASE}/{path}.json?{params}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "race-in-30/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)["MRData"]
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def _all_laps(year: int, rnd: int) -> list[dict]:
    laps: dict[int, list] = {}
    offset, limit = 0, 100
    while True:
        data = _get(f"{year}/{rnd}/laps", f"limit={limit}&offset={offset}")
        races = data.get("RaceTable", {}).get("Races", [])
        if races:
            for lap in races[0].get("Laps", []):
                laps.setdefault(int(lap["number"]), []).extend(lap.get("Timings", []))
        total = int(data.get("total", 0))
        offset += limit
        if offset >= total:
            break
        time.sleep(0.3)  # stay well inside the rate limit
    return [{"number": n, "Timings": laps[n]} for n in sorted(laps)]


def build_race(results_mr: dict, laps: list[dict], year: int, rnd: int, session: str) -> dict | None:
    races = results_mr.get("RaceTable", {}).get("Races", [])
    if not races or not laps:
        return None
    race = races[0]
    results = race.get("Results", [])
    total = max(l["number"] for l in laps)
    n_cars = len(results)
    by_id: dict[str, dict[int, int]] = {}
    for lap in laps:
        for t in lap["Timings"]:
            by_id.setdefault(t["driverId"], {})[lap["number"]] = int(t["position"])

    drivers, fastest = [], None
    for r in results:
        d, c = r["Driver"], r["Constructor"]
        did = d["driverId"]
        grid = int(r.get("grid") or 0) or n_cars
        classified = str(r.get("positionText", "")).isdigit()
        finish = int(r["position"]) if classified else None
        pos: list[int | None] = [None] * (total + 1)
        pos[0] = grid
        for n, p in by_id.get(did, {}).items():
            pos[n] = p
        last = max((i for i, p in enumerate(pos) if p is not None), default=0)
        end = total if classified else last
        for i in range(1, end + 1):
            if pos[i] is None:
                pos[i] = pos[i - 1] if pos[i - 1] is not None else (finish or grid)
        if classified and finish:
            pos[total] = finish
        code = d.get("code") or d["familyName"][:3].upper()
        drivers.append({
            "code": code, "name": f"{d['givenName']} {d['familyName']}", "last": d["familyName"],
            "team": c["name"], "color": TEAM_COLORS.get(c["constructorId"], "#9AA0A6"),
            "grid": grid, "finish": finish, "status": r.get("status", ""),
            "classified": classified, "positions": pos,
        })
        fl = r.get("FastestLap")
        if fl and str(fl.get("rank")) == "1" and fl.get("Time", {}).get("time"):
            fastest = {"code": code, "time": fl["Time"]["time"], "lap": int(fl.get("lap", 0))}

    return {"event": race["raceName"], "year": year, "round": rnd, "session": session,
            "total_laps": total, "drivers": drivers, "fastest_lap": fastest}


def load_session(year: int, rnd: int, session: str) -> dict | None:
    if session != "Race":
        return None
    results = _get(f"{year}/{rnd}/results", "limit=100")
    laps = _all_laps(year, rnd)
    return build_race(results, laps, year, rnd, session)
