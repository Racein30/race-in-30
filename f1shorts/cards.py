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


NEXT_HERO: dict | None = None  # set by formats before a render: photo intro for the next video


def _encode(fig, cap, captions, duration, update, out_path, audio_path=None):
    global NEXT_HERO
    hero = None
    if NEXT_HERO:
        from .hero import Hero
        hero = Hero(fig, **NEXT_HERO)
        NEXT_HERO = None
        cap.set_zorder(60)
        inner = update

        def update(t, dur):  # noqa: F811
            inner(t, dur)
            hero.update(t, dur)
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
            ab = AnnotationBbox(OffsetImage(img, zoom=0.5), (0, 20), frameon=False, zorder=5,
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
                pic_of[i].xy = pic_of[i].xybox = (v[i] + vmax * 0.06, y)
                pic_of[i].set_visible(rank[i] <= top_n)
                off = vmax * 0.125
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


# ------------------------------------------------------------- prediction podium
def prediction(p: dict, captions, out_path, audio_path=None, duration=None, handle="", photos=None):
    duration = _dur(captions, duration)
    gp = p["name"].replace("Grand Prix", "GP").upper()
    fig, cap = _frame(f"{gp} {p['year']}", "WHO WINS? THE DATA PICKS", handle)
    fig.text(0.5, 0.858, p["date"].strftime("%a %d %b").upper() + " · PREDICTION", color=FG, fontsize=30,
             fontweight="bold", ha="center", va="center")
    # podium blocks: P2 left, P1 centre, P3 right
    slots = [(0, 0.5, 0.20), (1, 0.18, 0.15), (2, 0.82, 0.11)]  # (podium idx, x centre, block height)
    base, width = 0.36, 0.28
    groups = []
    for idx, xc, hgt in slots:
        d = p["podium"][idx]
        blk = FancyBboxPatch((xc - width / 2 + 0.01, base), width - 0.02, hgt,
                             boxstyle="round,pad=0,rounding_size=0.01", transform=fig.transFigure,
                             facecolor=d["color"], edgecolor="none")
        fig.patches.append(blk)
        num = fig.text(xc, base + hgt / 2, str(idx + 1), color=_ink_on(d["color"]), fontsize=80,
                       fontweight="bold", ha="center", va="center")
        top = base + hgt
        name = fig.text(xc, top + 0.03, d["last"].upper(), color=FG, fontsize=30 if len(d["last"]) < 10 else 24,
                        fontweight="bold", ha="center", va="center")
        stat = fig.text(xc, top + 0.008, f"{d['form']:.1f} PTS/RACE", color=MUTED, fontsize=18,
                        fontweight="bold", ha="center", va="center")
        arts = [blk, num, name, stat]
        img = (photos or {}).get(d["id"])
        if img is not None:
            ax = fig.add_axes([xc - 0.11, top + 0.05, 0.22, 0.124])
            ax.imshow(img)
            ax.axis("off")
            arts.append(ax)
        else:
            code = fig.text(xc, top + 0.11, d["code"], color=d["color"], fontsize=60, fontweight="bold",
                            ha="center", va="center")
            arts.append(code)
        groups.append((idx, arts))
    groups.sort(key=lambda g: -g[0])  # reveal P3, P2, then P1
    span = (duration - INTRO - OUTRO)
    reveal_at = {2: INTRO + span * 0.18, 1: INTRO + span * 0.42, 0: INTRO + span * 0.66}

    def update(t, dur):
        for idx, arts in groups:
            a = _smooth((t - reveal_at[idx]) / 0.5)
            for art in arts:
                art.set_alpha(a) if not hasattr(art, "images") else [im.set_alpha(a) for im in art.images]

    update(0, duration)
    return _encode(fig, cap, captions, duration, update, out_path, audio_path)


# ------------------------------------------------------------- how the leader clinches
_ABBR = {"United States": "USA", "Mexico City": "MEX", "Brazil": "BRA", "São Paulo": "BRA", "Las Vegas": "LVG",
         "Qatar": "QAT", "Abu Dhabi": "ABU", "Singapore": "SIN", "Japan": "JPN", "Azerbaijan": "AZE",
         "Italian": "ITA", "Dutch": "NED", "Belgian": "BEL", "Hungarian": "HUN", "British": "GBR",
         "Austrian": "AUT", "Spanish": "ESP", "Monaco": "MON", "Canadian": "CAN", "Miami": "MIA",
         "Chinese": "CHN", "Australian": "AUS", "Saudi": "KSA", "Bahrain": "BHR", "Emilia": "IMO",
         "Barcelona": "BAR", "Madrid": "MAD", "Brazilian": "BRA", "Japanese": "JPN"}


def _abbr(name: str) -> str:
    for k, v in _ABBR.items():
        if name.startswith(k):
            return v
    return name[:3].upper()


def _cap_time(captions, words, default):
    for c in captions:
        if any(w.lower() in c["text"].lower() for w in words):
            return c["start"]
    return default


def clinch(t: dict, captions, out_path, audio_path=None, duration=None, handle="", gallery=None):
    duration = _dur(captions, duration)
    L = t["leader"]
    fig, cap = _frame(f"HOW {L['last'].upper()} WINS", f"THE {t['year']} TITLE · EVERY SCENARIO", handle)
    cap.set_position((0.5, 0.215))

    # --- photo panel with slow zoom + crossfade
    px = [0.0, 0.585, 1.0, 0.295]
    aspect = (px[2] * W) / (px[3] * H)
    panels = []
    for img in (gallery or []):
        ax = fig.add_axes(px, zorder=1)
        h, w = img.shape[:2]
        ax.imshow(img, extent=(0, w, h, 0), interpolation="bilinear")
        ax.axis("off")
        # crop window matching the panel aspect, centred slightly high
        cw = min(w, h * aspect)
        ch = cw / aspect
        panels.append((ax, w, h, cw, ch))
    # gradient so text on top stays readable
    gax = fig.add_axes(px, zorder=2)
    grad = np.zeros((64, 2, 4))
    grad[..., :3] = [int(BG[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    grad[:, :, 3] = np.linspace(0.0, 1.0, 64)[:, None] ** 1.6
    grad[:12, :, 3] = np.maximum(grad[:12, :, 3], np.linspace(0.55, 0.0, 12)[:, None])
    gax.imshow(grad, aspect="auto", extent=(0, 1, 0, 1))
    gax.set_xlim(0, 1)
    gax.set_ylim(0, 1)
    gax.axis("off")
    if not panels:
        fig.text(0.5, 0.74, L["code"], color=L["color"], fontsize=150, fontweight="bold", ha="center",
                 va="center", zorder=3)
    fig.text(0.06, 0.612, L["last"].upper(), color=FG, fontsize=44, fontweight="bold", va="center", zorder=3)
    fig.text(0.06, 0.594 - 0.004, f"{_fmt(L['pts'])} PTS · LEADER", color=L["color"], fontsize=22,
             fontweight="bold", va="center", zorder=3)
    r0 = t["rival"]
    fig.text(0.94, 0.612, f"-{_fmt(r0['gap'])}", color=ACCENT, fontsize=44, fontweight="bold", ha="right",
             va="center", zorder=3)
    fig.text(0.94, 0.590, f"TO {r0['last'].upper()}", color=MUTED, fontsize=22, fontweight="bold",
             ha="right", va="center", zorder=3)

    nl = len(t["left"])
    fig.text(0.5, 0.560, f"{nl} RACE{'S' if nl != 1 else ''} LEFT · {t['remaining']} PTS ON THE TABLE",
             color=FG, fontsize=24, fontweight="bold", ha="center", va="center")

    span = duration - INTRO - OUTRO
    tA = _cap_time(captions, ["this weekend", "can't seal"], INTRO + span * 0.25)
    tB = _cap_time(captions, ["keeps winning"], INTRO + span * 0.5)
    tC = _cap_time(captions, ["worst case"], INTRO + span * 0.72)

    arts_chart, line = [], None
    pill = fig.text(0.5, 0.345, "", color=FG, fontsize=25, fontweight="bold", ha="center", va="center",
                    linespacing=1.2)
    if not t["decided"]:
        after = t["after"]
        lines = t["lines"]
        xs = np.arange(nl)
        ymax = max(max(after + [t["remaining"]]), max(lines)) * 1.12
        ax = fig.add_axes([0.08, 0.392, 0.84, 0.132])
        ax.set_facecolor(BG)
        ax.set_xlim(-0.6, nl - 0.4)
        ax.set_ylim(0, ymax)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_yticks([])
        ax.set_xticks(xs)
        ax.set_xticklabels([_abbr(w["name"]) for w in t["left"]], color=MUTED, fontsize=18, fontweight="bold")
        ax.tick_params(length=0, pad=6)
        bars = ax.bar(xs, [0] * nl, width=0.62, color="#2A303C", zorder=2)
        blabels = [ax.text(x, 0, "", color=MUTED, fontsize=15, fontweight="bold", ha="center", va="bottom")
                   for x in xs]
        line, = ax.plot([], [], color=L["color"], lw=4, marker="o", ms=11, zorder=4,
                        markeredgecolor=BG, markeredgewidth=2)
        star, = ax.plot([], [], "o", ms=22, color="#3DDC84", zorder=5, markeredgecolor=BG, markeredgewidth=3)
        champ = ax.text(0, 0, "", color="#3DDC84", fontsize=18, fontweight="bold", ha="center", va="bottom",
                        zorder=5)
        legend = fig.text(0.5, 0.538, f"BARS = POINTS LEFT   ·   LINE = {L['last'].upper()}'S LEAD",
                          color=MUTED, fontsize=15, fontweight="bold", ha="center", va="center")
        legend.set_alpha(0)
        likely = t["likely"]
        nx = t["next"]
        where = _abbr(nx["weekend"]["name"])
        if nx["possible"]:
            pill_a = f"FASTEST: {where} — WIN"
            conds = []
            for r in nx["needs"][:2]:
                if r["finish"] and r["finish"].startswith("P"):
                    conds.append(f"{r['code']} {r['finish']} OR LOWER")
                elif r["finish"]:
                    conds.append(f"{r['code']} NO POINTS")
                else:
                    conds.append(f"{r['code']} ≤{_fmt(r['allowed'])} PTS")
            if conds:
                pill_a += ", " + ", ".join(conds)
        else:
            pill_a = f"NOT YET IN {where}"
        pill_b = (f"LIKELY: CHAMPION IN {_abbr(t['left'][likely]['name'])}" if likely is not None
                  else "KEEP WINNING")
        wc = t["worst"]
        pill_c = (f"WORST CASE: P{wc['every']} EVERY RACE" if wc["every"] else f"WORST CASE: {wc['need']} PTS")

    def update(tt, dur):
        # photos: crossfade + slow push-in
        n = len(panels)
        if n:
            seg = dur / n
            for i, (ax, w, h, cw, ch) in enumerate(panels):
                local = tt - i * seg
                a = 1.0 if i == 0 and local < seg else 0.0
                if i > 0:
                    a = _smooth(local / 0.6)
                if i < n - 1 and tt > (i + 1) * seg + 0.6:
                    a = 0.0
                for im in ax.images:
                    im.set_alpha(a)
                ax.set_visible(a > 0)
                z = 1.0 + 0.10 * max(0.0, min(1.0, local / (seg + 0.6)))
                vw, vh = cw / z, ch / z
                cx = w / 2 + (0.04 * w if i % 2 else -0.04 * w) * (local / (seg + 0.6))
                cy = h * 0.45
                cx = min(max(cx, vw / 2), w - vw / 2)
                cy = min(max(cy, vh / 2), h - vh / 2)
                ax.set_xlim(cx - vw / 2, cx + vw / 2)
                ax.set_ylim(cy + vh / 2, cy - vh / 2)
        if t["decided"]:
            pill.set_text("CHAMPION" if tt > INTRO else "")
            return
        g = _smooth((tt - tA + 0.3) / 1.2)
        for i, b in enumerate(bars):
            b.set_height(after[i] * g)
            blabels[i].set_position((i, after[i] * g + ymax * 0.02))
            blabels[i].set_text(str(after[i]) if g > 0.9 else "")
        legend.set_alpha(g)
        k = (tt - tB) / 2.5
        if k > 0:
            m = min(nl, int(k * nl) + 1)
            line.set_data(np.arange(m), lines[:m])
            if likely is not None and m > likely:
                champ.set_position((likely, max(lines[likely], after[likely]) + ymax * 0.10))
                champ.set_text("CHAMPION")
                star.set_data([likely], [lines[likely]])
        if tt >= tC:
            pill.set_text(textwrap.fill(pill_c, 36))
            pill.set_color("#FFB020")
        elif tt >= tB:
            pill.set_text(textwrap.fill(pill_b, 36))
            pill.set_color("#3DDC84")
        elif tt >= tA:
            pill.set_text(textwrap.fill(pill_a, 36))
            pill.set_color(FG)

    return _encode(fig, cap, captions, duration, update, out_path, audio_path)
