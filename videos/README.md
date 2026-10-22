# Videos

Videos about the MariaDB AI Plugins, generated entirely from source: an HTML
animation that is captured frame by frame in headless Chrome, a narration from a
local text-to-speech model, and music and sound effects synthesized in Python.
Nothing is edited by hand in a video tool, so a video can be changed and rebuilt
at any time.

| Video | Audience | Length | Plan |
| --- | --- | --- | --- |
| `se-enablement/` | MariaDB plc Sales Engineers | 2:12 | [PLAN.md](se-enablement/PLAN.md) |

## Requirements

- macOS or Linux with `python3` (3.12+), `curl`, `ffmpeg` and Google Chrome
- network access for the first setup and for Google Fonts during a render

## Build

```sh
videos/setup.sh                    # once: builds videos/.cache/ (about 900 MB)
videos/se-enablement/build.sh      # → videos/output/MariaDB-AI-Plugins-SE-Enablement.mp4 + .srt
```

`build.sh` runs `setup.sh` itself when the toolchain is missing.

## What is tracked

| Tracked | Generated and gitignored |
| --- | --- |
| `setup.sh`, `requirements.txt`, this README | `.cache/`: venv, voice model, espeak data |
| per video: `PLAN.md`, `build.sh`, `src/` sources | per video: `.work/`, `src/vo.wav`, `src/timeline.json`, `src/timeline.js` |
| `output/.gitkeep` | `output/*`: the rendered `.mp4` and `.srt` |

## Adding a video

Copy `se-enablement/` to a new folder, then:

- rewrite `src/narration.json` and the scenes in `src/index.html`;
- change `NAME` in `src/render.py` and the output file name in `build.sh`;
- write the new video's `PLAN.md`.

The cue system, renderer and audio engine carry over unchanged, and so does the
toolchain in `.cache/`.
