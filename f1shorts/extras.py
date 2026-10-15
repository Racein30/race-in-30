"""Extra formats built from the Jolpica API: championship race, title maths,
teammate battles, race preview, and daily classic races."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .jolpica import TEAM_COLORS, _get

RACE_PTS, SPRINT_PTS = 25, 8


# ---------------------------------------------------------------- data helpers
def _paged(path: str, key: str) -> list[dict]:
    """Fetch every page of a season endpoint, merging rows per round."""
    races: dict[int, dict] = {}
    offset = 0
    while True:
        mr = _get(path, f"limit=100&offset={offset}")
        for r in mr.get("RaceTable", {}).get("Races", []):
            rnd = int(r["round"])
            if rnd not in races:
                races[rnd] = {**r, key: []}
            races[rnd][key].extend(r.get(key, []))
        offset += 100
        if offset >= int(mr.get("total", 0)):
            break
    return [races[k] for k in sorted(races)]


def _code(d: dict) -> str:
    return d.get("code") or d["familyName"][:3].upper()


def _color(cid: str) -> str:
    return TEAM_COLORS.get(cid, "#9AA0A6")


def schedule(year: int) -> list[dict]:
    return _get(str(year), "limit=100").get("RaceTable", {}).get("Races", [])


def _race_dt(r: dict) -> datetime:
    t = (r.get("time") or "12:00:00Z").rstrip("Z")
    return datetime.fromisoformat(f"{r['date']}T{t}").replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- championship
def championship(year: int) -> dict | None:
    results = _paged(f"{year}/results", "Results")
    if not results:
        return None
    sprints = {int(r["round"]): r for r in _paged(f"{year}/sprint", "SprintResults")}
    drivers: dict[str, dict] = {}
    rounds = []
    for race in results:
        rnd = int(race["round"])
        rounds.append({"round": rnd, "name": race["raceName"].replace("Grand Prix", "GP")})
        gained: dict[str, float] = {}
        rows = list(race["Results"]) + list(sprints.get(rnd, {}).get("SprintResults", []))
        for row in rows:
            d = row["Driver"]
            did = d["driverId"]
            if did not in drivers:
                drivers[did] = {"id": did, "code": _code(d), "last": d["familyName"],
                                "name": f"{d['givenName']} {d['familyName']}", "url": d.get("url", ""),
                                "color": _color(row["Constructor"]["constructorId"]),
                                "team": row["Constructor"]["name"], "cum": []}
            drivers[did]["color"] = _color(row["Constructor"]["constructorId"])
            gained[did] = gained.get(did, 0.0) + float(row.get("points", 0) or 0)
        for did, dr in drivers.items():
            prev = dr["cum"][-1] if dr["cum"] else 0.0
            dr["cum"] += [prev] * (len(rounds) - 1 - len(dr["cum"]))  # joined mid-season
            dr["cum"].append(prev + gained.get(did, 0.0))
    total_rounds = len(schedule(year)) or len(rounds)
    return {"year": year, "rounds": rounds, "drivers": list(drivers.values()),
            "complete": len(rounds) >= total_rounds}


def pts(x: float) -> str:
    return f"{x:g}"


def championship_story(c: dict, seed: int) -> tuple[list[str], dict]:
    rnd = random.Random(seed)
    n = len(c["rounds"])
    order = sorted(c["drivers"], key=lambda d: -d["cum"][-1])
    l, p2, p3 = order[0], order[1], order[2]
    leaders = [max(c["drivers"], key=lambda d: d["cum"][i])["last"] for i in range(n)]
    changes = sum(1 for a, b in zip(leaders, leaders[1:]) if a != b)
    since = n - next((i for i, x in enumerate(reversed(leaders)) if x != l["last"]), n) + 1
    gap = l["cum"][-1] - p2["cum"][-1]
    finished = c.get("complete", False)
    s = [rnd.choice([f"The {c['year']} title fight, race by race.",
                     f"{n} rounds of the {c['year']} championship in thirty seconds."])]
    if changes == 0:
        s.append(f"{l['last']} has led after every single round.")
    elif since > 1:
        s.append(f"The lead changed hands {changes} times. {l['last']} has led since round {since}.")
    else:
        s.append(f"The lead changed hands {changes} times.")
    verb = "won it" if finished else "leads"
    s.append(f"{l['last']} {verb} on {pts(l['cum'][-1])} points, {pts(gap)} clear of {p2['last']}."
             if gap > 0 else f"{l['last']} and {p2['last']} are level on points.")
    s.append(f"{p3['last']} {'finished' if finished else 'is'} third, {pts(l['cum'][-1] - p3['cum'][-1])} points back.")
    s.append("Follow for the title run-in." if not finished else "Follow for more title fights.")
    title = (f"The {c['year']} F1 Title Fight in 30 Seconds 🏆 {l['last']} vs {p2['last']} #F1 #Shorts")
    desc = "\n".join([f"Every round of the {c['year']} Formula 1 drivers' championship, animated.", "",
                      *[f"P{i+1}: {d['name']} ({pts(d['cum'][-1])} pts)" for i, d in enumerate(order[:5])], "",
                      "Data: Jolpica F1 API (Ergast-compatible).",
                      "Unofficial fan channel, not affiliated with Formula 1 or the FIA.", "",
                      "#F1 #Formula1 #Shorts #F1Data"])
    tags = ["F1", "Formula 1", f"{c['year']} F1", "F1 championship", "F1 title fight", l["last"], p2["last"],
            "Shorts"]
    return s, {"title": title[:100], "description": desc, "tags": tags}


# ---------------------------------------------------------------- title maths
def title_maths(year: int, now: datetime | None = None) -> dict | None:
    c = championship(year)
    if not c:
        return None
    done_rounds = {r["round"] for r in c["rounds"]}
    sprint_done = {int(r["round"]) for r in _paged(f"{year}/sprint", "SprintResults")}
    races_left = sprints_left = 0
    for r in schedule(year):
        rn = int(r["round"])
        if rn not in done_rounds:
            races_left += 1
        if "Sprint" in r and rn not in sprint_done:
            sprints_left += 1
    if races_left == 0:
        return None
    maxp = races_left * RACE_PTS + sprints_left * SPRINT_PTS
    order = sorted(c["drivers"], key=lambda d: -d["cum"][-1])
    lead = order[0]["cum"][-1]
    rows = []
    for d in order[:7]:
        pts = d["cum"][-1]
        rows.append({**d, "pts": pts, "gap": lead - pts, "alive": pts + maxp >= lead})
    # keep everyone still alive plus up to two who are out, max 7
    alive = [r for r in rows if r["alive"]]
    out = [r for r in rows if not r["alive"]][:max(0, min(2, 7 - len(alive)))]
    return {"year": year, "races_left": races_left, "sprints_left": sprints_left, "max": maxp,
            "rows": alive + out, "round": max(done_rounds), "complete_rounds": len(done_rounds)}


def title_story(t: dict, seed: int) -> tuple[list[str], dict]:
    rows = t["rows"]
    l = rows[0]
    alive = [r for r in rows[1:] if r["alive"]]
    out = [r for r in rows[1:] if not r["alive"]]
    left = f"{t['races_left']} race{'s' if t['races_left'] != 1 else ''}"
    if t["sprints_left"]:
        left += f" and {t['sprints_left']} sprint{'s' if t['sprints_left'] != 1 else ''}"
    s = [f"Can anyone still catch {l['last']}?",
         f"{left} to go, {t['max']} points still on the table.",
         f"{l['last']} leads on {pts(l['pts'])}."]
    if not alive:
        s.append(f"Nobody can catch {l['last']} now. The title is decided.")
    else:
        for r in alive[:2]:
            s.append(f"{r['last']} is {pts(r['gap'])} behind and still in it.")
        if len(alive) > 2:
            s.append(f"{len(alive)} drivers can still mathematically win it.")
    if out and alive:
        s.append(f"{out[0]['last']} is mathematically out.")
    s.append("Who wins it? Tell me in the comments.")
    title = f"Can Anyone Still Catch {l['last']}? {t['year']} F1 Title Maths 🧮 #F1 #Shorts"
    desc = "\n".join([f"{t['year']} F1 title maths with {left} remaining ({t['max']} points available).", "",
                      *[f"{r['name']}: {pts(r['pts'])} pts ({'still in it' if r['alive'] else 'out'})"
                        for r in rows], "",
                      "Points: 25 per race win, 8 per sprint win.",
                      "Data: Jolpica F1 API. Unofficial fan channel, not affiliated with Formula 1 or the FIA.",
                      "", "#F1 #Formula1 #Shorts #F1Data"])
    tags = ["F1", "Formula 1", f"{t['year']} F1", "F1 title", "F1 championship maths", l["last"], "Shorts"]
    return s, {"title": title[:100], "description": desc, "tags": tags}


# ---------------------------------------------------------------- teammates
def teammates(year: int) -> dict | None:
    results = _paged(f"{year}/results", "Results")
    if not results:
        return None
    pairs: dict[tuple, dict] = {}
    for race in results:
        by_team: dict[str, list] = {}
        for row in race["Results"]:
            by_team.setdefault(row["Constructor"]["constructorId"], []).append(row)
        for cid, rows in by_team.items():
            if len(rows) != 2:
                continue
            a, b = sorted(rows, key=lambda r: r["Driver"]["driverId"])
            key = (cid, a["Driver"]["driverId"], b["Driver"]["driverId"])
            p = pairs.setdefault(key, {"team": a["Constructor"]["name"], "color": _color(cid),
                                       "a": _code(a["Driver"]), "b": _code(b["Driver"]),
                                       "a_last": a["Driver"]["familyName"],
                                       "b_last": b["Driver"]["familyName"], "aw": 0, "bw": 0})
            if int(a["position"]) < int(b["position"]):
                p["aw"] += 1
            else:
                p["bw"] += 1
    rows = []
    for p in pairs.values():
        if p["aw"] + p["bw"] < 3:
            continue
        if p["bw"] > p["aw"]:  # leader on the left
            p = {**p, "a": p["b"], "b": p["a"], "a_last": p["b_last"], "b_last": p["a_last"],
                 "aw": p["bw"], "bw": p["aw"]}
        rows.append(p)
    rows.sort(key=lambda p: -(p["aw"] - p["bw"]))
    return {"year": year, "rounds": len(results), "rows": rows[:11]} if rows else None


def teammates_story(t: dict, seed: int) -> tuple[list[str], dict]:
    rows = t["rows"]
    top, close = rows[0], min(rows, key=lambda p: (p["aw"] - p["bw"], -(p["aw"] + p["bw"])))
    s = [f"Every {t['year']} teammate battle, race by race.",
         f"Most one-sided: {top['a_last']} leads {top['b_last']} {top['aw']} to {top['bw']}."]
    if close is not top:
        s.append(f"Closest fight: {close['a_last']} and {close['b_last']}, {close['aw']} to {close['bw']}.")
    s.append(f"That's finishing position after {t['rounds']} races.")
    s.append("Who's the biggest surprise? Comment below.")
    title = f"Every {t['year']} F1 Teammate Battle 🥊 Who's Beating Who? #F1 #Shorts"
    desc = "\n".join([f"Race head-to-heads for every {t['year']} F1 team (who finished ahead).", "",
                      *[f"{p['team']}: {p['a_last']} {p['aw']}–{p['bw']} {p['b_last']}" for p in rows], "",
                      "Data: Jolpica F1 API. Unofficial fan channel, not affiliated with Formula 1 or the FIA.",
                      "", "#F1 #Formula1 #Shorts #F1Data"])
    tags = ["F1", "Formula 1", f"{t['year']} F1", "F1 teammates", "head to head", "Shorts"]
    return s, {"title": title[:100], "description": desc, "tags": tags}


# ---------------------------------------------------------------- preview
def preview(year: int, now: datetime | None = None, max_days: float = 3.0) -> dict | None:
    now = now or datetime.now(timezone.utc)
    upcoming = [r for r in schedule(year) if _race_dt(r) > now]
    if not upcoming:
        return None
    nxt = upcoming[0]
    if _race_dt(nxt) - now > timedelta(days=max_days):
        return None
    cid = nxt["Circuit"]["circuitId"]
    races = _get(f"circuits/{cid}/results/1", "limit=100").get("RaceTable", {}).get("Races", [])
    races = sorted(races, key=lambda r: int(r["season"]), reverse=True)
    if not races:
        return None
    winners = []
    for r in races[:5]:
        w = r["Results"][0]
        winners.append({"season": int(r["season"]), "last": w["Driver"]["familyName"], "code": _code(w["Driver"]),
                        "team": w["Constructor"]["name"], "color": _color(w["Constructor"]["constructorId"])})
    counts: dict[str, int] = {}
    for r in races:
        n = r["Results"][0]["Driver"]["familyName"]
        counts[n] = counts.get(n, 0) + 1
    king = max(counts.items(), key=lambda kv: kv[1])
    return {"year": year, "round": int(nxt["round"]), "name": nxt["raceName"], "circuit": nxt["Circuit"]["circuitName"],
            "date": _race_dt(nxt), "winners": winners, "king": king, "since": int(races[-1]["season"])}


def preview_story(p: dict, seed: int) -> tuple[list[str], dict]:
    gp = p["name"].replace("Grand Prix", "GP")
    w = p["winners"]
    s = [f"Next up: the {gp}. Here are the last five winners."]
    if w[0]["season"] == p["year"] - 1:
        s.append(f"{w[0]['last']} won here last year.")
    rep = {}
    for x in w:
        rep[x["last"]] = rep.get(x["last"], 0) + 1
    top = max(rep.items(), key=lambda kv: kv[1])
    if top[1] >= 2:
        s.append(f"{top[0]} has won {top[1]} of the last five.")
    if p["king"][1] >= 3:
        s.append(f"The record here belongs to {p['king'][0]}, with {p['king'][1]} wins.")
    s.append(f"Lights out on {p['date'].strftime('%A')}.")
    s.append("Who's your pick? Comment below.")
    title = f"{gp} {p['year']} Preview: The Last 5 Winners 🏁 #F1 #Shorts"
    desc = "\n".join([f"Who won the last five {p['name']}s at {p['circuit']}?", "",
                      *[f"{x['season']}: {x['last']} ({x['team']})" for x in w], "",
                      "Data: Jolpica F1 API. Unofficial fan channel, not affiliated with Formula 1 or the FIA.",
                      "", "#F1 #Formula1 #Shorts #F1Data"])
    tags = ["F1", "Formula 1", p["name"], f"{p['year']} F1", "F1 preview", "Shorts"]
    return s, {"title": title[:100], "description": desc, "tags": tags}


# ---------------------------------------------------------------- classics
CLASSICS = [  # (season, circuitId) - famous races, posted one per day
    (2008, "interlagos"), (2016, "interlagos"), (2021, "silverstone"), (2011, "villeneuve"),
    (2019, "hockenheimring"), (2020, "monza"), (2012, "interlagos"), (2021, "hungaroring"),
    (2010, "yas_marina"), (2024, "interlagos"), (2021, "jeddah"), (2005, "suzuka"),
    (2014, "bahrain"), (2017, "baku"), (2020, "istanbul"), (2016, "catalunya"), (2012, "valencia"),
    (2021, "sochi"), (2007, "interlagos"), (1998, "spa"), (2003, "interlagos"), (2018, "hockenheimring"),
    (2019, "interlagos"), (2010, "albert_park"), (2012, "sepang"),
]


def classic_round(season: int, circuit: str) -> int | None:
    for r in schedule(season):
        if r["Circuit"]["circuitId"] == circuit:
            return int(r["round"])
    return None
