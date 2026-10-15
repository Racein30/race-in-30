"""Vertical renderers for the extra formats (same look as the race video)."""
from __future__ import annotations

import subprocess
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from .render import ACCENT, BG, FAINT, FG, FPS, H, MUTED, W, _ink_on, _smooth, caption_at  # noqa: E402

INTRO, OUTRO = 1.2, 3.0


def _fmt(x: float) -> str:
    return f"{x:g}"


def _frame(title: str, subtitle: str, handle: str):
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    if handle:
        fig.text(0.06, 0.972, handle, color=MUTED, fontsize=22, fontweight="bold", va="center")
    fig.text(0.5, 0.935, title, color=FG, fontsize=50 if len(title) < 20 else 40, fontweight="bold",
             ha="center", va="center")
    fig.text(0.5, 0.900, subtitle, color=ACCENT, fontsize=27, fontweight="bold", ha="center", va="center")
    cap = fig.text(0.5, 0.245, "", color=FG, fontsize=50, fontweight="bold", ha="center", va="center",
                   linespacing=1.15)
    cap.set_path_effects([pe.withStroke(linewidth=10, foreground="#000000")])
    return fig, cap


def _encode(fig, cap, captions, duration, update, out_path, audio_path=None):
    frames = int(round(duration * FPS))
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
        update(t, duration)
        cap.set_text("\n".join(textwrap.wrap(caption_at(captions, t), 22)))
        fig.canvas.draw()
        proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    plt.close(fig)
    return out_path


def _dur(captions, duration):
    if duration is None:
        duration = (captions[-1]["end"] + 0.8) if captions else 30.0
    return float(min(58.0, max(20.0, duration)))


# ------------------------------------------------------------- championship bar race
def championship(c: dict, captions, out_path, audio_path=None, duration=None, handle="", photos=None):
    duration = _dur(captions, duration)
    rounds, drivers = c["rounds"], c["drivers"]
    n = len(rounds)
    top_n = 10
    cum = np.array([[0.0] + d["cum"] for d in drivers])  # index 0 = before round 1
    fig, cap = _frame(f"{c['year']} TITLE FIGHT", "EVERY ROUND IN 30 SECONDS", handle)
    ax = fig.add_axes([0.06, 0.34, 0.80, 0.48])
    ax.set_facecolor(BG)
    ax.set_ylim(top_n + 0.5, 0.4)
    ax.axis("off")
    rnd_txt = fig.text(0.5, 0.858, "", color=FG, fontsize=32, fontweight="bold", ha="center", va="center",
                       family="DejaVu Sans Mono")
    bars, labels, vals, pics = [], [], [], []
    for i, d in enumerate(drivers):
        r = Rectangle((0, 20), 0, 0.72, color=d["color"], zorder=3)
        ax.add_patch(r)
        bars.append(r)
        lab = ax.text(0, 20, f" {d['code']}", color=_ink_on(d["color"]), fontsize=22, fontweight="bold",
                      va="center", ha="left", zorder=4, clip_on=True)
        labels.append(lab)
        v = ax.text(0, 20, "", color=FG, fontsize=22, fontweight="bold", va="center", ha="left", zorder=4)
        vals.append(v)
        img = (photos or {}).get(d["id"])
        if img is not None:
            ab = AnnotationBbox(OffsetImage(img, zoom=0.42), (0, 20), frameon=False, zorder=5,
                                box_alignment=(0.5, 0.5), annotation_clip=False)
            ax.add_artist(ab)
            pics.append((i, ab))
    pic_of = dict(pics)
    race_t = duration - INTRO - OUTRO

    def update(t, dur):
        x = 0.0 if t <= INTRO else min(1.0, (t - INTRO) / race_t) * n
        k = int(np.floor(x))
        fr = _smooth(x - k)
        v = cum[:, k] if k >= n else cum[:, k] + (cum[:, k + 1] - cum[:, k]) * fr
        order = np.argsort(-v, kind="stable")
        rank = np.empty(len(v))
        rank[order] = np.arange(1, len(v) + 1)
        vmax = max(1.0, v[order[0]]) * 1.28
        ax.set_xlim(0, vmax)
        for i in range(len(drivers)):
            y = rank[i] if rank[i] <= top_n else 20
            bars[i].set_xy((0, y - 0.36))
            bars[i].set_width(v[i])
            labels[i].set_position((0, y))
            labels[i].set_visible(v[i] > vmax * 0.09 and rank[i] <= top_n)
            off = vmax * 0.012
            if i in pic_of:
                pic_of[i].xy = (v[i] + vmax * 0.045, y)
                pic_of[i].set_visible(rank[i] <= top_n)
                off = vmax * 0.09
            vals[i].set_position((v[i] + off, y))
            vals[i].set_text(_fmt(round(v[i] * 2) / 2) if rank[i] <= top_n else "")
        r = min(n, max(1, int(np.ceil(x)))) if x > 0 else 0
        rnd_txt.set_text(f"ROUND {r}/{n} · {rounds[r-1]['name'].upper()}" if r else f"{n} ROUNDS")
        if len(rnd_txt.get_text()) > 30:
            rnd_txt.set_fontsize(26)

    return _encode(fig, cap, captions, duration, update, out_path, audio_path)


# ------------------------------------------------------------- title maths
def title_maths(tm: dict, captions, out_path, audio_path=None, duration=None, handle="", photos=None):
    duration = _dur(captions, duration)
    rows = tm["rows"]
    lead = rows[0]["pts"]
    fig, cap = _frame(f"{tm['year']} TITLE MATHS", "CAN ANYONE STILL CATCH THE LEADER?", handle)
    left = f"{tm['races_left']} RACE{'S' if tm['races_left'] != 1 else ''}"
    if tm["sprints_left"]:
        left += f" + {tm['sprints_left']} SPRINT{'S' if tm['sprints_left'] != 1 else ''}"
    fig.text(0.5, 0.858, f"{left} LEFT · {tm['max']} PTS AVAILABLE", color=FG, fontsize=23, fontweight="bold",
             ha="center", va="center")
    ax = fig.add_axes([0.17, 0.35, 0.70, 0.47])
    ax.set_facecolor(BG)
    ax.axis("off")
    n = len(rows)
    ax.set_ylim(n + 0.4, 0.4)
    xmax = max(r["pts"] + tm["max"] for r in rows) * 1.05
    ax.set_xlim(0, xmax)
    ax.axvline(lead, color=FG, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.text(lead, 0.45, " LEADER", color=FG, fontsize=16, fontweight="bold", va="bottom")
    solid, ghost, status = [], [], []
    for i, r in enumerate(rows):
        y = i + 1
        ax.text(-xmax * 0.02, y, r["code"], color=r["color"], fontsize=24, fontweight="bold", ha="right",
                va="center", clip_on=False)
        g = Rectangle((0, y - 0.33), 0, 0.66, facecolor=r["color"], alpha=0.25, edgecolor=r["color"],
                      hatch="//", lw=0, zorder=2)
        s = Rectangle((0, y - 0.33), 0, 0.66, facecolor=r["color"], zorder=3)
        ax.add_patch(g)
        ax.add_patch(s)
        solid.append(s)
        ghost.append(g)
        st = ax.text(0, y, "", fontsize=20, fontweight="bold", va="center", ha="left", zorder=4)
        status.append(st)
    phase1, phase2 = INTRO, INTRO + 0.35 * (duration - INTRO - OUTRO)

    def update(t, dur):
        a = _smooth((t - phase1) / 2.0)
        b = _smooth((t - phase2) / 2.5)
        for i, r in enumerate(rows):
            solid[i].set_width(r["pts"] * a)
            ghost[i].set_x(r["pts"] * a)
            ghost[i].set_width(tm["max"] * b)
            if b > 0.95:
                status[i].set_position((r["pts"] + tm["max"] + xmax * 0.01, i + 1))
                if i == 0:
                    status[i].set_text(f"{_fmt(r['pts'])}")
                    status[i].set_color(FG)
                elif r["alive"]:
                    status[i].set_text(f"-{_fmt(r['gap'])}  IN IT")
                    status[i].set_color("#3DDC84")
                else:
                    status[i].set_text(f"-{_fmt(r['gap'])}  OUT")
                    status[i].set_color(ACCENT)
            elif a > 0.95:
                status[i].set_position((r["pts"] + xmax * 0.01, i + 1))
                status[i].set_text(_fmt(r["pts"]))
                status[i].set_color(FG)

    return _encode(fig, cap, captions, duration, update, out_path, audio_path)


# ------------------------------------------------------------- teammates
def teammates(tm: dict, captions, out_path, audio_path=None, duration=None, handle=""):
    duration = _dur(captions, duration)
    rows = tm["rows"]
    fig, cap = _frame(f"{tm['year']} TEAMMATE WARS", "WHO FINISHED AHEAD MORE OFTEN?", handle)
    fig.text(0.5, 0.858, f"AFTER {tm['rounds']} RACES", color=FG, fontsize=30, fontweight="bold",
             ha="center", va="center")
    top, bottom = 0.83, 0.34
    step = (top - bottom) / len(rows)
    arts = []
    for i, p in enumerate(rows):
        y = top - step * (i + 0.5)
        tot = p["aw"] + p["bw"]
        frac = p["aw"] / tot
        x0, x1 = 0.24, 0.76
        bg = FancyBboxPatch((x0, y - step * 0.3), x1 - x0, step * 0.6, boxstyle="round,pad=0,rounding_size=0.006",
                            transform=fig.transFigure, facecolor=FAINT, edgecolor="none")
        fill = FancyBboxPatch((x0, y - step * 0.3), 0.0001, step * 0.6, boxstyle="round,pad=0,rounding_size=0.006",
                              transform=fig.transFigure, facecolor=p["color"], edgecolor="none")
        fig.patches += [bg, fill]
        la = fig.text(0.22, y, p["a"], color=p["color"], fontsize=26, fontweight="bold", ha="right", va="center")
        lb = fig.text(0.78, y, p["b"], color=MUTED, fontsize=26, fontweight="bold", ha="left", va="center")
        sc = fig.text(0.5, y, f"{p['aw']} – {p['bw']}", color=FG, fontsize=24, fontweight="bold", ha="center",
                      va="center")
        sc.set_path_effects([pe.withStroke(linewidth=5, foreground=BG)])
        arts.append((bg, fill, la, lb, sc, frac, x1 - x0))
    reveal = (duration - INTRO - OUTRO) * 0.75 / len(rows)

    def update(t, dur):
        for i, (bg, fill, la, lb, sc, frac, wid) in enumerate(arts):
            a = _smooth((t - INTRO - i * reveal) / 0.5)
            for art in (bg, la, lb, sc):
                art.set_alpha(a)
            fill.set_alpha(a)
            fill.set_width(max(0.0001, wid * frac * _smooth((t - INTRO - i * reveal) / 0.9)))

    return _encode(fig, cap, captions, duration, update, out_path, audio_path)


# ------------------------------------------------------------- preview
def preview(p: dict, captions, out_path, audio_path=None, duration=None, handle=""):
    duration = _dur(captions, duration)
    gp = p["name"].replace("Grand Prix", "GP").upper()
    fig, cap = _frame(f"NEXT: {gp}", "THE LAST 5 WINNERS", handle)
    fig.text(0.5, 0.858, p["date"].strftime("%a %d %b %Y").upper(), color=FG, fontsize=30, fontweight="bold",
             ha="center", va="center")
    rows = p["winners"]
    top, step = 0.80, 0.082
    arts = []
    for i, w in enumerate(rows):
        y = top - step * i
        box = FancyBboxPatch((0.08, y - 0.032), 0.84, 0.064, boxstyle="round,pad=0,rounding_size=0.012",
                             transform=fig.transFigure, facecolor="#11151D", edgecolor="#2A303C", lw=2)
        chip = FancyBboxPatch((0.08, y - 0.032), 0.018, 0.064, boxstyle="round,pad=0,rounding_size=0.006",
                              transform=fig.transFigure, facecolor=w["color"], edgecolor="none")
        fig.patches += [box, chip]
        yr = fig.text(0.13, y, str(w["season"]), color=MUTED, fontsize=32, fontweight="bold", va="center")
        nm = fig.text(0.31, y + 0.009, w["last"].upper(), color=FG, fontsize=38, fontweight="bold", va="center")
        tm = fig.text(0.31, y - 0.018, w["team"], color=w["color"], fontsize=20, fontweight="bold", va="center")
        arts.append((box, chip, yr, nm, tm))
    king = fig.text(0.5, 0.375, f"MOST WINS HERE: {p['king'][0].upper()} ×{p['king'][1]}", color=ACCENT,
                    fontsize=28, fontweight="bold", ha="center", va="center")
    reveal = (duration - INTRO - OUTRO) * 0.6 / len(rows)

    def update(t, dur):
        for i, group in enumerate(arts):
            a = _smooth((t - INTRO - i * reveal) / 0.4)
            for art in group:
                art.set_alpha(a)
        king.set_alpha(_smooth((t - INTRO - len(rows) * reveal) / 0.5))

    return _encode(fig, cap, captions, duration, update, out_path, audio_path)
