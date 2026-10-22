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
# Build the shared, gitignored toolchain in videos/.cache/ that every video's
# build.sh uses: a Python venv, the Kokoro voice model and a copy of the
# espeak-ng data. Safe to re-run; it only fetches what is missing.
#
# Needs python3 (3.12+), curl, ffmpeg and Google Chrome.
set -e
cd "$(dirname "$0")"
CACHE=.cache
MODELS=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0

for tool in python3 curl ffmpeg; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

if [ ! -x "$CACHE/venv/bin/python" ]; then
  python3 -m venv "$CACHE/venv"
fi
"$CACHE/venv/bin/python" -m pip install -q --disable-pip-version-check -r requirements.txt

mkdir -p "$CACHE/models"
fetch() {  # fetch FILE SHA256
  if [ ! -f "$CACHE/models/$1" ]; then
    curl -fL --progress-bar -o "$CACHE/models/$1.part" "$MODELS/$1"
    mv "$CACHE/models/$1.part" "$CACHE/models/$1"
  fi
  echo "$2  $CACHE/models/$1" | shasum -a 256 -c -
}
fetch kokoro-v1.0.onnx 7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5
fetch voices-v1.0.bin bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d

# espeak-ng ignores a data path longer than 160 characters, and the venv's own
# copy sits too deep, so the TTS step reads this short copy instead.
if [ ! -f "$CACHE/esd/phontab" ]; then
  src=$("$CACHE/venv/bin/python" -c 'import espeakng_loader, pathlib; print(pathlib.Path(espeakng_loader.__file__).parent / "espeak-ng-data")')
  rm -rf "$CACHE/esd" && cp -R "$src" "$CACHE/esd"
fi
echo "toolchain ready in $(pwd)/$CACHE"
