#!/usr/bin/env python3
#
# Copyright (c) 2026, MariaDB plc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2.0,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License, version 2.0, for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
"""Synthesize the narration sentence by sentence with Kokoro, then lay it out on
one timeline: vo.wav plus timeline.json with segment, sentence and estimated
word times, which the animation page uses as cues."""
import json, re, sys, pathlib
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro, EspeakConfig
import espeakng_loader

here = pathlib.Path(__file__).parent
cache = here.parent.parent / ".cache"  # videos/.cache, built by videos/setup.sh
models = cache / "models"
voice = sys.argv[1] if len(sys.argv) > 1 else "af_heart"
speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.05
esp = pathlib.Path(espeakng_loader.__file__).parent
k = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"),
           espeak_config=EspeakConfig(lib_path=str(esp / "libespeak-ng.dylib"),
                                      data_path=str(cache / "esd")))

LEAD = 1.6        # silence before the first word
GAP = 0.95        # pause between segments
SENT_GAP = 0.12   # extra pause between sentences of a segment
TAIL = 5.0        # end card after the last word
SR = 24000


PAUSE = re.compile(r"\s*\{pause:([\d.]+)\}\s*")


def set_pauses(audio, spoken, marks):
    """Resize the silence at each {pause:S} mark to exactly S seconds. The mark is
    voiced as a comma, for the natural intonation; its silence is then found as
    the longest quiet run near the mark's estimated time and cut or padded."""
    env = np.convolve(np.abs(audio), np.ones(240) / 240, mode="same")
    quiet = env < 0.01
    for pos, secs in sorted(marks, reverse=True):  # from the end, so earlier indices stay valid
        est = len(audio) * pos / len(spoken)
        runs, start = [], None
        for i, q in enumerate(quiet):
            if q and start is None:
                start = i
            elif not q and start is not None:
                runs.append((start, i)); start = None
        near = [r for r in runs if abs((r[0] + r[1]) / 2 - est) < 0.6 * SR and r[0] > 0]
        if not near:
            print(f"  no pause found near char {pos}"); continue
        a, b = max(near, key=lambda r: r[1] - r[0])
        print(f"  pause {1000 * (b - a) / SR:.0f} ms -> {secs * 1000:.0f} ms")
        f = int(0.005 * SR)  # 5 ms fades, so the cut never clicks
        head, tail = audio[:a].copy(), audio[b:].copy()
        head[-f:] *= np.linspace(1, 0, f)
        tail[:f] *= np.linspace(0, 1, f)
        audio = np.concatenate([head, np.zeros(int(secs * SR), dtype=np.float32), tail])
        quiet = np.convolve(np.abs(audio), np.ones(240) / 240, mode="same") < 0.01
    return audio


def trim(x, thr=0.004):
    """Strip leading/trailing silence, keeping a few ms of air."""
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    a = max(idx[0] - int(0.02 * SR), 0)
    b = min(idx[-1] + int(0.06 * SR), len(x))
    return x[a:b]


segs = json.loads((here / "narration.json").read_text())
track = [np.zeros(int(LEAD * SR), dtype=np.float32)]
t = LEAD
timeline = {"segments": []}
for si, seg in enumerate(segs):
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", seg["text"]) if s.strip()]
    segrec = {"id": seg["id"], "start": round(t, 3), "sentences": []}
    for i, raw in enumerate(sentences):
        # "{pause:0.2}" in the script: spoken as a comma, then set to 0.2 s exactly
        spoken, marks, s = "", [], ""
        pieces = PAUSE.split(raw)
        for j, piece in enumerate(pieces):
            if j % 2 == 0:
                spoken += piece; s += piece
            else:
                marks.append((len(spoken), float(piece)))
                spoken += ", "; s += " "
        audio, sr = k.create(spoken, voice=voice, speed=speed, lang="en-us")
        assert sr == SR
        audio = trim(audio.astype(np.float32))
        if marks:
            audio = set_pauses(audio, spoken, marks)
        dur = len(audio) / SR
        # Word cue estimates: proportional to character position, which is
        # close enough for motion cues at sentence granularity.
        words = []
        for m in re.finditer(r"[A-Za-z0-9'\-]+", s):
            words.append({"w": m.group(0).lower(), "t": round(t + dur * (m.start() / len(s)), 3)})
        segrec["sentences"].append({"text": s, "start": round(t, 3), "end": round(t + dur, 3), "words": words})
        track.append(audio)
        t += dur
        if i < len(sentences) - 1:
            track.append(np.zeros(int(SENT_GAP * SR), dtype=np.float32))
            t += SENT_GAP
    segrec["end"] = round(t, 3)
    timeline["segments"].append(segrec)
    print(f"{seg['id']:8s} {segrec['start']:7.2f} -> {segrec['end']:7.2f}")
    pad = GAP if si < len(segs) - 1 else TAIL
    track.append(np.zeros(int(pad * SR), dtype=np.float32))
    t += pad

timeline["duration"] = round(t, 3)
vo = np.concatenate(track)
sf.write(here / "vo.wav", vo, SR)
(here / "timeline.json").write_text(json.dumps(timeline, indent=1))
print("duration", round(t, 2))
