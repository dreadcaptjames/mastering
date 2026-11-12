#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if ! command -v python >/dev/null 2>&1; then
  echo 'Python is missing. Run: sudo pacman -S --needed python tk ffmpeg' >&2
  exit 1
fi
if ! python -c 'import tkinter' 2>/dev/null; then
  echo 'Tkinter is missing. Run: sudo pacman -S --needed python tk ffmpeg' >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo 'FFmpeg is missing. Run: sudo pacman -S --needed ffmpeg' >&2
  exit 1
fi
exec python -m masterforge_python
