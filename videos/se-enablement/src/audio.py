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
"""Score, sound design and mix, all synthesized here — no samples, no licences.

Reads src/timeline.json (section times), src/vo.wav (narration) and
.work/sfx.json (cue events exported by `render.py check`), writes .work/mix.wav.
"""
import json, pathlib
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

SRC = pathlib.Path(__file__).parent
WORK = SRC.parent / ".work"
WORK.mkdir(exist_ok=True)
SR = 48000
rng = np.random.default_rng(7)

TL = json.loads((SRC / "timeline.json").read_text())
SEG = {s["id"]: s for s in TL["segments"]}
DUR = TL["duration"]
N = int(DUR * SR) + SR
T_PROBLEM = SEG["problem"]["start"] - 0.55
T_REVEAL = SEG["reveal"]["start"] - 0.55
T_CLOSE = SEG["close"]["start"] - 0.55
T_LOGO = SEG["close"]["sentences"][1]["start"]

BPM = 100
BEAT = 60 / BPM
CHORD_LEN = 8 * BEAT  # two bars
# D minor colour: Dm9 - Bbmaj7 - Fmaj7 - Cadd9, and their roots
CHORDS = [[50, 57, 60, 64, 65], [46, 53, 57, 62, 65], [41, 53, 57, 60, 64], [48, 55, 60, 62, 64]]
ROOTS = [38, 34, 41, 36]

hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
lp = lambda x, f, o=2: sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
hp = lambda x, f, o=2: sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
bp = lambda x, a, b, o=2: sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)


def add(buf, t0, sig, gain=1.0):
    i = int(t0 * SR)
    if i >= len(buf) or i + len(sig) <= 0:
        return
    j = max(0, -i)
    sig = sig[j:]
    i = max(i, 0)
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n] * gain


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na) if na else 1
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def section_gain(t, pairs):
    """Piecewise-linear gain from (time, value) points."""
    ts, vs = zip(*pairs)
    return np.interp(t, ts, vs)


t_all = np.arange(N) / SR

# ---------------------------------------------------------------- pad
pad = np.zeros(N)
k = 0
t0 = 0.0
while t0 < DUR + 2:
    ch = CHORDS[k % 4]
    L = CHORD_LEN + 1.2
    tt = np.arange(int(L * SR)) / SR
    sig = np.zeros_like(tt)
    for m in ch:
        for cents in (-7, 0, 7):
            f = hz(m) * 2 ** (cents / 1200)
            ph = rng.uniform(0, 6.28)
            sig += np.sin(2 * np.pi * f * tt + ph) + 0.3 * np.sin(4 * np.pi * f * tt + ph) + 0.1 * np.sin(6 * np.pi * f * tt)
    sig *= env_ar(len(tt), 1.2, 1.4) / (len(ch) * 3)
    add(pad, t0, sig)
    t0 += CHORD_LEN
    k += 1
pad = lp(pad, 1700)
pad_gain = section_gain(t_all, [(0, 0), (1.5, .9), (T_PROBLEM, .9), (T_PROBLEM + .8, .55), (T_REVEAL - .3, .4), (T_REVEAL, 1), (T_CLOSE, 1), (DUR - 2.5, 1), (DUR, 0)])
pad *= pad_gain

# ---------------------------------------------------------------- arp
arp_l, arp_r = np.zeros(N), np.zeros(N)
pattern = [0, 1, 2, 3, 4, 3, 2, 1]
step = BEAT / 2
n_steps = int(DUR / step)
for s in range(n_steps):
    t = s * step
    if T_PROBLEM <= t < T_REVEAL or t < 1.6 or t > DUR - 1:
        continue
    ch = CHORDS[int(t // CHORD_LEN) % 4]
    m = ch[pattern[s % 8] % len(ch)] + 12
    tt = np.arange(int(0.55 * SR)) / SR
    f = hz(m)
    sig = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt) * np.exp(-tt * 9)) * np.exp(-tt * 5.5)
    sig[:240] *= np.linspace(0, 1, 240)
    accent = 1.0 if s % 4 == 0 else 0.7
    pan = 0.3 if s % 2 else 0.7
    add(arp_l, t, sig, accent * (1 - pan))
    add(arp_r, t, sig, accent * pan)
arp_gain = section_gain(t_all, [(0, .5), (T_PROBLEM, .5), (T_REVEAL, .8), (T_CLOSE, .8), (T_LOGO, 1), (DUR, .6)])
arp_l, arp_r = lp(arp_l * arp_gain, 5000), lp(arp_r * arp_gain, 5000)

# ---------------------------------------------------------------- drums & bass (main section only)
kick, hat, bass = np.zeros(N), np.zeros(N), np.zeros(N)
kt = np.arange(int(0.45 * SR)) / SR
kphase = 2 * np.pi * np.cumsum(45 + 90 * np.exp(-kt * 28)) / SR
kick_one = np.sin(kphase) * np.exp(-kt * 7.5)
hat_one = hp(rng.standard_normal(int(0.07 * SR)), 7000) * np.exp(-np.arange(int(0.07 * SR)) / SR * 55)
b = 0
while b * BEAT < DUR:
    t = b * BEAT
    main = T_REVEAL <= t < T_CLOSE
    problem = T_PROBLEM + 0.8 <= t < T_REVEAL - 0.2
    if main:
        add(kick, t, kick_one, 1.0)
        add(hat, t + BEAT / 2, hat_one, 0.9)
        root = ROOTS[int(t // CHORD_LEN) % 4]
        for h in (0, 0.5):
            bt = np.arange(int(0.28 * SR)) / SR
            f = hz(root)
            sig = (np.sin(2 * np.pi * f * bt) + 0.35 * np.sin(4 * np.pi * f * bt)) * np.exp(-bt * 6)
            sig[:200] *= np.linspace(0, 1, 200)
            add(bass, t + h * BEAT, sig, 0.9 if h == 0 else 0.6)
    elif problem:
        add(hat, t, hat_one, 0.6)  # a clock ticking under the problem
        if b % 4 == 0:
            add(kick, t, kick_one, 0.55)
    b += 1
# tension drone under the problem
drone = np.sin(2 * np.pi * hz(26) * t_all) * 0.5 + np.sin(2 * np.pi * hz(38) * t_all + 1) * 0.3
drone *= section_gain(t_all, [(T_PROBLEM, 0), (T_PROBLEM + 1.5, .6), (T_REVEAL - .2, .8), (T_REVEAL, 0)])
# riser into the reveal
riser = np.zeros(N)
rl = 3.2
rt = np.arange(int(rl * SR)) / SR
noise = rng.standard_normal(len(rt))
blocks = np.array_split(np.arange(len(rt)), 64)
rs = np.zeros(len(rt))
for i, idx in enumerate(blocks):
    fc = 300 * (12000 / 300) ** (i / 64)
    rs[idx] = bp(noise, fc * .7, min(fc * 1.4, 23000))[idx]
rs *= (rt / rl) ** 2.2
add(riser, T_REVEAL - rl + 0.15, rs, 0.5)

music_l = pad + arp_l + kick * .9 + hat * .22 + bass * .55 + drone * .5 + riser
music_r = pad + arp_r + kick * .9 + hat * .26 + bass * .55 + drone * .5 + riser

# ---------------------------------------------------------------- sound effects
sfx_l, sfx_r = np.zeros(N), np.zeros(N)


def whoosh():
    L = 0.9
    tt = np.arange(int(L * SR)) / SR
    nz = rng.standard_normal(len(tt))
    out = np.zeros_like(tt)
    for i, idx in enumerate(np.array_split(np.arange(len(tt)), 36)):
        fc = 400 * (5000 / 400) ** np.sin(np.pi * i / 36)
        out[idx] = bp(nz, fc * .6, fc * 1.6)[idx]
    return out * np.sin(np.pi * tt / L) ** 2 * 0.16


def impact():
    L = 2.4
    tt = np.arange(int(L * SR)) / SR
    ph = 2 * np.pi * np.cumsum(32 + 50 * np.exp(-tt * 6)) / SR
    boom = np.sin(ph) * np.exp(-tt * 1.8)
    crack = lp(rng.standard_normal(len(tt)), 2500) * np.exp(-tt * 9) * 0.5
    tail = lp(rng.standard_normal(len(tt)), 900) * np.exp(-tt * 2.2) * 0.15
    return (boom + crack + tail) * 0.9


def blip():
    tt = np.arange(int(0.09 * SR)) / SR
    return (np.sin(2 * np.pi * 1320 * tt) + 0.4 * np.sin(2 * np.pi * 1980 * tt)) * np.exp(-tt * 45) * 0.16


def key():
    tt = np.arange(int(0.014 * SR)) / SR
    return bp(rng.standard_normal(len(tt)), 1800, 6000) * np.exp(-tt * 400) * rng.uniform(.05, .09)


def glitch():
    tt = np.arange(int(0.16 * SR)) / SR
    sq = np.sign(np.sin(2 * np.pi * rng.uniform(90, 160) * tt)) * (rng.standard_normal(len(tt)) > 0)
    return np.round(sq * 4) / 4 * np.exp(-tt * 14) * 0.12


def thud():
    tt = np.arange(int(0.4 * SR)) / SR
    return (np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 10) + lp(rng.standard_normal(len(tt)), 1200) * np.exp(-tt * 40) * .4) * 0.8


GEN = {"whoosh": whoosh, "impact": impact, "blip": blip, "key": key, "glitch": glitch, "thud": thud}
events = json.loads((WORK / "sfx.json").read_text()) + [{"t": 0.15, "k": "impact"}]
for i, ev in enumerate(events):
    s = GEN[ev["k"]]()
    pan = 0.5 if ev["k"] in ("impact", "thud") else 0.35 + 0.3 * ((i * 37) % 10) / 10
    add(sfx_l, ev["t"], s, 1 - pan)
    add(sfx_r, ev["t"], s, pan)

# ---------------------------------------------------------------- voice + ducking
vo, vsr = sf.read(SRC / "vo.wav")
vo = resample_poly(vo, SR, vsr)
vo = np.pad(vo, (0, max(0, N - len(vo))))[:N]
vo = hp(vo, 70)
vo = vo / np.max(np.abs(vo)) * 0.7

env = np.abs(vo)
w = int(0.25 * SR)
env = np.convolve(env, np.ones(w) / w, mode="same")
env = np.clip(env / np.percentile(env[env > 1e-4], 90), 0, 1)
duck = 1 - 0.55 * env

speech_rms = np.sqrt(np.mean(vo[env > 0.3] ** 2))
music_rms = np.sqrt(np.mean(((music_l + music_r) / 2) ** 2))
mg = 0.38 * speech_rms / music_rms
sfx_rms = np.sqrt(np.mean(((sfx_l + sfx_r) / 2)[np.abs(sfx_l) > 1e-4] ** 2)) or 1

L = vo + music_l * mg * duck + sfx_l * 0.9
R = vo + music_r * mg * duck + sfx_r * 0.9
mix = np.stack([L, R], 1)[: int(DUR * SR)]
fade = int(2.0 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix /= np.max(np.abs(mix)) / 0.89
sf.write(WORK / "mix.wav", mix.astype(np.float32), SR)
print("mix ->", WORK / "mix.wav", f"{len(mix) / SR:.2f}s, music gain {mg:.3f}, {len(events)} sfx")
