"""Package-safe MasterForge AI entry point (including PyInstaller builds).

Never freeze masterforge_python/main.py directly: doing so discards its
package context and makes relative imports of masterforge_python.engine fail.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

# Imports are deliberately at module scope. This makes PyInstaller analyze
# the full package dependency graph, including the FFmpeg-based engine.
from masterforge_python.engine import Engine, VERSION
from masterforge_python.main import main


def self_test(report_path: Path) -> int:
    """Verify the packaged executable has its engine and an executable FFmpeg.

    The Windows build script calls this on the final .exe. In --windowed mode
    console output may be invisible, so write an easy-to-verify report file.
    """
    try:
        engine = Engine()
        result = subprocess.run(
            [engine.ffmpeg, "-version"], capture_output=True, text=True,
            timeout=30, check=True,
        )
        if "ffmpeg version" not in result.stdout.lower():
            raise RuntimeError("FFmpeg did not respond with version information")
        line = result.stdout.splitlines()[0]
        bundled_detail = ""
        if getattr(sys, "frozen", False):
            # A portable build must not depend on the user's PATH containing
            # ffmpeg.exe. PyInstaller is instructed to collect imageio-ffmpeg.
            import imageio_ffmpeg
            bundled_ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
            if not bundled_ffmpeg.is_file():
                raise RuntimeError("Bundled FFmpeg executable not found")
            bundled_result = subprocess.run(
                [str(bundled_ffmpeg), "-version"], capture_output=True,
                text=True, timeout=30, check=True,
            )
            if "ffmpeg version" not in bundled_result.stdout.lower():
                raise RuntimeError("Bundled FFmpeg executable failed to start")
            bundled_detail = f"Bundled FFmpeg: {bundled_ffmpeg}\n"
        report_path.write_text(
            f"READY: MasterForge AI v{VERSION}\n"
            f"Engine module: {Engine.__module__}\n"
            f"FFmpeg executable: {engine.ffmpeg}\n"
            f"{bundled_detail}"
            f"{line}\n", encoding="utf-8"
        )
        return 0
    except Exception as exc:
        report_path.write_text(f"FAILED: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return 1


def cli(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "--self-test":
        return self_test(Path(args[1]))
    if args:
        # Avoid silently accepting misspelled diagnostic arguments.
        return 2
    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
