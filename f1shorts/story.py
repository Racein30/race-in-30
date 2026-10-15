"""Turn race data into facts, a narration script, and YouTube metadata."""
from __future__ import annotations

import json
import os
import random
import re

import urllib.request


def facts(race: dict) -> dict:
    drv = race["drivers"]
    by_code = {d["code"]: d for d in drv}
    total = race["total_laps"]
    finishers = sorted([d for d in drv if d["classified"] and d["finish"]], key=lambda d: d["finish"])
    podium = finishers[:3]
    winner = podium[0] if podium else None

    # leader on each lap
    leaders = []
    for lap in range(1, total + 1):
        lead = next((d["code"] for d in drv if d["positions"][lap] == 1), None)
        leaders.append(lead)
    changes = sum(1 for a, b in zip(leaders, leaders[1:]) if a and b and a != b)
    led_laps: dict[str, int] = {}
    for c in leaders:
        if c:
            led_laps[c] = led_laps.get(c, 0) + 1

    took_lead_lap = None
    if winner:
        took_lead_lap = 1
        for i, c in enumerate(leaders, start=1):
            if c != winner["code"]:
                took_lead_lap = i + 1

    gains = [(d["grid"] - d["finish"], d) for d in finishers]
    gains.sort(key=lambda g: -g[0])
    win_code = winner["code"] if winner else None
    gainer = next((g for g in gains if g[0] >= 3 and g[1]["code"] != win_code), None)
    loser = gains[-1] if gains and gains[-1][0] <= -3 else None

    dnfs = [d for d in drv if not d["classified"]]
    pole = next((d for d in drv if d["grid"] == 1), None)
    fl = race.get("fastest_lap")

    return {
        "event": race["event"], "year": race["year"], "session": race["session"],
        "total_laps": total,
        "winner": winner and {"name": winner["name"], "last": winner["last"], "team": winner["team"],
                              "grid": winner["grid"], "took_lead_lap": took_lead_lap},
        "podium": [{"pos": d["finish"], "name": d["name"], "last": d["last"], "team": d["team"]} for d in podium],
        "pole": pole and {"name": pole["name"], "last": pole["last"], "finish": pole["finish"],
                          "classified": pole["classified"]},
        "lead_changes": changes,
        "laps_led": {by_code[c]["last"]: n for c, n in sorted(led_laps.items(), key=lambda x: -x[1])},
        "biggest_gainer": gainer and {"name": gainer[1]["name"], "last": gainer[1]["last"], "places": gainer[0],
                                      "grid": gainer[1]["grid"], "finish": gainer[1]["finish"]},
        "biggest_loser": loser and {"name": loser[1]["name"], "last": loser[1]["last"], "places": -loser[0],
                                    "grid": loser[1]["grid"], "finish": loser[1]["finish"]},
        "retirements": [{"name": d["name"], "last": d["last"], "status": d["status"]} for d in dnfs],
        "fastest_lap": fl and {"name": by_code.get(fl["code"], {}).get("name", fl["code"]),
                               "last": by_code.get(fl["code"], {}).get("last", fl["code"]),
                               "time": fl["time"], "lap": fl["lap"]},
    }


def _short_event(f: dict) -> str:
    name = f["event"].replace("Grand Prix", "GP")
    return f"{name} Sprint" if f["session"] == "Sprint" else name


def template_script(f: dict, seed: int = 0) -> list[str]:
    """Data-driven narration, ~75-95 words. Each item is one caption."""
    rnd = random.Random(seed)
    w, pod = f["winner"], f["podium"]
    s = [rnd.choice([
        f"The {_short_event(f)}, the whole race in thirty seconds.",
        f"{f['total_laps']} laps of the {_short_event(f)} in thirty seconds.",
    ])]
    if w:
        if w["grid"] == 1 and f["lead_changes"] == 0:
            s.append(f"{w['last']} started on pole and led every single lap.")
        elif w["grid"] == 1:
            s.append(f"{w['last']} turned pole into victory, through {f['lead_changes']} lead changes.")
        else:
            lap = w["took_lead_lap"]
            s.append(f"{w['last']} won from P{w['grid']}, taking the lead for good on lap {lap}."
                     if lap and lap > 1 else f"{w['last']} won from P{w['grid']}, leading from lap one.")
            if f["pole"] and f["pole"]["last"] != w["last"]:
                p = f["pole"]
                s.append(f"Polesitter {p['last']} " + (f"finished P{p['finish']}." if p["classified"] else "did not finish."))
    if len(pod) >= 3:
        s.append(f"{pod[1]['last']} and {pod[2]['last']} completed the podium.")
    if f["biggest_gainer"]:
        g = f["biggest_gainer"]
        s.append(f"Biggest mover: {g['last']}, up {g['places']} places from P{g['grid']} to P{g['finish']}.")
    if f["biggest_loser"] and len(s) < 6 and not (f["pole"] and f["pole"]["last"] == f["biggest_loser"]["last"]):
        l = f["biggest_loser"]
        s.append(f"{l['last']} dropped {l['places']} places to P{l['finish']}.")
    r = f["retirements"]
    if len(r) == 1:
        s.append(f"One retirement: {r[0]['last']}.")
    elif len(r) > 1:
        s.append(f"{len(r)} cars failed to finish, including {r[0]['last']}.")
    if f["fastest_lap"] and len(s) < 7:
        m, sec = f["fastest_lap"]["time"].split(":")
        s.append(f"Fastest lap: {f['fastest_lap']['last']}, {int(m)} minute {sec}.")
    s.append(rnd.choice(["Follow for every race in thirty seconds.",
                         "Follow so you never miss a race."]))
    return s


def template_metadata(f: dict) -> dict:
    ev = _short_event(f)
    w = f["winner"]["last"] if f["winner"] else ""
    title = f"{ev} {f['year']} in 30 Seconds 🏁 {w} wins #F1 #Shorts"
    if len(title) > 100:
        title = f"{ev} {f['year']} in 30s 🏁 #F1 #Shorts"
    lines = [f"The {f['year']} {ev} in 30 seconds, built from official timing data.", ""]
    for p in f["podium"]:
        lines.append(f"P{p['pos']}: {p['name']} ({p['team']})")
    if f["biggest_gainer"]:
        g = f["biggest_gainer"]
        lines.append(f"Biggest gainer: {g['name']} (+{g['places']})")
    if f["fastest_lap"]:
        lines.append(f"Fastest lap: {f['fastest_lap']['name']} {f['fastest_lap']['time']}")
    lines += ["", "Data: official F1 live timing via the open-source FastF1 library.",
              "Unofficial fan channel, not affiliated with Formula 1 or the FIA.",
              "", "#F1 #Formula1 #Shorts #F1Data"]
    tags = ["F1", "Formula 1", f"{f['event']}", f"{f['year']} F1", "F1 data", "F1 highlights",
            "race recap", "Shorts"] + [p["last"] for p in f["podium"]]
    return {"title": title, "description": "\n".join(lines), "tags": tags}


def claude_script(f: dict) -> tuple[list[str], dict] | None:
    """Optional: a more natural script from Claude, using only the given facts."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    prompt = (
        "You write narration for a 30-second vertical F1 data video (an animated position chart). "
        "Use ONLY the facts in this JSON; never invent incidents, causes, quotes or numbers.\n\n"
        f"{json.dumps(f)}\n\n"
        "Return JSON only, no prose, with keys:\n"
        '"sentences": 5-7 short punchy sentences, 70-95 words total, spoken British-commentator style, '
        "first sentence a hook naming the race, last sentence a short follow call-to-action;\n"
        '"title": YouTube title under 90 characters ending with "#F1 #Shorts";\n'
        '"description": 3-6 lines summarising the result, then the line '
        '"Data: official F1 live timing via FastF1. Unofficial fan channel, not affiliated with Formula 1.";\n'
        '"tags": 8-12 tags.'
    )
    body = json.dumps({"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 1200,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = json.load(resp)["content"][0]["text"]
        data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        sents = [s.strip() for s in data["sentences"] if s.strip()]
        words = sum(len(s.split()) for s in sents)
        if not (4 <= len(sents) <= 8 and 50 <= words <= 120) or len(data["title"]) > 100:
            return None
        meta = {"title": data["title"], "description": data["description"],
                "tags": [str(t)[:30] for t in data["tags"]][:15]}
        return sents, meta
    except Exception as e:  # any failure -> template fallback
        print(f"[story] Claude script failed, using template: {e}")
        return None


def build(race: dict) -> tuple[dict, list[str], dict]:
    f = facts(race)
    seed = race["year"] * 100 + race["round"]
    got = claude_script(f)
    if got:
        return f, got[0], got[1]
    return f, template_script(f, seed), template_metadata(f)
