"""Full-screen photo moments: a hero intro (slow pan across a driver photo with
the video's title over it) and an optional dimmed photo behind the outro."""
from __future__ import annotations

import matplotlib.patheffects as pe
import numpy as np

from .render import BG, FG, H, W, _smooth

ASPECT = W / H  # portrait 9:16


def _bg_rgb():
    return [int(BG[i:i + 2], 16) / 255 for i in (1, 3, 5)]


class Hero:
    def __init__(self, fig, imgs, title="", subtitle="", name="", color=FG,
                 intro=2.6, outro_from=None, outro_alpha=0.32):
        self.imgs = [i for i in (imgs or []) if i is not None]
        self.intro, self.outro_from, self.outro_alpha = intro, outro_from, outro_alpha
        self.arts = []
        if not self.imgs:
            return
        # intro: full-bleed photo, above everything except captions
        self.ax = fig.add_axes([0, 0, 1, 1], zorder=50)
        img = self.imgs[0]
        h, w = img.shape[:2]
        self.w, self.h = w, h
        self.im = self.ax.imshow(img, extent=(0, w, h, 0), interpolation="bilinear")
        self.ax.axis("off")
        # gradient top and bottom so text reads
        g = np.zeros((128, 2, 4))
        g[..., :3] = _bg_rgb()
        y = np.linspace(0, 1, 128)
        g[:, :, 3] = (np.clip((0.35 - y) / 0.35, 0, 1) ** 1.5 * 0.85 + np.clip((y - 0.55) / 0.45, 0, 1) ** 1.3 * 0.95)[:, None]
        self.gax = fig.add_axes([0, 0, 1, 1], zorder=51)
        self.gim = self.gax.imshow(g, aspect="auto", extent=(0, 1, 0, 1), origin="upper")
        self.gax.set_xlim(0, 1)
        self.gax.set_ylim(0, 1)
        self.gax.axis("off")
        t1 = fig.text(0.5, 0.90, title, color=FG, fontsize=58 if len(title) < 18 else 46, fontweight="bold",
                      ha="center", va="center", zorder=52)
        t2 = fig.text(0.5, 0.855, subtitle, color=color, fontsize=28, fontweight="bold", ha="center",
                      va="center", zorder=52)
        t3 = fig.text(0.5, 0.40, name.upper(), color=FG, fontsize=64 if len(name) < 14 else 50,
                      fontweight="bold", ha="center", va="center", zorder=52)
        for t in (t1, t2, t3):
            t.set_path_effects([pe.withStroke(linewidth=8, foreground="#000000")])
        self.texts = [t1, t2, t3]
        # outro: dimmed photo behind everything
        self.oax = None
        if outro_from is not None:
            oimg = self.imgs[1] if len(self.imgs) > 1 else self.imgs[0]
            self.oax = fig.add_axes([0, 0, 1, 1], zorder=-5)
            oh, ow = oimg.shape[:2]
            self.ow, self.oh = ow, oh
            self.oim = self.oax.imshow(oimg, extent=(0, ow, oh, 0), interpolation="bilinear")
            self.oax.axis("off")
            self.oax.set_visible(False)
            fig.patch.set_alpha(1)

    def _crop(self, ax, w, h, k, zoom):
        cw = min(w, h * ASPECT) / zoom
        ch = cw / ASPECT
        cx = cw / 2 + (w - cw) * k
        cy = h * 0.5
        cy = min(max(cy, ch / 2), h - ch / 2)
        ax.set_xlim(cx - cw / 2, cx + cw / 2)
        ax.set_ylim(cy + ch / 2, cy - ch / 2)

    def update(self, t, dur):
        if not self.imgs:
            return
        a = 1.0 - _smooth((t - (self.intro - 0.45)) / 0.45)
        vis = a > 0.001
        for art in (self.ax, self.gax):
            art.set_visible(vis)
        self.im.set_alpha(a)
        self.gim.set_alpha(a)
        for i, tx in enumerate(self.texts):
            tx.set_visible(vis)
            tx.set_alpha(a * _smooth((t - 0.15 * i) / 0.4))
        if vis:
            k = min(1.0, t / max(self.intro, 0.1))
            self._crop(self.ax, self.w, self.h, 0.15 + 0.7 * k, 1.0 + 0.08 * k)
        if self.oax is not None:
            o = _smooth((t - self.outro_from) / 0.6)
            self.oax.set_visible(o > 0)
            if o > 0:
                self.oim.set_alpha(self.outro_alpha * o)
                k = min(1.0, (t - self.outro_from) / max(dur - self.outro_from, 0.1))
                self._crop(self.oax, self.ow, self.oh, 0.7 - 0.4 * k, 1.05)
