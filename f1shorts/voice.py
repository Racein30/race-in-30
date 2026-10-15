"""Free neural voiceover (Microsoft Edge TTS) with caption timings."""
from __future__ import annotations

import asyncio
import os
import subprocess

VOICE = os.environ.get("TTS_VOICE", "en-GB-RyanNeural")
RATE = os.environ.get("TTS_RATE", "+10%")
LEAD_IN = 0.35  # seconds of silence before the voice starts


def _duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def proportional_captions(sentences: list[str], start: float, end: float) -> list[dict]:
    words = [max(1, len(s.split())) for s in sentences]
    total, t, caps = sum(words), start, []
    for s, w in zip(sentences, words):
        d = (end - start) * w / total
        caps.append({"start": t, "end": t + d, "text": s})
        t += d
    return caps


async def _speak(text: str, mp3: str) -> list[tuple[float, float, str]]:
    import edge_tts

    try:
        com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="SentenceBoundary")
    except TypeError:  # older edge-tts
        com = edge_tts.Communicate(text, VOICE, rate=RATE)
    marks = []
    with open(mp3, "wb") as fh:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                marks.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7, chunk["text"]))
    return marks


def synthesize(sentences: list[str], out_dir: str) -> tuple[str, list[dict], float]:
    """Return (audio path, captions, audio duration in seconds)."""
    raw = os.path.join(out_dir, "voice_raw.mp3")
    final = os.path.join(out_dir, "voice.m4a")
    marks = asyncio.run(_speak(" ".join(sentences), raw))
    # add the lead-in silence
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    f"adelay={int(LEAD_IN * 1000)}:all=1", "-c:a", "aac", "-b:a", "160k", final], check=True)
    dur = _duration(final)

    caps = []
    if marks and len(marks) >= len(sentences) - 1 and all(len(m[2].split()) > 2 for m in marks[:2]):
        # sentence boundaries from the TTS engine: exact timing
        for i, (off, d, text) in enumerate(marks):
            start = off + LEAD_IN
            end = marks[i + 1][0] + LEAD_IN if i + 1 < len(marks) else dur
            caps.append({"start": start, "end": max(end, start + d), "text": text})
    if not caps:
        caps = proportional_captions(sentences, LEAD_IN, dur)
    return final, caps, dur
