# MasterForge AI

**Current desktop release: v0.10.1 (Python)**

MasterForge AI is a local, privacy-first music mastering studio for Windows and CachyOS / Arch Linux. It includes the **Dynamic Signature** mastering profile, whole-song analysis, section-responsive gain and dynamics, tonal and stereo processing, full-track waveforms and scrubbing, A/B listening, and WAV / MP3 / M4A output. Its UI provides six color themes, four aesthetics, and user-defined startup mastering defaults.

## Current Python desktop application

The complete current source is in **[desktop/](desktop/)**. It is directly launchable from extracted source using Python and FFmpeg. No Electron, Node.js, GitHub Actions, cloud processing, or GitHub account is needed to run it locally.

### Windows

1. Download/clone this repository and open the `desktop` directory.
2. Install Python 3.11+ with Tcl/Tk included, if needed.
3. Run `RUN-MASTERFORGE-WINDOWS.bat` to set up and launch the Python app.
4. Optional: run `BUILD-WINDOWS-EXE.bat` or `BUILD-WINDOWS-INSTALLER.bat` locally to package it.

### CachyOS / Arch Linux

Install the dependencies:

```bash
sudo pacman -S --needed python tk ffmpeg
```

Then from `desktop/` run:

```bash
chmod +x RUN-MASTERFORGE-CACHYOS.sh
./RUN-MASTERFORGE-CACHYOS.sh
```

Optional: run `INSTALL-CACHYOS-MENU.sh` to add a local desktop-menu shortcut, or `BUILD-CACHYOS-APP.sh` to build a standalone app.

### Tests

From the `desktop/` directory run:

```bash
python -m unittest discover -s tests -v
```

UI tests need a graphical desktop; on a headless Linux runner use `xvfb-run -a python -m unittest discover -s tests -v`.

See [desktop/README.md](desktop/README.md) for complete instructions and [desktop/DYNAMIC-MASTERING.md](desktop/DYNAMIC-MASTERING.md) for the mastering chain and its limitations.

## Web Studio v1.0 beta — browser-native Dynamic Signature

The repository root now contains an **upgraded browser-native mastering studio**, hosted as static files on GitHub Pages or any HTTPS static host. The web edition features:

- Full-song, 2-second window analysis of quiet, dense and transient-rich passages
- Time-varying Signature gain and EQ, adaptive tonal shaping, guarded stereo widening, conditional compression
- Gated K-weighted integrated loudness **estimates**, bounded peak protection with a 4× intersample-peak **estimate**
- A/B player, waveform/scrubbing, Natural / Balanced / Impact / Signature, WAV / MP3 / M4A export, six themes × four aesthetics
- **Save current as default** for personal mastering preferences (new-install default: Signature + Streaming / -14 LUFS)
- Offline-capable Home Screen web application after service worker caching

Music is processed entirely in the browser in local mode. It is **not** sonically identical to Python/FFmpeg yet; compression, limiting and meter calibration differ. Output formats and long-song capacity depend on the device and browser. See [Web Dynamic Mastering Technical Notes](docs/WEB-DYNAMIC-MASTERING.md).

### Web development test

```bash
node tests/web-mastering.test.cjs
```

## Earlier web edition and deployment notes


The repository root was updated from v0.8.2 to browser-native Web Studio v1.0 beta. The Python desktop application under `desktop/` remains untouched.

## Privacy and status

Local desktop processing stays on your machine. No sample songs, user music, installer binaries, or build artifacts are committed here. The mastering algorithm is experimental DSP and has not been independently certified as professional mastering quality.

