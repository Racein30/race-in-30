"""Render a 1080x1920 'race in 30 seconds' Short from a race dict."""
from __future__ import annotations

import math
import subprocess
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

W, H, FPS = 1080, 1920, 30
BG, FG, MUTED, FAINT, ACCENT = "#0B0D12", "#F2F4F7", "#8A93A3", "#1A1F29", "#FF2E3B"
FONT = "DejaVu Sans"  # bundled with matplotlib, so identical everywhere
INTRO, OUTRO = 1.6, 4.8

plt.rcParams["font.family"] = FONT


def _ink_on(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return "#0B0D12" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "#FFFFFF"


def _smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def caption_at(captions: list[dict], t: float) -> str:
    for c in captions:
        if c["start"] <= t < c["end"]:
            return c["text"]
    return ""


def render(race: dict, captions: list[dict], out_path: str, audio_path: str | None = None,
           duration: float | None = None, handle: str = "", facts: dict | None = None,
           photos: dict | None = None, hero: dict | None = None) -> str:
    total = race["total_laps"]
    drivers = sorted(race["drivers"], key=lambda d: (d["finish"] is None, d["finish"] or 99, d["grid"]))
    n = len(drivers)
    if duration is None:
        duration = (captions[-1]["end"] + 0.8) if captions else 30.0
    duration = float(min(58.0, max(24.0, duration)))
    race_t = duration - INTRO - OUTRO
    frames = int(round(duration * FPS))

    podium = [d for d in drivers if d["classified"]][:3]
    gainer_code = None
    if facts and facts.get("biggest_gainer"):
        gainer_code = next((d["code"] for d in drivers if d["last"] == facts["biggest_gainer"]["last"]), None)
    highlight = {d["code"] for d in podium} | ({gainer_code} if gainer_code else set())

    pos = {d["code"]: np.array([np.nan if p is None else p for p in d["positions"]], dtype=float)
           for d in drivers}

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.12, 0.365, 0.68, 0.465])
    ax.set_facecolor(BG)
    ax.set_xlim(0, total)
    ax.set_ylim(n + 0.7, 0.3)
    ax.set_yticks(range(1, n + 1))
    ax.set_yticklabels([f"P{i}" for i in range(1, n + 1)], color=MUTED, fontsize=13, fontweight="bold")
    ticks = sorted({0, total} | {round(total * q) for q in (0.25, 0.5, 0.75)})
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks], color=MUTED, fontsize=15)
    ax.tick_params(length=0, pad=8)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(1, n + 1):
        ax.axhline(i, color=FAINT, lw=1, zorder=0)

    artists = {}
    for d in drivers:
        hi = d["code"] in highlight
        line, = ax.plot([], [], color=d["color"], lw=5.5 if hi else 2.6, alpha=1.0 if hi else 0.5,
                        solid_capstyle="round", solid_joinstyle="round", zorder=4 if hi else 2)
        if hi:
            line.set_path_effects([pe.Stroke(linewidth=9, foreground=BG), pe.Normal()])
        dot, = ax.plot([], [], "o", color=d["color"], ms=11 if hi else 8, zorder=5,
                       markeredgecolor=BG, markeredgewidth=2)
        lbl = ax.text(0, 0, d["code"], color=d["color"], fontsize=17 if hi else 14,
                      fontweight="bold", va="center", ha="left", clip_on=False, zorder=6,
                      alpha=1.0 if hi else 0.8)
        lbl.set_path_effects([pe.withStroke(linewidth=4, foreground=BG)])
        out, = ax.plot([], [], "x", color=d["color"], ms=12, mew=3, zorder=5, alpha=0.9)
        artists[d["code"]] = (line, dot, lbl, out)

    # header
    if handle:
        fig.text(0.06, 0.972, handle, color=MUTED, fontsize=22, fontweight="bold", va="center")
    title = race["event"].replace("Grand Prix", "GP").upper()
    if race["session"] == "Sprint":
        title += " SPRINT"
    fig.text(0.5, 0.935, f"{title} {race['year']}", color=FG, fontsize=50 if len(title) < 18 else 40,
             fontweight="bold", ha="center", va="center")
    fig.text(0.5, 0.900, "THE RACE IN 30 SECONDS", color=ACCENT, fontsize=27, fontweight="bold",
             ha="center", va="center")
    lap_txt = fig.text(0.5, 0.862, "", color=FG, fontsize=36, fontweight="bold", ha="center",
                       va="center", family="DejaVu Sans Mono")
    if race.get("sample"):
        fig.text(0.94, 0.972, "SAMPLE DATA", color=ACCENT, fontsize=18, fontweight="bold",
                 ha="right", va="center")

    leader_lbl = fig.text(0.5, 0.322, "", color=FG, fontsize=30, fontweight="bold", ha="center", va="center")
    cap = fig.text(0.5, 0.245, "", color=FG, fontsize=50, fontweight="bold", ha="center", va="center",
                   linespacing=1.15)
    cap.set_path_effects([pe.withStroke(linewidth=10, foreground="#000000")])

    # outro card (fades in)
    card = []
    box = FancyBboxPatch((0.07, 0.39), 0.86, 0.43, boxstyle="round,pad=0,rounding_size=0.025",
                         transform=fig.transFigure, facecolor="#11151D", edgecolor="#2A303C", lw=2, zorder=20)
    fig.patches.append(box)
    card.append(box)
    rows_y = 0.775
    def ctext(x, y, s, **kw):
        t = fig.text(x, y, s, zorder=21, va="center", **kw)
        card.append(t)
        return t
    photos = photos or {}

    def cimg(img, x, y, w):
        a = fig.add_axes([x - w / 2, y - w * W / H / 2, w, w * W / H], zorder=22)
        a.imshow(img)
        a.axis("off")
        card.append(a)

    if podium:
        w = podium[0]
        if photos.get(w["code"]) is not None:
            cimg(photos[w["code"]], 0.5, 0.748, 0.15)
            ny = 0.668
        else:
            ctext(0.5, rows_y, "WINNER", color=MUTED, fontsize=26, fontweight="bold", ha="center")
            ny = rows_y - 0.048
        ctext(0.5, ny, w["last"].upper(), color=w["color"], fontsize=72, fontweight="bold", ha="center")
        ctext(0.5, ny - 0.044, f"WINNER · {w['team']} · from P{w['grid']}", color=FG, fontsize=24, ha="center")
        y = ny - 0.10
        for d in podium[1:]:
            ctext(0.12, y, f"P{d['finish']}", color=MUTED, fontsize=34, fontweight="bold", ha="left")
            nx = 0.27
            if photos.get(d["code"]) is not None:
                cimg(photos[d["code"]], 0.285, y, 0.07)
                nx = 0.34
            ctext(nx, y, d["last"].upper(), color=d["color"], fontsize=40, fontweight="bold", ha="left")
            y -= 0.052
        extra = []
        if facts and facts.get("biggest_gainer"):
            g = facts["biggest_gainer"]
            extra.append((f"+{g['places']}", f"{g['last'].upper()}  P{g['grid']} → P{g['finish']}"))
        if facts and facts.get("fastest_lap"):
            extra.append(("FL", f"{facts['fastest_lap']['last'].upper()}  {facts['fastest_lap']['time']}"))
        for k, v in extra[:2]:
            ctext(0.14, y, k, color="#3DDC84" if k.startswith("+") else "#C084FC", fontsize=30,
                  fontweight="bold", ha="left")
            ctext(0.27, y, v, color=FG, fontsize=30, fontweight="bold", ha="left")
            y -= 0.045
    for a in card:
        a.set_visible(False)
    hero_obj = None
    if hero:
        from .hero import Hero
        hero_obj = Hero(fig, outro_from=duration - OUTRO, **hero)
        cap.set_zorder(60)

    def lap_of(t: float) -> float:
        if t <= INTRO:
            return 0.0
        return total * min(1.0, (t - INTRO) / race_t)

    def leader_at(lap: float):
        k = min(total, int(math.floor(lap)))
        for d in drivers:
            if pos[d["code"]][k] == 1:
                return d
        return None

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if audio_path:
        cmd += ["-i", audio_path, "-map", "0:v", "-map", "1:a", "-af", "apad", "-shortest",
                "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for f in range(frames):
        t = f / FPS
        lap = lap_of(t)
        k = int(math.floor(lap))
        frac = lap - k
        for d in drivers:
            line, dot, lbl, out = artists[d["code"]]
            p = pos[d["code"]]
            xs = list(range(0, k + 1))
            ys = list(p[: k + 1])
            if k < total and frac > 0 and not np.isnan(p[k]) and not np.isnan(p[k + 1]):
                xs.append(lap)
                ys.append(p[k] + (p[k + 1] - p[k]) * _smooth(frac))
            arr = np.array(ys, dtype=float)
            valid = ~np.isnan(arr)
            line.set_data(np.array(xs)[valid], arr[valid])
            if valid.any():
                hx, hy = np.array(xs)[valid][-1], arr[valid][-1]
                retired = (not d["classified"]) and (k >= len(p) - 1 or np.isnan(p[min(k + 1, total)])) \
                    and hx < lap - 0.5
                if retired:
                    dot.set_data([], [])
                    out.set_data([hx], [hy])
                    lbl.set_visible(False)
                else:
                    dot.set_data([hx], [hy])
                    out.set_data([], [])
                    lbl.set_visible(True)
                    lbl.set_position((hx + total * 0.018, hy))
            else:
                dot.set_data([], [])
                lbl.set_visible(False)

        lap_txt.set_text(f"LAP {min(total, max(1, math.ceil(lap))) if lap > 0 else 0:>2} / {total}"
                         if lap < total else f"FINISH · {total} LAPS")
        lead = leader_at(max(lap, 1))
        if lead:
            leader_lbl.set_text(f"  LEADER  {lead['last'].upper()}  ")
            leader_lbl.set_color(_ink_on(lead["color"]))
            leader_lbl.set_bbox(dict(boxstyle="round,pad=0.35", facecolor=lead["color"], edgecolor="none"))

        cap.set_text("\n".join(textwrap.wrap(caption_at(captions, t), 22)))

        o = t - (duration - OUTRO)
        if o >= 0:
            a = _smooth(o / 0.45)
            for art in card:
                art.set_visible(True)
                if hasattr(art, "images"):
                    for im in art.images:
                        im.set_alpha(a)
                else:
                    art.set_alpha(a)
            ax.set_alpha(1 - 0.6 * a)
            if hero_obj is not None:
                ax.patch.set_alpha(1 - a)
        if hero_obj is not None:
            hero_obj.update(t, duration)
        fig.canvas.draw()
        proc.stdin.write(fig.canvas.buffer_rgba().tobytes())

    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    plt.close(fig)
    return out_path
