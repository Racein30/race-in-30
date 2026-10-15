"""Free-licensed driver headshots from Wikimedia Commons, with credits.

Only images hosted on Commons under CC / public-domain licences are used, so
they can appear in videos with attribution. Anything else is skipped and the
video simply shows no photo for that driver.
"""
from __future__ import annotations

import io
import json
import os
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "race-in-30/1.0 (https://racein30.github.io/race-in-30/)"}
CACHE = os.environ.get("PHOTO_CACHE", ".photo-cache")
OK_LICENCE = re.compile(r"^(CC BY|CC0|CC-BY|Public domain|PD)", re.I)


def _json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def headshot(wiki_url: str, size: int = 160):
    """Return (RGBA numpy image, credit string) or (None, None)."""
    try:
        import numpy as np
        from PIL import Image, ImageDraw

        title = urllib.parse.unquote(wiki_url.rstrip("/").split("/wiki/")[-1])
        host = urllib.parse.urlparse(wiki_url).netloc or "en.wikipedia.org"
        os.makedirs(CACHE, exist_ok=True)
        key = re.sub(r"[^A-Za-z0-9]+", "_", title)
        meta_path = os.path.join(CACHE, key + ".json")
        img_path = os.path.join(CACHE, key + ".png")

        if os.path.exists(meta_path) and os.path.exists(img_path):
            meta = json.load(open(meta_path))
            if not meta.get("ok"):
                return None, None
            return np.asarray(Image.open(img_path).convert("RGBA")), meta["credit"]

        q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "pageimages",
                                    "piprop": "name", "format": "json", "redirects": 1})
        pages = _json(f"https://{host}/w/api.php?{q}")["query"]["pages"]
        fname = next(iter(pages.values())).get("pageimage")
        if not fname:
            raise ValueError("no page image")
        # must be on Commons with a free licence
        q = urllib.parse.urlencode({"action": "query", "titles": f"File:{fname}", "prop": "imageinfo",
                                    "iiprop": "url|extmetadata", "iiurlwidth": 600, "format": "json"})
        p = next(iter(_json(f"https://commons.wikimedia.org/w/api.php?{q}")["query"]["pages"].values()))
        if "imageinfo" not in p:
            raise ValueError("not on Commons")
        info = p["imageinfo"][0]
        em = info.get("extmetadata", {})
        lic = _strip_html(em.get("LicenseShortName", {}).get("value", ""))
        if not OK_LICENCE.match(lic):
            raise ValueError(f"licence {lic!r}")
        artist = _strip_html(em.get("Artist", {}).get("value", "")) or "Unknown"
        credit = f"{fname} by {artist}, {lic}, via Wikimedia Commons"

        req = urllib.request.Request(info.get("thumburl") or info["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGB")
        # square crop from the upper-middle, where portraits keep the face
        w, h = im.size
        side = min(w, int(h * 0.62))
        left = (w - side) // 2
        top = int(max(0, min(h - side, h * 0.06)))
        im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        out = im.convert("RGBA")
        out.putalpha(mask)
        out.save(img_path)
        json.dump({"ok": True, "credit": credit}, open(meta_path, "w"))
        return np.asarray(out), credit
    except Exception as e:
        print(f"[photos] no photo for {wiki_url}: {e}")
        try:
            json.dump({"ok": False}, open(meta_path, "w"))  # type: ignore[name-defined]
        except Exception:
            pass
        return None, None
