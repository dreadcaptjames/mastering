#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
for cmd in python ffmpeg; do
  command -v "$cmd" >/dev/null || { echo "Install $cmd first" >&2; exit 1; }
done
python -c 'import tkinter' || { echo 'Install Tk: sudo pacman -S tk' >&2; exit 1; }
python -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --upgrade pyinstaller imageio-ffmpeg
python -m unittest discover -s tests -v
python -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name MasterForge-AI \
  --add-data 'masterforge_python/assets:masterforge_python/assets' \
  --paths "$PWD" \
  --hidden-import masterforge_python.engine \
  --collect-all imageio_ffmpeg run_masterforge.py
SMOKE_REPORT="$PWD/dist/masterforge-build-check.txt"
rm -f "$SMOKE_REPORT"
"$PWD/dist/MasterForge-AI" --self-test "$SMOKE_REPORT"
if [[ ! -f "$SMOKE_REPORT" ]] || ! grep -q '^READY:' "$SMOKE_REPORT"; then
  echo "[ERROR] Packaged executable could not import the engine / start FFmpeg" >&2
  [[ -f "$SMOKE_REPORT" ]] && cat "$SMOKE_REPORT" >&2
  exit 1
fi
cat "$SMOKE_REPORT"
printf '\nBuilt and verified: dist/MasterForge-AI\n'
