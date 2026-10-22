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
"""Render index.html frame by frame in headless Chrome and encode with ffmpeg.

The page exposes window.seek(t), which draws the exact frame for time t, so the
render is deterministic and can be split across workers.

  render.py check            cue errors + sfx.json, no frames
  render.py stills T [T…]    PNG stills at the given seconds -> .work/stills/
  render.py video [FPS]      full render -> .work/video.mp4 (silent)
"""
import json, math, pathlib, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
from playwright.sync_api import sync_playwright

SRC = pathlib.Path(__file__).parent
WORK = SRC.parent / ".work"
WORK.mkdir(exist_ok=True)
OUTPUT = SRC.parent.parent / "output"
NAME = "MariaDB-AI-Plugins-SE-Enablement"
W, H = 1920, 1080
WORKERS = 7


def write_timeline_js():
    tl = json.loads((SRC / "timeline.json").read_text())
    (SRC / "timeline.js").write_text("window.TIMELINE = " + json.dumps(tl) + ";\n")


def open_page(p):
    browser = p.chromium.launch(channel="chrome", args=["--force-color-profile=srgb", "--hide-scrollbars"])
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    page.goto((SRC / "index.html").as_uri())
    page.wait_for_function("document.fonts.ready.then(() => true)")
    page.evaluate("document.fonts.load('900 40px Lato')")
    page.evaluate("document.fonts.load('400 20px \"IBM Plex Mono\"')")
    page.wait_for_timeout(300)
    return browser, page


def write_srt(caps):
    ts = lambda x: f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round(x % 1 * 1000)) % 1000:03d}"
    ends = [min(c["end"] + 0.2, n["start"] - 0.01) for c, n in zip(caps, caps[1:])] + [caps[-1]["end"] + 0.2]
    out = "".join(f"{i}\n{ts(c['start'])} --> {ts(e)}\n{c['text']}\n\n" for i, (c, e) in enumerate(zip(caps, ends), 1))
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / f"{NAME}.srt").write_text(out)


def check():
    with sync_playwright() as p:
        browser, page = open_page(p)
        errs = page.evaluate("window.cueErrors")
        fonts = page.evaluate("[document.fonts.check('900 40px Lato'), document.fonts.check('400 20px \"IBM Plex Mono\"')]")
        sfx = page.evaluate("window.sfxEvents()")
        dur = page.evaluate("window.DUR")
        caps = page.evaluate("window.CAPS")
        browser.close()
    write_srt(caps)
    (WORK / "sfx.json").write_text(json.dumps(sfx))
    print("duration", dur, "| fonts Lato/Plex:", fonts, "| sfx events:", len(sfx))
    print("cue errors:", errs or "none")
    return dur, errs


def stills(times):
    out = WORK / "stills"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser, page = open_page(p)
        for t in times:
            page.evaluate(f"seek({t})")
            page.screenshot(path=str(out / f"t{float(t):07.2f}.png"))
        browser.close()
    print("stills ->", out)


def render_chunk(args):
    idx, f0, f1, fps = args
    seg = WORK / "chunks" / f"c{idx:02d}.mp4"
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(fps), str(seg)],
        stdin=subprocess.PIPE)
    with sync_playwright() as p:
        browser, page = open_page(p)
        for f in range(f0, f1):
            page.evaluate(f"seek({f / fps})")
            enc.stdin.write(page.screenshot(type="jpeg", quality=95))
        browser.close()
    enc.stdin.close()
    enc.wait()
    return seg


def video(fps=30):
    dur, errs = check()
    if errs:
        sys.exit("fix cue errors first")
    n = math.ceil(dur * fps)
    (WORK / "chunks").mkdir(parents=True, exist_ok=True)
    step = math.ceil(n / WORKERS)
    jobs = [(i, i * step, min((i + 1) * step, n), fps) for i in range(WORKERS) if i * step < n]
    with ProcessPoolExecutor(WORKERS) as ex:
        segs = list(ex.map(render_chunk, jobs))
    lst = WORK / "chunks" / "list.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(WORK / "video.mp4")], check=True)
    print("video ->", WORK / "video.mp4", n, "frames")


if __name__ == "__main__":
    write_timeline_js()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "stills":
        stills(sys.argv[2:])
    elif cmd == "video":
        video(int(sys.argv[2]) if len(sys.argv) > 2 else 30)
