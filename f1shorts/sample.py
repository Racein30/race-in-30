"""Synthetic race for previews and tests. Clearly labelled; never uploaded."""
from __future__ import annotations

import random

GRID = [  # code, first, last, team, colour
    ("NOR", "Lando", "Norris", "McLaren", "#FF8000"), ("PIA", "Oscar", "Piastri", "McLaren", "#FF8000"),
    ("VER", "Max", "Verstappen", "Red Bull Racing", "#3671C6"), ("HAD", "Isack", "Hadjar", "Red Bull Racing", "#3671C6"),
    ("LEC", "Charles", "Leclerc", "Ferrari", "#E8002D"), ("HAM", "Lewis", "Hamilton", "Ferrari", "#E8002D"),
    ("RUS", "George", "Russell", "Mercedes", "#27F4D2"), ("ANT", "Kimi", "Antonelli", "Mercedes", "#27F4D2"),
    ("ALO", "Fernando", "Alonso", "Aston Martin", "#229971"), ("STR", "Lance", "Stroll", "Aston Martin", "#229971"),
    ("ALB", "Alex", "Albon", "Williams", "#64C4FF"), ("SAI", "Carlos", "Sainz", "Williams", "#64C4FF"),
    ("LAW", "Liam", "Lawson", "Racing Bulls", "#6692FF"), ("LIN", "Arvid", "Lindblad", "Racing Bulls", "#6692FF"),
    ("OCO", "Esteban", "Ocon", "Haas F1 Team", "#B6BABD"), ("BEA", "Oliver", "Bearman", "Haas F1 Team", "#B6BABD"),
    ("HUL", "Nico", "Hulkenberg", "Audi", "#BB0A30"), ("BOR", "Gabriel", "Bortoleto", "Audi", "#BB0A30"),
    ("GAS", "Pierre", "Gasly", "Alpine", "#0093CC"), ("COL", "Franco", "Colapinto", "Alpine", "#0093CC"),
    ("PER", "Sergio", "Perez", "Cadillac", "#C0C0C0"), ("BOT", "Valtteri", "Bottas", "Cadillac", "#C0C0C0"),
]


def sample_race(seed: int = 7, laps: int = 58) -> dict:
    rnd = random.Random(seed)
    order = [g[0] for g in GRID]
    pace = {c: rnd.gauss(0, 1) - i * 0.06 for i, c in enumerate(order)}
    order.sort(key=lambda c: -(pace[c] + rnd.gauss(0, 0.8)))  # qualifying
    grid = {c: i + 1 for i, c in enumerate(order)}
    pit_lap = {c: rnd.randint(16, 30) for c in order}
    out_lap = {order[-4]: 9, order[6]: 37}
    history = {c: [grid[c]] for c in order}
    running = list(order)
    for lap in range(1, laps + 1):
        running = [c for c in running if out_lap.get(c, 10**9) > lap]
        # pace-weighted overtakes between neighbours
        for _ in range(3):
            for i in range(len(running) - 1, 0, -1):
                a, b = running[i], running[i - 1]
                if pace[a] - pace[b] > rnd.gauss(0.9, 0.6):
                    running[i], running[i - 1] = b, a
        for c in [c for c in running if pit_lap[c] == lap]:
            i = running.index(c)
            j = min(len(running) - 1, i + rnd.randint(3, 6))
            running.insert(j, running.pop(i))
        for i, c in enumerate(running):
            history[c].append(i + 1)
        for c in order:
            if c not in running and len(history[c]) <= lap:
                history[c].append(None)
    drivers = []
    info = {g[0]: g for g in GRID}
    for c in order:
        code, first, last, team, colour = info[c]
        fin = history[c][-1]
        drivers.append({"code": code, "name": f"{first} {last}", "last": last, "team": team,
                        "color": colour, "grid": grid[c], "finish": fin,
                        "status": "Finished" if fin else "Retired", "classified": fin is not None,
                        "positions": history[c]})
    fast = min((d for d in drivers if d["classified"]), key=lambda d: pace[d["code"]] * -1)
    return {"event": "Sample Grand Prix", "year": 2026, "round": 0, "session": "Race",
            "total_laps": laps, "drivers": drivers,
            "fastest_lap": {"code": fast["code"], "time": "1:33.482", "lap": 51}, "sample": True}
