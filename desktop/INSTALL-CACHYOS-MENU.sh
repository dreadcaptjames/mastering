#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$dir"
python - "$root" "$dir" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
dir = Path(sys.argv[2])
script = root / 'RUN-MASTERFORGE-CACHYOS.sh'
icon = root / 'masterforge_python' / 'assets' / 'icon.png'
# desktop file quotes paths containing spaces; no shell interpretation.
exec_line = 'Exec="' + str(script).replace('\\', '\\\\').replace('"', '\\"') + '"'
content = f'''[Desktop Entry]
Type=Application
Name=MasterForge AI
Comment=Offline Python music mastering studio
{exec_line}
TryExec=/usr/bin/env
Icon={icon}
Terminal=false
Categories=AudioVideo;Audio;AudioVideoEditing;
StartupNotify=true
'''
(dest := dir / 'masterforge-ai-python.desktop').write_text(content, encoding='utf-8')
print(f'Installed menu launcher: {dest}')
PY
chmod +x "$root/RUN-MASTERFORGE-CACHYOS.sh"
