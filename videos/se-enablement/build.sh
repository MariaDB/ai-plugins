#!/bin/sh
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
# Rebuild the SE enablement video end to end. See PLAN.md.
#   ./build.sh          narration + check + frames + audio + mux
#   ./build.sh --no-tts keep src/vo.wav and src/timeline.json as they are
set -e
cd "$(dirname "$0")"
PY=../.cache/venv/bin/python
[ -x "$PY" ] || ../setup.sh
OUT=../output/MariaDB-AI-Plugins-SE-Enablement.mp4
[ "$1" = "--no-tts" ] || $PY -I src/tts.py af_heart 1.05
$PY -I src/render.py check
$PY -I src/render.py video 30
$PY -I src/audio.py
ffmpeg -y -loglevel error -i .work/video.mp4 -i .work/mix.wav -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-16:LRA=11:TP=-1.5" -ar 48000 -c:a aac -b:a 256k -movflags +faststart -shortest \
  "$OUT"
echo "-> $(cd ../output && pwd)/MariaDB-AI-Plugins-SE-Enablement.mp4 (+ .srt)"
