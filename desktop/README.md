# MasterForge AI v0.10.1 — Personal Startup Defaults

**New in this release:** The Python desktop edition remembers each user's chosen mastering style, loudness intention, and fine-tuning controls. It starts with **Signature** and **Streaming (-14 LUFS)** on a fresh installation, but users can choose any combination, then click **★ Save Current as Default** under *Loudness Intention*. The saved settings load automatically at the next launch. **Reset Startup Defaults** returns to Signature/Streaming with neutral fine-tuning. You can still change any setting per song without changing your saved default.

The appearance settings (six palettes and four aesthetics) are saved independently and remain unchanged. Settings are stored per local user in `MasterForge AI/preferences.json` inside `%APPDATA%` on Windows or `$XDG_CONFIG_HOME` (normally `~/.config`) on CachyOS/Linux. Mastering audio is **not uploaded**, and no account or network connection is required for saving preferences. The v0.10.0 dynamic Signature mastering engine, waveform player, A/B comparisons, exports, launchers, and builders are unchanged.

---

# MasterForge AI v0.10.0 — Dynamic Mastering

**Complete Python desktop application for Windows and CachyOS.** Signature now responds to changing quiet passages, dense sections, and transient-heavy material as the recording progresses. Processing uses time-varying, smoothed section gain plus real-time RMS compression and conditional frequency-dependent dynamic EQ. This goes beyond the v0.9.7 whole-song *static* EQ recipe.

[Read the exact new signal chain, detection rules and limitations](DYNAMIC-MASTERING.md).

The existing Studio Console interface, Original/Mastered waveforms and scrubber, themes, presets, WAV/MP3/M4A exports, and existing launch/build scripts are preserved. No GitHub or Electron is needed.

# MasterForge AI — Signature Full-Song Analysis v0.9.7

**Complete Python desktop application for Windows and CachyOS.** This update changes only the audio analysis that guides the Signature mastering profile. The existing Studio Console UI, four mastering modes, playback, full-track waveforms, A/B scrubber, WAV/MP3/M4A export, themes, and existing launch and installer scripts are preserved.

## What's changed

- **Before:** tonal EQ and stereo measurements were based on just the first 35 seconds of each track.
- **Now:** Signature examines the **entire decoded recording** for five frequency-band measurements, stereo correlation and mid/side energy, including choruses, solos and outros.
- Audio is decoded as 16-kHz stereo PCM and **processed in streaming chunks**, avoiding a giant in-memory copy of long songs. Streaming takes additional processing time for longer recordings.
- Mastering progress indicates whole-song analysis. Processing JSON reports contain `recipe.sampled_profile.seconds_analyzed` and `recipe.sampled_profile.analysis_coverage: "entire_recording"`.
- One overall EQ/stereo profile is still derived from the entire song and applied consistently during the master. **This is not dynamic per-section EQ or a trained AI model.**
- The previous **six-hour input-duration safeguard remains**. Very long or unusual files are subject to FFmpeg decoding and processing-time limitations.

## Tested

- Full 3:39 `Liberty day is coming.m4a` analyzed across **219.61 seconds** and rendered a Signature 24-bit master successfully.
- 80-second test with identical 42-second intros but different final 38 seconds caused **different high-band profiles and Signature EQ choices**.
- All **21 Python regression tests passed** under a Linux virtual display; includes WAV/MP3/M4A exports, timeline and waveform, and theming tests.
- The source is ready for Windows and CachyOS but was not graphically tested on those physical machines.

## Running it

Unzip the complete package and launch the existing scripts as before: `RUN-MASTERFORGE-WINDOWS.bat` on Windows or `RUN-MASTERFORGE-CACHYOS.sh` on CachyOS. No GitHub, Electron or Node.js required. Previously compiled executables need to be rebuilt to incorporate this code change.

---

# MasterForge AI — Studio Console Facelift v0.9.6

This is the **complete Python desktop application** for Windows and CachyOS, not an incremental patch. The release refreshes the interface only; the mastering engine and launch/install scripts have not been modified.

## What's new in this visual release

- Restyled premium Studio Console header, with a clear local-engine status and prominent export action.
- A compact session overview with visual Import → Shape → Master → Export stages.
- Improved three-column workspace spacing, typography and track header.
- More detailed full-length waveform visualization with subtle signal depth, a distinct playhead and true time markers.
- A **measured loudness comparison rail** that displays the source and rendered master using actual integrated LUFS values when those are available; it does not simulate loudness readings.
- Refined playback and export controls, full-duration scrubber and Original/Mastered A/B views.
- Theme Studio retains its scroll position while the user experiments with the 6 color palettes and 4 interface aesthetics.
- Consistent light-theme styling, including Arctic Precision.

The existing engine, Natural/Balanced/Impact/Signature profiles, WAV/MP3/M4A exports, themes, Windows/CachyOS launchers and build scripts are preserved. No Electron, GitHub, or new Python GUI dependency is required.

## Get started

1. Extract the **complete** ZIP into a new folder. You do not need earlier versions or patches.
2. On Windows, double-click `RUN-MASTERFORGE-WINDOWS.bat`.
3. On CachyOS, open a terminal in the extracted directory and run:

   ```bash
   chmod +x RUN-MASTERFORGE-CACHYOS.sh
   ./RUN-MASTERFORGE-CACHYOS.sh
   ```

The original optional Windows build scripts and CachyOS application-menu integration scripts remain included and unchanged.

## Tested

- 20/20 existing Python regression tests passed in a virtual Linux graphical environment.
- All 24 palette/aesthetic combinations launched and refreshed correctly.
- A 3:39 source/master pair was loaded to check the full-length display, original/mastered presentation and scrubber.
- Tested that a theme change maintains the 3:20 scrubber position and keeps the Theme Studio section visible.

Windows and a physical CachyOS desktop have not been visually tested in this release. Preview images are in `previews/` and are included for reference; no audio files are included in the ZIP.

---

# MasterForge AI — Windows Build Test Compatibility Fix v0.9.5.1

The Windows build previously stopped when the timeline test compared a Windows
file path (using `\`) against a hard-coded Unix path (using `/`). This was a
test assertion mistake, **not** a playback, waveform or audio-mastering failure.

The full source package now compares the requested playback path to the selected
file using Python's platform-native `Path` semantics, so it works consistently on
Windows and Linux. No mastering DSP, UI behavior, launcher or build logic was
changed. The original/mastered waveforms, full-duration scrubber, mastering modes,
all themes, and WAV/MP3/M4A exports are preserved.

**Build on Windows:** Extract this full archive to a new directory, open the
`MasterForge-AI-Python-Desktop` folder, and run `BUILD-WINDOWS-EXE.bat` or
`BUILD-WINDOWS-INSTALLER.bat`. The latter invokes the EXE build and also requires
Inno Setup. There is no need to merge previous patch archives.

**Verification:** The complete source test suite passes on Linux, including the
fixed timeline assertion. This environment cannot run the Windows compiler,
so the actual `.exe` build still needs verification on your Windows PC.

---

# MasterForge AI — A/B Waveform + Full-Track Scrubber Fix v0.9.5

This is a **Python desktop UI/playback fix**. The mastering DSP, presets, exports,
color themes, local launchers, Windows build scripts and CachyOS menus remain as before.
No Electron, additional Python package, or GitHub step is required.

## What's fixed

- The playback bar has a visible, clickable and draggable **scrubber thumb**.
- Its range now uses the **full duration of the selected recording**, rather than a
  fixed 100-second range. Scrub from 00:00 through the true end, even on long songs.
- The selected **Original** and **Mastered** modes render separate waveforms.
  MasterForge measures the mastered file's waveform after creating the master.
- Both waveform overviews use the **same amplitude scale** (not one independent
  auto-normalization per track). This makes their level/dynamic differences visible.
- Mastering automatically switches the visual comparison to the completed master.
- Changing the theme preserves the scrubber position and waveform selection.
- The full-song waveform is clickable to jump directly to a location.
- Selected-file time labels and playhead track the full duration of that file.

## Updating an existing Python-source installation

1. Close MasterForge.
2. Back up your existing `masterforge_python` folder.
3. Extract the small **Waveform and Scrubber Patch** archive.
4. Copy `engine.py`, `main.py`, and `polished_ui.py` from its `masterforge_python`
   folder into the same folder in your working MasterForge installation.
   Replace only those three files. Leave launchers, installers, and dependencies alone.
5. Run MasterForge normally. Load a track, create a master and click Original /
   Mastered. Drag the scrubber or click the waveform to seek anywhere in the song.

You may instead extract the **full v0.9.5 source package** and run that normally.
A compiled `.exe` won't change when source files are replaced; it would need a
new build. This patch targets the already-working Python source installation.

**Preview playback still requires FFplay**, as in earlier releases. The scrubber,
waveform views and exporting work independently of FFplay; if FFplay is absent,
pressing Play will show a setup notice.

## Verification

20 local regression tests passed, including 219-second timeline movement,
Original/Mastered switching, waveform gain difference, and seeking past 100 s.
A Linux desktop GUI workflow imported the user's existing 3:39 source and
master, displayed distinct waveforms, and dragged the scrubber to ~3:20.
A new Signature render also generated and displayed its own waveform. Windows
and CachyOS physical-device behavior has not been independently retested.

---

# MasterForge AI — Full-Track Waveform Fix v0.9.4

The waveform now shows the entire duration of the imported recording, including songs longer than a minute. The waveform engine decodes audio incrementally and computes time-aligned peaks instead of filtering the audio to 150 Hz, which could hide much of the music. The preview does not cut off at a fixed song length or load a full PCM recording into RAM. Resizing the application preserves late peaks; the waveform's timeline and playhead correspond to the full song.

**Unchanged:** the mastering algorithms, loudness targets, Signature profile, WAV/MP3/M4A export code, themes, launchers, and installer/build scripts. This is a display/analysis improvement only. Source installations do not need to reinstall Python or FFmpeg.

**Small patch:** Copy `engine.py` and `polished_ui.py` from the `masterforge_python/` directory in the patch ZIP into the same directory in your existing MasterForge installation. Back up the originals first. Launch MasterForge as usual. A prebuilt `.exe` cannot be updated by copying Python files; it needs a new build if that's your method of running the app.

---

# MasterForge AI — Python Desktop · Studio Visual Refresh v0.9.3


## Studio visual refresh (v0.9.3)

This release focuses **only on making the Python desktop interface look and feel
closer to the earlier Electron studio**. The existing Python/FFmpeg mastering engine,
Windows/CachyOS run scripts, Windows installer and build scripts are preserved.
There is **no Electron, browser or extra Python GUI dependency**.

What's new: a refined studio header and hero, three-column layout, redesigned
mastering cards, rounded action controls, richer waveform presentation, measured
audio tiles, clearer export controls, touch-friendly spacing, and a redesigned
Theme Studio at the bottom. All six palettes and four aesthetics remain available,
with settings stored on the computer. A small UI-thread safety fix makes exports
read the selected bitrate before starting the background encoder.

### Updating without changing your installer setup

If you run from Python source and already have a working MasterForge folder:

1. Make a backup of that folder.
2. Copy the **`masterforge_python`** folder from this release over the existing
   `masterforge_python` folder, preserving your launch scripts.
3. Start MasterForge the same way you do now, using your existing launcher.

Alternatively, the separate **UI-only patch ZIP** contains just the two changed
Python files (`main.py` and `polished_ui.py`). Copy both into your existing
`masterforge_python` directory. No virtual-environment reinstall is needed.

If you currently launch a **compiled `.exe`**, Python source edits cannot change
that binary. Your existing installer remains valid; a new executable must
be built only when you choose to update the installed copy.

Validation: 14 source/regression checks, a graphical test of all 24 appearance
combinations, and a local import → Signature master → M4A export workflow on Linux.
Actual appearance on Windows and CachyOS desktops should be checked locally.

---

**Native Python desktop music mastering for Windows and CachyOS.** No Electron, Node.js, GitHub, cloud mastering service, or browser required. This is a new Python/Tkinter interface and a Python implementation of MasterForge's desktop FFmpeg processing chain.

## Windows setup installer (new)

**A proper Windows installer can now be built without GitHub.** It uses Inno Setup and installs the already-tested `MasterForge-AI.exe` into `%LOCALAPPDATA%\Programs\MasterForge AI`. The wizard creates an uninstall entry in Windows **Settings → Installed apps**, a Start menu shortcut, and an optional desktop shortcut. It is per-user and does not need administrator permissions. Reinstalling a later release with the same Inno `AppId` upgrades the existing installation.

**To build Setup.exe on your Windows PC:**

1. Install [Inno Setup](https://jrsoftware.org/isdl.php) (6 or 7), using its default installation path. Commercial distribution may require an Inno Setup license; check the upstream terms.
2. Extract this ZIP into a folder. If you have a previously verified `dist\MasterForge-AI.exe` from v0.9.2, you may copy it into this new folder's `dist` folder to avoid rebuilding Python; otherwise, the installer builder automatically runs the EXE builder first.
3. Double-click `BUILD-WINDOWS-INSTALLER.bat`. It verifies that the portable EXE can import the engine and start FFmpeg, then compiles the installer.
4. Run **`dist\MasterForge-AI-Setup-0.9.2.exe`** and follow the installation wizard.
5. Launch from the Windows Start menu. To remove it later, use **Settings → Apps → Installed apps → MasterForge AI → Uninstall**.

The downloadable source ZIP **does not contain a prebuilt Setup.exe**; the compiler must run on Windows using a Windows-built EXE. The installer has not yet been compiled/tested here on Windows.

**Privacy & updating:** Your tracks remain local. The installer does not bundle your songs or project audio. The uninstaller removes the application, not your exported masters or per-user saved settings. For a later version, keep the existing `AppId` in `installer/MasterForgeAI.iss` and increase both the app and installer versions.

**Security:** This installer is not code-signed. Windows SmartScreen may display an Unknown Publisher warning. For a verified publisher and fewer warnings when distributing, obtain and use a legitimate Authenticode code-signing certificate; don't bypass security warnings for untrusted downloads. Inno Setup compilation alone is not equivalent to publisher verification.

## v0.9.2 packaged Windows EXE fix

**Fixes the `No module named 'engine'` crash in the packaged Windows EXE.**
The earlier PyInstaller builder froze `masterforge_python/main.py` as a top-level
script. That discards the Python package context; the fallback `from engine import ...`
then failed inside the frozen app. The new builder freezes `run_masterforge.py`,
which imports `masterforge_python.main` and `masterforge_python.engine` by their
proper package names. It also bundles assets in the correct resource location.

**Crucially, the Windows build script now launches the completed EXE in a headless
`--self-test` mode, checking both the Python engine import and the actual FFmpeg
executable.** It fails with a diagnostic if the packaged EXE cannot start these
components, instead of reporting success for a broken executable. Two source
regression tests cover the entry point and self-test.

**Windows instructions:** Download and extract this entire archive into a NEW
folder. Open the `MasterForge-AI-Python-Desktop` folder and double-click
`BUILD-WINDOWS-EXE.bat`. Do not reuse the old v0.9.1 `dist` executable. When the
builder says `[SUCCESS] Built and verified`, open `dist\MasterForge-AI.exe`.
You can inspect `dist\masterforge-build-check.txt` for its engine and FFmpeg
self-test results.

**Verification limitation:** The source and CLI self-test can be run on Linux,
but this environment does not have PyInstaller and cannot compile or launch a
Windows EXE. The post-build self-test is designed to perform that crucial check
on your Windows PC.

## v0.9.1 Windows build fix

The v0.9.0 build could stop at the WAV codec test on Windows when only FFmpeg was bundled (without `ffprobe.exe`). The text-based FFmpeg probe returned a string such as `pcm_s24le ([1][0][0][0] / 0x0001)`, even though the actual codec is `pcm_s24le`. v0.9.1 normalizes that codec field and adds a regression test for the no-ffprobe path, covering WAV, MP3 and M4A. No mastering sound-processing settings were changed.

**To retry:** Extract this archive into a fresh folder and double-click `BUILD-WINDOWS-EXE.bat`. The new package-aware entrypoint and both build scripts must be kept together; do not replace only the engine file.

## Quick start — Windows 10/11

1. Install Python **3.11 or later**, with **Tcl/Tk** enabled (the official Windows Python installer includes it). The source app can use Python 3.15 if tkinter is present; to build a portable EXE, use a Python version supported by the installed PyInstaller release.
2. Extract **all** files in this ZIP to a normal folder, such as `Documents\MasterForge AI Python`.
3. Double-click **`RUN-MASTERFORGE-WINDOWS.bat`**. It creates a virtual environment in `.venv` and checks for FFmpeg. If needed, it installs the optional `imageio-ffmpeg` binary into that environment on first run (internet needed). No Electron or Node installation occurs.
4. Import an audio file and choose Natural, Balanced, Impact or Signature. Choose a target LUFS level, then **Create Master**. Preview A/B if FFplay is installed, and export your audio in WAV/MP3/M4A.

**Build a portable Windows `.exe` locally:** Double-click **`BUILD-WINDOWS-EXE.bat`** on Windows. It installs PyInstaller and `imageio-ffmpeg` into `.venv`, runs the audio-engine tests, and attempts to create **`dist\MasterForge-AI.exe`** containing Python, the interface, and a bundled FFmpeg binary. This is a **portable EXE, not an MSI/Setup installer**. The first build requires internet access. This build workflow has not been executed on Windows in the test environment; compatibility with Python 3.15 depends on the PyInstaller version available on your PC.

**Playback note:** For in-app Original/Mastered A/B playback and seeking, install the **full FFmpeg distribution including `ffplay.exe`** and add it to PATH. The optional `imageio-ffmpeg` wheel contains FFmpeg for processing but **not** FFplay. All mastering, loudness measurement, and exports work without FFplay. You can still listen to exported files in your usual player.

## Quick start — CachyOS / Arch Linux

In Konsole:

```bash
sudo pacman -S --needed python tk ffmpeg
```

Extract the ZIP, open a terminal inside that extracted folder, and run:

```bash
chmod +x RUN-MASTERFORGE-CACHYOS.sh INSTALL-CACHYOS-MENU.sh
./RUN-MASTERFORGE-CACHYOS.sh
```

To add MasterForge to the application launcher after confirming it runs:

```bash
./INSTALL-CACHYOS-MENU.sh
```

The desktop entry points to the extracted source folder, so keep that folder where you installed it. **Do not run the app with `sudo`.** FFplay is normally supplied by your distribution's FFmpeg package; if not, installing a suitable `ffplay` player enables in-app A/B monitoring.

**Build an optional standalone Linux executable locally:** Install `python-pip` if necessary and run:

```bash
chmod +x BUILD-CACHYOS-APP.sh
./BUILD-CACHYOS-APP.sh
```

The build attempts to create `dist/MasterForge-AI`, using PyInstaller and a bundled FFmpeg binary. This build requires initial internet access. It is **not** an AppImage or pacman package and has not been verified on physical CachyOS hardware.

## Mastering features

- **Natural / Balanced / Impact / Signature (Beta)** — four tonal/dynamic profiles. Signature uses a 35-second local spectral and stereo analysis to make bounded adjustments; the entire song is processed for the master.
- **LUFS and true-peak measurements** — FFmpeg's `loudnorm` two-pass analysis and 24-bit, 48 kHz stereo WAV rendering.
- **Dynamic protection** — compression is selectively bypassed when it would unnecessarily flatten the source. Stereo enhancement is restricted on mono and phase-risky material.
- **Loudness options** — -16, -14, -12, -11, -10 and -9 LUFS intentions. Some may not be achievable on every source, and higher loudness can reduce punch.
- **Exports** — 24-bit WAV, MP3 and AAC-in-M4A at 128 / 192 / 256 / 320 kbps. Changing export format does not require remastering.
- **Waveform and A/B preview** — Original/Mastered toggle, seek and level-matched comparison if FFplay is available.
- **Processing report** — export JSON with measured before/after LUFS, true peaks, EQ parameters, stereo correlation and warnings.
- **Themes** — Obsidian Mint, Midnight Violet, Vintage Console, Arctic Precision, Ember Studio, Cyberwave; four interface aesthetics. Theme preferences are saved on this PC.
- **Privacy** — all files and FFmpeg processing remain on your computer. No third-party service or user account is involved. Input audio is never overwritten.

### Format and performance caveats

- Source audio: WAV, MP3, AAC/M4A, FLAC, Ogg/Opus and other formats supported by FFmpeg, mono or stereo. The Python implementation does not impose the older 4-minute, 12-minute, or 80 MB input limit. Processing requires local disk space, especially for long 24-bit masters; there is a six-hour safety cap on a single render.
- Source analysis runs on a bounded excerpt; actual mastering, loudness measurement, and output validation cover the complete recording. FFmpeg processes files in a streaming fashion; the full uncompressed song does not need to be loaded into Python RAM.
- A compressed export can create new codec-induced peaks. For important releases, independently verify peaks and audition each delivery file. The app does not assert equivalence to any commercial mastering service.
- Signature remains experimental. Proper listening comparisons across varied source material are needed before claiming a consistent professional mastering result.
- Python Desktop v0.9 is separate from the phone/tablet web edition. The **existing v0.8.2 web app is unchanged**.

## Project files

- `masterforge_python/main.py` — native Python/Tkinter UI.
- `run_masterforge.py` — package-aware entry point, with packaged EXE engine/FFmpeg self-test.
- `masterforge_python/engine.py` — Python audio analysis, rendering, and export logic using FFmpeg.
- `RUN-MASTERFORGE-WINDOWS.bat` / `RUN-MASTERFORGE-CACHYOS.sh` — start native desktop app.
- `BUILD-WINDOWS-EXE.bat` / `BUILD-CACHYOS-APP.sh` — optional **local** PyInstaller builds.
- `INSTALL-CACHYOS-MENU.sh` — per-user Linux desktop shortcut.
- `tests/test_engine.py` — real WAV, MP3, AAC/M4A codec and audio-rendering integration tests.
- `python-desktop-preview.png` — updated studio UI screenshot captured from the Python app in a Linux virtual display using a real 24-second audio excerpt.

### Testing

To run the engine suite yourself:

```bash
python -m unittest discover -s tests -v
```

Six audio integration tests plus two launcher regression tests passed in the Linux development environment, and an excerpt from a supplied original music track was also rendered successfully with Signature processing. The interface was smoke-tested in a virtual Linux desktop. **Windows GUI and packaged Windows/CachyOS binary builds have not been executed or verified on those specific operating systems.**

### Licensing considerations

This source package includes an original Python implementation, plus the existing MasterForge icon assets. It does **not** ship proprietary music, audio references, FFmpeg executables, or Python interpreters. If redistributing a built executable with bundled FFmpeg, review the exact FFmpeg build's LGPL/GPL obligations and any other dependencies' licenses.
