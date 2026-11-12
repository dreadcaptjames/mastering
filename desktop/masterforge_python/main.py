"""MasterForge AI — Native Python/Tkinter mastering workstation.

Works on Windows and Linux with standard-library UI; FFmpeg does all DSP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Always import the engine as part of the masterforge_python package.
# Freezing this module as a standalone script loses its package context;
# the PyInstaller entry point is run_masterforge.py at the project root.
from .engine import Engine, MasterForgeError, Settings, VERSION, TARGETS, PRESETS, ffplay_binary

APP_NAME = "MasterForge AI"

PALETTES = {
    "Obsidian Mint": dict(bg="#0A1418", panel="#142329", panel2="#1D3037", text="#EAF8F4", muted="#9BB5BA", accent="#69E5BB", line="#2B454C", wave="#80F0C8", warn="#F7C36A", good="#78DFA6"),
    "Midnight Violet": dict(bg="#100E20", panel="#1D1A31", panel2="#2C2448", text="#F2EDFF", muted="#AFA7CB", accent="#AA8BFF", line="#3D345C", wave="#B399FF", warn="#FFC078", good="#B6E7C4"),
    "Vintage Console": dict(bg="#1A201B", panel="#2C342B", panel2="#3E4837", text="#F5ECD5", muted="#C5C4AD", accent="#E0AD65", line="#505C45", wave="#E5C48A", warn="#FFD27E", good="#B0DBAD"),
    "Arctic Precision": dict(bg="#EFF5F6", panel="#FFFFFF", panel2="#DCE9EE", text="#223B46", muted="#567079", accent="#167E98", line="#B8CED5", wave="#1E9AAA", warn="#9E5C13", good="#12806D"),
    "Ember Studio": dict(bg="#1C1514", panel="#2D221E", panel2="#452F28", text="#FFF2E8", muted="#CDB1A4", accent="#FF9861", line="#583C32", wave="#FFB16D", warn="#FFC36E", good="#B6DDB1"),
    "Cyberwave": dict(bg="#0C1021", panel="#181E35", panel2="#23374B", text="#E8F8FF", muted="#96B6C9", accent="#1DDDE4", line="#2C5360", wave="#F76AC8", warn="#FFCF6C", good="#91F6D7"),
}
AESTHETICS = ("Digital Studio", "Analog Hardware", "Precision Minimalism", "Hybrid")
FORMATS = ("WAV", "MP3", "M4A")
EXTENSIONS = {"WAV": ".wav", "MP3": ".mp3", "M4A": ".m4a"}
LOUDNESS_CHOICES = (
    "-16 LUFS · Open", "-14 LUFS · Streaming", "-12 LUFS · Energetic",
    "-11 LUFS · Signature", "-10 LUFS · Loud", "-9 LUFS · Max Impact",
)
# First launch defaults requested for MasterForge Desktop. Each user may save
# a different combination from the controls in the mastering workspace.
FACTORY_MASTERING_DEFAULTS = {
    "preset": "signature", "target": "-14 LUFS · Streaming",
    "warmth": 0.0, "clarity": 0.0, "intensity": 0.0,
}


def normalized_mastering_defaults(raw: object) -> dict:
    """Validate user-editable preferences before they reach Tk or the DSP engine."""
    valid = dict(FACTORY_MASTERING_DEFAULTS)
    if not isinstance(raw, dict):
        return valid
    if raw.get("preset") in PRESETS:
        valid["preset"] = raw["preset"]
    if raw.get("target") in LOUDNESS_CHOICES:
        valid["target"] = raw["target"]
    for name, bound in (("warmth", 3.0), ("clarity", 3.0), ("intensity", 2.0)):
        try:
            num = float(raw.get(name, valid[name]))
            if -bound <= num <= bound:  # also rejects NaN/Infinity
                valid[name] = num
        except (ValueError, TypeError, OverflowError):
            pass
    # Same validation contract as the mastering engine.
    Settings(preset=valid["preset"], target=int(valid["target"].split()[0]),
             warmth=valid["warmth"], clarity=valid["clarity"],
             intensity=valid["intensity"]).validate()
    return valid


def mastering_defaults_description(defaults: dict) -> str:
    preset = defaults["preset"].capitalize()
    loudness = defaults["target"].split("·", 1)[-1].strip()
    return f"STARTUP: {preset}  ·  {loudness} ({defaults['target'].split()[0]} LUFS)"


def user_config_file() -> Path:
    if os.name == "nt":
        root = Path(os.getenv("APPDATA", str(Path.home())))
    else:
        root = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return root / "MasterForge AI" / "preferences.json"


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class MasterForgeWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} — Python Desktop {VERSION}")
        self.root.geometry("1340x900")
        self.root.minsize(990, 650)
        self.settings_file = user_config_file()
        prefs = self._read_prefs()
        self.palette = tk.StringVar(value=prefs.get("palette", "Obsidian Mint"))
        self.aesthetic = tk.StringVar(value=prefs.get("aesthetic", "Digital Studio"))
        self.startup_mastering = normalized_mastering_defaults(prefs.get("mastering_defaults"))
        self.preset = tk.StringVar(value=self.startup_mastering["preset"])
        self.warmth = tk.DoubleVar(value=self.startup_mastering["warmth"])
        self.clarity = tk.DoubleVar(value=self.startup_mastering["clarity"])
        self.intensity = tk.DoubleVar(value=self.startup_mastering["intensity"])
        self.target = tk.StringVar(value=self.startup_mastering["target"])
        self.format = tk.StringVar(value="WAV")
        self.bitrate = tk.StringVar(value="256")
        self.ab_mode = tk.StringVar(value="Original")
        self.level_match = tk.BooleanVar(value=True)
        self.source: Path | None = None
        self.master: Path | None = None
        self.report: dict | None = None
        self.source_info: dict | None = None
        self.master_info: dict | None = None
        self.original_meter: dict | None = None
        # Raw, unnormalized PCM peak envelopes from the full file. The two
        # recordings are rendered at the SAME scale for a meaningful A/B view.
        self.original_waveform: list[float] = []
        self.master_waveform: list[float] = []
        self.waveform: list[float] = []
        self.busy = False
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.engine: Engine | None = None
        self.temp = tempfile.TemporaryDirectory(prefix="masterforge-python-")
        self.play_proc: subprocess.Popen | None = None
        self.play_start = 0.0
        self.play_offset = 0.0
        self._play_duration = 0.0
        self._seeking = False
        self.status = "Ready · Open an audio file to begin"
        try:
            self.engine = Engine()
        except MasterForgeError as exc:
            self.status = f"FFmpeg missing · {exc}"
        self._build()
        self._poll_after = self.root.after(180, self._poll)
        self._tick_after = self.root.after(250, self._play_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)
        self.root.bind("<Control-o>", lambda e: self.open_audio())
        self.root.bind("<Control-s>", lambda e: self.export_audio())
        self.root.bind("<space>", self._space)

    def _space(self, event) -> None:
        if event.widget.winfo_class() not in ("Entry", "TEntry", "Text"):
            self.toggle_play()

    def _read_prefs(self) -> dict:
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_prefs(self) -> bool:
        """Persist appearance and mastering defaults without clobbering either."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            preferences = self._read_prefs()
            preferences.update({
                "palette": self.palette.get(),
                "aesthetic": self.aesthetic.get(),
                "mastering_defaults": dict(self.startup_mastering),
            })
            staging = self.settings_file.with_suffix(".tmp")
            staging.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
            staging.replace(self.settings_file)
            return True
        except OSError:
            return False

    def _set_saved_defaults_message(self, detail: str = "") -> None:
        if hasattr(self, "saved_defaults_label"):
            self.saved_defaults_label.configure(text=mastering_defaults_description(self.startup_mastering))
        if detail:
            self.status = detail
            if hasattr(self, "status_label"):
                self.status_label.configure(text=detail)

    def save_mastering_defaults(self) -> None:
        """Explicit action: only Save as Default changes future startup choices."""
        candidate = normalized_mastering_defaults({
            "preset": self.preset.get(),
            "target": self.target.get(),
            "warmth": self.warmth.get(),
            "clarity": self.clarity.get(),
            "intensity": self.intensity.get(),
        })
        previous = self.startup_mastering
        self.startup_mastering = candidate
        if not self._save_prefs():
            self.startup_mastering = previous
            messagebox.showerror("Unable to save defaults", "MasterForge could not write your preferences file. Check folder permissions and try again.")
            return
        self._set_saved_defaults_message("Startup defaults saved · Your choices will load next time")

    def reset_mastering_defaults(self) -> None:
        """Restore the original Signature/Streaming startup combination."""
        previous = self.startup_mastering
        self.startup_mastering = dict(FACTORY_MASTERING_DEFAULTS)
        if not self._save_prefs():
            self.startup_mastering = previous
            messagebox.showerror("Unable to reset defaults", "MasterForge could not write your preferences file. Check folder permissions and try again.")
            return
        self.preset.set(self.startup_mastering["preset"])
        self.target.set(self.startup_mastering["target"])
        self.warmth.set(self.startup_mastering["warmth"])
        self.clarity.set(self.startup_mastering["clarity"])
        self.intensity.set(self.startup_mastering["intensity"])
        self._highlight_preset()
        self._set_saved_defaults_message("Startup defaults reset · Signature + Streaming")

    def _colors(self) -> dict:
        return PALETTES.get(self.palette.get(), PALETTES["Obsidian Mint"])

    def _style(self) -> None:
        c = self._colors()
        self.root.configure(bg=c["bg"])
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure("Studio.Horizontal.TProgressbar", troughcolor=c["panel2"], background=c["accent"], bordercolor=c["panel2"], lightcolor=c["accent"], darkcolor=c["accent"])
        st.configure("Studio.Horizontal.TScale", background=c["panel"], troughcolor=c["line"])
        st.configure("Studio.TCombobox", fieldbackground=c["panel2"], foreground=c["text"], background=c["panel2"], arrowcolor=c["accent"], bordercolor=c["line"], padding=7)
        st.map("Studio.TCombobox", fieldbackground=[("readonly", c["panel2"])], foreground=[("readonly", c["text"])])

    def _label(self, parent, text: str, size=11, bold=False, color="text", bg="panel", **kwargs):
        c = self._colors()
        font = ("Segoe UI" if os.name == "nt" else "DejaVu Sans", size, "bold" if bold else "normal")
        return tk.Label(parent, text=text, fg=c.get(color, color), bg=c.get(bg, bg), font=font, **kwargs)

    def _button(self, parent, text: str, command, *, primary=False, padx=14, pady=10):
        c = self._colors()
        aesthetic = self.aesthetic.get()
        bg = c["accent"] if primary else c["panel2"]
        fg = c["bg"] if primary else c["text"]
        relief = "ridge" if aesthetic in ("Analog Hardware", "Hybrid") else "flat"
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=c["wave"] if primary else c["line"],
                         activeforeground=c["bg"] if primary else c["text"],
                         relief=relief, bd=1 if relief != "flat" else 0,
                         cursor="hand2", padx=padx, pady=pady,
                         font=("Segoe UI" if os.name == "nt" else "DejaVu Sans", 10, "bold"),
                         disabledforeground=c["muted"], highlightthickness=0)

    def _panel(self, parent, pad=19, border=True):
        c = self._colors()
        rel = "groove" if self.aesthetic.get() == "Analog Hardware" else "flat"
        frame = tk.Frame(parent, bg=c["panel"], padx=pad, pady=pad,
                         relief=rel, bd=2 if rel == "groove" else 0,
                         highlightbackground=c["line"], highlightthickness=1 if border else 0)
        return frame

    def _section_title(self, parent, kicker: str, title: str) -> None:
        self._label(parent, kicker.upper(), 9, True, "accent").pack(anchor="w", pady=(0, 6))
        self._label(parent, title, 16, True).pack(anchor="w", pady=(0, 15))

    def _build(self):
        for child in self.root.winfo_children():
            child.destroy()
        self._style()
        c = self._colors()
        header = tk.Frame(self.root, bg=c["bg"], padx=26, pady=19)
        header.pack(fill="x")
        brand = tk.Frame(header, bg=c["bg"])
        brand.pack(side="left")
        self._label(brand, "◈  M A S T E R F O R G E", 18, True, bg="bg").pack(anchor="w")
        self._label(brand, "AI  /  PYTHON DESKTOP STUDIO     •     LOCAL AUDIO PROCESSING", 9, True, "muted", bg="bg").pack(anchor="w", pady=(5, 0))
        self._label(header, f"STUDIO ENGINE  •  {VERSION}", 10, True, "accent", bg="bg").pack(side="right", padx=3)
        stripe = tk.Frame(self.root, bg=c["accent"], height=2)
        stripe.pack(fill="x")
        stripe.pack_propagate(False)

        self.body_canvas = tk.Canvas(self.root, bg=c["bg"], borderwidth=0, highlightthickness=0)
        sb = ttk.Scrollbar(self.root, command=self.body_canvas.yview, orient="vertical")
        sb.pack(side="right", fill="y")
        self.body_canvas.configure(yscrollcommand=sb.set)
        self.body_canvas.pack(fill="both", expand=True)
        inner = tk.Frame(self.body_canvas, bg=c["bg"], padx=22, pady=22)
        self.content_window = self.body_canvas.create_window((0, 0), anchor="nw", window=inner)
        inner.bind("<Configure>", lambda e: self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all")))
        self.body_canvas.bind("<Configure>", lambda e: self.body_canvas.itemconfigure(self.content_window, width=e.width))
        self.body_canvas.bind_all("<MouseWheel>", self._wheel)

        self.row = tk.Frame(inner, bg=c["bg"])
        self.row.pack(fill="x")
        self.row.grid_columnconfigure(0, weight=1, minsize=263)
        self.row.grid_columnconfigure(1, weight=2, minsize=340)
        self.row.grid_columnconfigure(2, weight=1, minsize=263)
        self._left(self.row)
        self._center(self.row)
        self._right(self.row)
        self._themes(inner)
        footer = tk.Frame(inner, bg=c["bg"])
        footer.pack(fill="x", pady=(16, 10))
        self._label(footer, "OFFLINE BY DESIGN  •  Your music stays on your computer.", 9, bg="bg", color="muted").pack(side="left")
        self._label(footer, "Experimental DSP mastering · Verify critical releases with a trusted meter.", 9, bg="bg", color="muted").pack(side="right")

        statusbar = tk.Frame(self.root, bg=c["panel"], padx=24, pady=10)
        statusbar.pack(side="bottom", fill="x")
        self.status_label = self._label(statusbar, self.status, 10, color="muted")
        self.status_label.pack(side="left")
        self.progress = ttk.Progressbar(statusbar, length=150, mode="indeterminate", style="Studio.Horizontal.TProgressbar")
        self.progress.pack(side="right")
        self.progress.pack_forget()
        self._update_track_ui()
        self._render_waveform()
        self._refresh_master_ui()

    def _wheel(self, event):
        if event.delta:
            self.body_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _left(self, parent):
        c = self._colors()
        column = self._panel(parent)
        column.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._section_title(column, "01 / Shape", "Mastering style")
        desc = {
            "natural": ("NATURAL", "Keep detail & dynamics"),
            "balanced": ("BALANCED", "Polished, versatile tone"),
            "impact": ("IMPACT", "Punchy and energetic"),
            "signature": ("SIGNATURE  β", "Dynamic tone & clarity"),
        }
        self.preset_buttons = {}
        for mode, (name, detail) in desc.items():
            btn = self._button(column, f"{name}\n{detail}", lambda m=mode: self._choose_preset(m), padx=11, pady=12)
            btn.configure(justify="left", anchor="w", wraplength=220)
            btn.pack(fill="x", pady=4)
            self.preset_buttons[mode] = btn
        self._label(column, "FINE TUNE", 9, True, "accent").pack(anchor="w", pady=(23, 12))
        self.sliders = []
        for title, var, minimum, maximum in (("Warmth", self.warmth, -3, 3),
                                              ("Clarity", self.clarity, -3, 3),
                                              ("Intensity", self.intensity, -2, 2)):
            row = tk.Frame(column, bg=c["panel"])
            row.pack(fill="x", pady=(2, 12))
            self._label(row, title, 10, True).pack(side="left")
            value = self._label(row, f"{var.get():+.1f}", 10, color="accent")
            value.pack(side="right")
            scale = ttk.Scale(column, from_=minimum, to=maximum, variable=var,
                              style="Studio.Horizontal.TScale",
                              command=lambda n, label=value: label.configure(text=f"{float(n):+.1f}"))
            scale.pack(fill="x", pady=(0, 5))
            self.sliders.append(scale)
        self._label(column, "OUTPUT LOUDNESS", 9, True, "accent").pack(anchor="w", pady=(16, 8))
        cb = ttk.Combobox(column, textvariable=self.target, values=LOUDNESS_CHOICES, state="readonly", style="Studio.TCombobox", width=25)
        cb.pack(fill="x")
        self._label(column, "Higher loudness can reduce dynamic range. The output is measured after rendering.",
                    9, color="muted", wraplength=230, justify="left").pack(anchor="w", pady=(10, 0))
        self._label(column, "YOUR STARTUP DEFAULTS", 9, True, "accent").pack(anchor="w", pady=(20, 7))
        self.saved_defaults_label = self._label(column, mastering_defaults_description(self.startup_mastering),
                                                9, color="muted", wraplength=240, justify="left")
        self.saved_defaults_label.pack(anchor="w", pady=(0, 10))
        self._button(column, "★  SAVE CURRENT AS DEFAULT", self.save_mastering_defaults,
                     padx=10, pady=10).pack(fill="x", pady=(0, 6))
        self._button(column, "↺  RESET STARTUP DEFAULTS", self.reset_mastering_defaults,
                     padx=10, pady=8).pack(fill="x")
        self._highlight_preset()

    def _center(self, parent):
        c = self._colors()
        col = self._panel(parent)
        col.grid(row=0, column=1, sticky="nsew", padx=10)
        self._section_title(col, "02 / Listen", "Your mastering session")
        self.load_btn = self._button(col, "+  OPEN AUDIO FILE", self.open_audio, primary=True, pady=13)
        self.load_btn.pack(fill="x")
        self.track_title = self._label(col, "No track loaded", 15, True, wraplength=420, justify="left")
        self.track_title.pack(anchor="w", pady=(21, 5))
        self.track_detail = self._label(col, "Choose a WAV, FLAC, MP3, M4A or other FFmpeg-supported file.",
                                        9, color="muted", wraplength=420, justify="left")
        self.track_detail.pack(anchor="w", pady=(0, 12))
        self.wave_canvas = tk.Canvas(col, height=190, bg=c["panel2"], highlightbackground=c["line"], highlightthickness=1)
        self.wave_canvas.pack(fill="x", pady=(8, 14))
        self.wave_canvas.bind("<Configure>", lambda e: self._render_waveform())
        controls = tk.Frame(col, bg=c["panel"])
        controls.pack(fill="x", pady=(2, 10))
        self.play_button = self._button(controls, "▶  PLAY", self.toggle_play, primary=True)
        self.play_button.pack(side="left", padx=(0, 9))
        self.stop_button = self._button(controls, "■", self.stop_play, pady=10, padx=15)
        self.stop_button.pack(side="left")
        self.time_label = self._label(controls, "00:00 / 00:00", 10, True, "muted")
        self.time_label.pack(side="right")
        self.seek = ttk.Scale(col, from_=0, to=.01, command=self._seek_visual,
                               style="Studio.Horizontal.TScale")
        self.seek.pack(fill="x", pady=(2, 10))
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "_seeking", True))
        self.seek.bind("<ButtonRelease-1>", self._seek_release)
        ab = tk.Frame(col, bg=c["panel"])
        ab.pack(fill="x", pady=8)
        self._label(ab, "COMPARE", 9, True, "accent").pack(anchor="w", pady=(0, 9))
        choices = tk.Frame(ab, bg=c["panel"])
        choices.pack(anchor="w")
        for choice in ("Original", "Mastered"):
            self._radio(choices, choice, self.ab_mode, choice, lambda: self._switch_ab()).pack(side="left", padx=(0, 14))
        self._check(ab, "Level-match A/B playback", self.level_match).pack(anchor="w", pady=(13, 0))
        info = tk.Frame(col, bg=c["panel2"], padx=16, pady=15)
        info.pack(fill="x", pady=(20, 0))
        self._label(info, "MASTER ASSISTANT", 9, True, "accent", bg="panel2").pack(anchor="w", pady=(0, 8))
        self.assistant = self._label(info,
            "Import a song to analyze its loudness and tonal profile. Then choose a finishing style and create a local 24-bit master.",
            10, color="text", bg="panel2", justify="left", wraplength=450)
        self.assistant.pack(anchor="w")

    def _right(self, parent):
        c = self._colors()
        col = self._panel(parent)
        col.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self._section_title(col, "03 / Deliver", "Analysis & export")
        self._label(col, "MEASURED LOUDNESS", 9, True, "accent").pack(anchor="w")
        self.input_lufs = self._label(col, "—", 25, True)
        self.input_lufs.pack(anchor="w", pady=(6, 3))
        self._label(col, "Original · Integrated LUFS", 9, color="muted").pack(anchor="w", pady=(0, 14))
        self.output_lufs = self._label(col, "—", 25, True)
        self.output_lufs.pack(anchor="w", pady=(5, 3))
        self._label(col, "Master · Integrated LUFS", 9, color="muted").pack(anchor="w", pady=(0, 14))
        self.stereo_line = self._label(col, "Stereo: —", 10, color="muted")
        self.stereo_line.pack(anchor="w", pady=(0, 9))
        self.peak_line = self._label(col, "True peak: —", 10, color="muted")
        self.peak_line.pack(anchor="w", pady=(0, 23))
        self._label(col, "EXPORT SETTINGS", 9, True, "accent").pack(anchor="w", pady=(0, 10))
        self._label(col, "File format", 10, True).pack(anchor="w", pady=(0, 5))
        for mode in FORMATS:
            self._radio(col, f"{mode}{'  · 24-bit PCM' if mode == 'WAV' else '  · compressed audio'}", self.format, mode,
                        self._refresh_master_ui).pack(anchor="w", pady=3)
        bitrate_frame = tk.Frame(col, bg=c["panel"])
        bitrate_frame.pack(fill="x", pady=(12, 17))
        self._label(bitrate_frame, "Bitrate", 10, True).pack(side="left")
        self.bitrate_combo = ttk.Combobox(bitrate_frame, textvariable=self.bitrate,
                                          values=("128", "192", "256", "320"), width=6, state="readonly",
                                          style="Studio.TCombobox")
        self.bitrate_combo.pack(side="right")
        self._label(col, "Compressed exports are generated from the same WAV master; no remastering required.",
                    9, "", "muted", wraplength=235, justify="left").pack(anchor="w", pady=(0, 13))
        self.master_btn = self._button(col, "✦  CREATE MASTER", self.make_master, primary=True, pady=15)
        self.master_btn.pack(fill="x", pady=(5, 9))
        self.export_btn = self._button(col, "↓  EXPORT AUDIO", self.export_audio, pady=13)
        self.export_btn.pack(fill="x", pady=5)
        self.report_btn = self._button(col, "↓  SAVE PROCESSING REPORT", self.save_report, pady=11)
        self.report_btn.pack(fill="x", pady=(5, 0))
        self._label(col, "Audio remains on this computer. Your original recording is never overwritten.",
                    9, color="muted", wraplength=230, justify="left").pack(anchor="w", pady=(24, 0))

    def _themes(self, inner):
        c = self._colors()
        section = self._panel(inner, pad=23)
        section.pack(fill="x", pady=(20, 0))
        top = tk.Frame(section, bg=c["panel"])
        top.pack(fill="x")
        self._label(top, "04 / MAKE IT YOURS", 9, True, "accent").pack(anchor="w")
        self._label(top, "Theme Studio", 20, True).pack(anchor="w", pady=(4, 5))
        self._label(top, "Choose a color palette and interface aesthetic. Appearance changes never affect the audio.",
                    10, "", "muted", wraplength=880).pack(anchor="w", pady=(0, 16))
        grid = tk.Frame(section, bg=c["panel"])
        grid.pack(fill="x")
        for j in range(6):
            grid.grid_columnconfigure(j, weight=1)
        for idx, (name, palette) in enumerate(PALETTES.items()):
            selected = name == self.palette.get()
            tile = tk.Frame(grid, bg=c["panel2"] if selected else c["panel"], highlightthickness=2 if selected else 1,
                            highlightbackground=c["accent"] if selected else c["line"], padx=5, pady=8)
            tile.grid(row=0, column=idx, sticky="nsew", padx=4)
            sample = tk.Canvas(tile, height=34, bg=palette["panel"], highlightthickness=0, cursor="hand2")
            sample.pack(fill="x", padx=4, pady=(0, 7))
            sample.create_rectangle(7, 8, 42, 28, fill=palette["bg"], outline="")
            sample.create_rectangle(46, 8, 86, 28, fill=palette["accent"], outline="")
            sample.create_line(100, 20, 114, 12, 126, 26, 140, 9, fill=palette["wave"], width=3)
            sample.bind("<Button-1>", lambda e, n=name: self.select_theme(n))
            btn = tk.Button(tile, text=name, bg=tile["bg"], fg=c["text"], relief="flat", bd=0,
                            font=("Segoe UI" if os.name == "nt" else "DejaVu Sans", 9, "bold" if selected else "normal"),
                            cursor="hand2", command=lambda n=name: self.select_theme(n), wraplength=130)
            btn.pack(fill="x")
        self._label(section, "INTERFACE AESTHETIC", 9, True, "accent").pack(anchor="w", pady=(21, 11))
        styles = tk.Frame(section, bg=c["panel"])
        styles.pack(fill="x")
        for name in AESTHETICS:
            self._radio(styles, name, self.aesthetic, name, lambda n=name: self.select_aesthetic(n)).pack(side="left", padx=(0, 24))
        restore = self._button(section, "↺  Restore original look", self.reset_theme, padx=12, pady=9)
        restore.pack(anchor="w", pady=(20, 0))

    def _radio(self, parent, label: str, variable: tk.Variable, value: str, command):
        c = self._colors()
        return tk.Radiobutton(parent, text=label, variable=variable, value=value, command=command,
                              bg=c["panel"], fg=c["text"], activebackground=c["panel"],
                              activeforeground=c["accent"], selectcolor=c["panel2"],
                              highlightthickness=0, font=("Segoe UI" if os.name == "nt" else "DejaVu Sans", 10))

    def _check(self, parent, label: str, variable: tk.BooleanVar):
        c = self._colors()
        return tk.Checkbutton(parent, text=label, variable=variable, bg=c["panel"], fg=c["text"],
                              activebackground=c["panel"], activeforeground=c["accent"],
                              selectcolor=c["panel2"], highlightthickness=0,
                              font=("Segoe UI" if os.name == "nt" else "DejaVu Sans", 9))

    def select_theme(self, name: str):
        if name in PALETTES:
            self.palette.set(name)
            self._save_prefs()
            self._build()

    def select_aesthetic(self, name: str):
        if name in AESTHETICS:
            self.aesthetic.set(name)
            self._save_prefs()
            self._build()

    def reset_theme(self):
        self.palette.set("Obsidian Mint")
        self.aesthetic.set("Digital Studio")
        self._save_prefs()
        self._build()

    def _choose_preset(self, preset: str):
        self.preset.set(preset)
        if preset == "signature" and self.target.get().startswith("-12"):
            self.target.set("-11 LUFS · Signature")
        self._highlight_preset()

    def _highlight_preset(self):
        c = self._colors()
        for key, button in self.preset_buttons.items():
            sel = key == self.preset.get()
            button.configure(bg=c["accent"] if sel else c["panel2"],
                             fg=c["bg"] if sel else c["text"])

    def _active_info(self):
        if self.ab_mode.get() == "Mastered" and self.master and self.master_info:
            return self.master_info
        return self.source_info

    def _active_waveform(self) -> list[float]:
        if self.ab_mode.get() == "Mastered" and self.master and self.master_waveform:
            return self.master_waveform
        return self.original_waveform

    def _sync_waveform_view(self, *, position=None):
        """Keep the selected waveform, timeline and seek range in sync."""
        self.waveform = self._active_waveform()
        info = self._active_info()
        duration = float(info["duration"]) if info else 0.0
        if hasattr(self, "seek"):
            if position is None:
                position = self.seek.get()
            if hasattr(self.seek, "set_duration"):
                self.seek.set_duration(duration)
            else:
                self.seek.configure(to=max(0.01, duration))
            self.seek.set(min(duration, max(0.0, float(position))))
        if hasattr(self, "time_label"):
            position = float(self.seek.get()) if hasattr(self, "seek") else 0.0
            self.time_label.configure(text=f"{fmt_time(position)} / {fmt_time(duration)}")
        self._render_waveform()
        self._update_track_ui()

    def _update_track_ui(self):
        if not hasattr(self, "track_title"):
            return
        if self.source:
            self.track_title.configure(text=self.source.stem[:65])
            if self.source_info:
                i = self.source_info
                self.track_detail.configure(text=f"{fmt_time(i['duration'])}  ·  {i['sample_rate']:,} Hz  ·  {i['channels']} ch  ·  {i['codec']}")
                active = self._active_info() or i
                current = float(self.seek.get()) if hasattr(self, 'seek') else 0.0
                self.time_label.configure(text=f"{fmt_time(current)} / {fmt_time(active['duration'])}")
            else:
                self.track_detail.configure(text="Analyzing recording…")
        if self.original_meter:
            self.input_lufs.configure(text=f"{self.original_meter['input_i']:.1f} LUFS")
        if self.report:
            r = self.report
            self.output_lufs.configure(text=f"{r['output']['input_i']:.1f} LUFS")
            spectral = r.get("recipe", {}).get("sampled_profile", {})
            self.stereo_line.configure(text=f"Stereo correlation: {spectral.get('correlation', '—')}")
            self.peak_line.configure(text=f"Final true peak: {r['output']['input_tp']:+.2f} dBTP")
            if r["warnings"]:
                assistant = "Master created. " + " ".join(r["warnings"][:2])
            else:
                assistant = f"{r['preset'].capitalize()} master is ready. Measured loudness: {r['output']['input_i']:.1f} LUFS. True peak: {r['output']['input_tp']:+.2f} dBTP."
            dynamics = r.get("dynamic_analysis", {})
            if dynamics:
                scenes = dynamics.get("scene_seconds", {})
                recipe = r.get("recipe", {}).get("dynamic_sections", {})
                assistant += (f"  Dynamic mastering: {scenes.get('quiet', 0):.0f}s quiet / "
                              f"{scenes.get('dense', 0):.0f}s dense / "
                              f"{scenes.get('transient', 0):.0f}s transient-rich. "
                              f"Smooth automation up to {recipe.get('max_abs_gain_db', 0):.2f} dB.")
            self.assistant.configure(text=assistant)
        elif self.original_meter:
            self.assistant.configure(text="Track analyzed. Choose a style and create your master. Signature now responds dynamically to quiet sections, dense passages and transient-heavy moments.")

    def _render_waveform(self):
        if not hasattr(self, "wave_canvas") or not self.wave_canvas.winfo_exists():
            return
        canvas = self.wave_canvas
        canvas.delete("all")
        c = self._colors()
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 130)
        center = height / 2
        canvas.create_line(0, center, width, center, fill=c["line"], width=1)
        for x in range(0, width, 46):
            canvas.create_line(x, 0, x, height, fill=c["line"], width=1)
        if not self.waveform:
            canvas.create_text(width / 2, center, text="YOUR WAVEFORM WILL APPEAR HERE", fill=c["muted"],
                               font=("Segoe UI" if os.name == "nt" else "DejaVu Sans", 10))
            return
        values = self.waveform
        bar = width / max(1, len(values))
        for i, v in enumerate(values):
            x = i * bar + bar / 2
            amp = max(2, v * (height * .44))
            canvas.create_line(x, center - amp, x, center + amp, fill=c["wave"], width=max(1, min(3, bar * .68)))

    def _refresh_master_ui(self):
        if hasattr(self, "master_btn"):
            self.master_btn.configure(state="normal" if self.source and not self.busy and self.engine else "disabled")
            self.export_btn.configure(state="normal" if self.master and not self.busy else "disabled")
            self.report_btn.configure(state="normal" if self.report and not self.busy else "disabled")
            self.play_button.configure(state="normal" if self.source and not self.busy else "disabled")
            self.bitrate_combo.configure(state="readonly" if self.format.get() != "WAV" else "disabled")
            self.load_btn.configure(state="disabled" if self.busy else "normal")
            for slider in self.sliders:
                slider.state(["disabled"] if self.busy else ["!disabled"])

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        if hasattr(self, "progress"):
            if busy:
                self.progress.pack(side="right")
                self.progress.start(12)
            else:
                self.progress.stop()
                self.progress.pack_forget()
        self._refresh_master_ui()

    def _start_job(self, func, complete: str) -> None:
        self._set_busy(True)
        def worker():
            try:
                payload = func()
                self.messages.put((complete, payload))
            except Exception as exc:
                self.messages.put(("error", str(exc) or exc.__class__.__name__))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                event, data = self.messages.get_nowait()
                if event == "status":
                    self.status = str(data)
                    self.status_label.configure(text=self.status)
                elif event == "loaded":
                    details, meter, wave = data
                    self.source_info, self.original_meter = details, meter
                    self.original_waveform = wave
                    self.ab_mode.set("Original")
                    if hasattr(self, "_style_ab"):
                        self._style_ab()
                    self._set_busy(False)
                    self.status = "Track ready · Choose a mastering style"
                    self.status_label.configure(text=self.status)
                    self._sync_waveform_view(position=0)
                    self._update_track_ui()
                elif event == "mastered":
                    self.report, self.master, self.master_info, self.master_waveform = data
                    self.ab_mode.set("Mastered")
                    if hasattr(self, "_style_ab"):
                        self._style_ab()
                    self._set_busy(False)
                    self.status = "Master complete · Compare Original vs Mastered"
                    self.status_label.configure(text=self.status)
                    self._sync_waveform_view(position=0)
                    self._update_track_ui()
                    self._refresh_master_ui()
                elif event == "exported":
                    self._set_busy(False)
                    self.status = f"Exported: {data}"
                    self.status_label.configure(text=self.status)
                    messagebox.showinfo("Export complete", f"Saved your mastered audio:\n\n{data}")
                elif event == "error":
                    self._set_busy(False)
                    self.status = "Processing stopped · " + str(data)[:120]
                    self.status_label.configure(text=self.status)
                    messagebox.showerror("MasterForge AI", str(data)[:1500])
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self._poll_after = self.root.after(180, self._poll)

    def open_audio(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(title="Open an audio recording", filetypes=[
            ("Audio files", "*.wav *.flac *.aiff *.aif *.mp3 *.m4a *.aac *.ogg *.opus *.mp4 *.wma"),
            ("All files", "*.*")])
        if not filename:
            return
        if not self.engine:
            messagebox.showerror("FFmpeg needed", self.status)
            return
        self.stop_play()
        self.source = Path(filename)
        self.master = None
        self.report = None
        self.source_info = None
        self.master_info = None
        self.original_meter = None
        self.original_waveform = []
        self.master_waveform = []
        self.waveform = []
        self.ab_mode.set("Original")
        if hasattr(self, "_style_ab"):
            self._style_ab()
        self.play_offset = 0.0
        self._seeking = False
        if hasattr(self, "seek"):
            self.seek.set(0)
            if hasattr(self.seek, "set_duration"):
                self.seek.set_duration(0)
        self.output_lufs.configure(text="—")
        self.input_lufs.configure(text="—")
        self.stereo_line.configure(text="Stereo: —")
        self.peak_line.configure(text="True peak: —")
        self.assistant.configure(text="Analyzing your selected recording…")
        self._update_track_ui()
        self._render_waveform()
        self._refresh_master_ui()
        def work():
            info = self.engine.probe(self.source)
            self.messages.put(("status", "Measuring loudness…"))
            reading = self.engine.meter(self.source)
            self.messages.put(("status", "Drawing waveform…"))
            wave = self.engine.waveform(self.source, normalized=False)
            return info, reading, wave
        self._start_job(work, "loaded")

    def make_master(self):
        if self.busy or not self.source or not self.engine:
            return
        self.stop_play()
        target = int(self.target.get().split()[0])
        settings = Settings(preset=self.preset.get(), warmth=self.warmth.get(), clarity=self.clarity.get(),
                            intensity=self.intensity.get(), target=target)
        source = self.source
        dest = Path(self.temp.name) / "master.wav"
        self.master = None
        self.master_info = None
        self.master_waveform = []
        self.report = None
        def work():
            if dest.exists():
                dest.unlink()
            summary = self.engine.master(source, dest, settings,
                                         lambda msg: self.messages.put(("status", msg)))
            self.messages.put(("status", "Drawing mastered waveform…"))
            details = self.engine.probe(dest)
            wave = self.engine.waveform(dest, normalized=False)
            return summary, dest, details, wave
        self._start_job(work, "mastered")

    def export_audio(self):
        if self.busy or not self.master or not self.engine:
            return
        mode = self.format.get()
        preferred = f"{self.source.stem if self.source else 'song'}-masterforge-{self.preset.get()}{EXTENSIONS[mode]}"
        target = filedialog.asksaveasfilename(title="Export mastered audio", initialfile=preferred,
                                             defaultextension=EXTENSIONS[mode],
                                             filetypes=[(f"{mode} audio", "*" + EXTENSIONS[mode])])
        if not target:
            return
        path = Path(target)
        if path == self.source:
            messagebox.showerror("Invalid output", "MasterForge won't overwrite your original recording.")
            return
        if path.exists() and not messagebox.askyesno("Replace file?", f"Overwrite existing file?\n{path}"):
            return
        # Capture tkinter variables on the UI thread before starting work.
        # Reading a Tk variable in a worker thread is not portable.
        bitrate = int(self.bitrate.get())
        def work():
            self.messages.put(("status", f"Encoding {mode}…"))
            self.engine.export(self.master, path, mode.lower(), bitrate)
            return str(path)
        self._start_job(work, "exported")

    def save_report(self):
        if not self.report:
            return
        target = filedialog.asksaveasfilename(title="Save processing report", defaultextension=".json",
                                             initialfile=(self.source.stem if self.source else "master") + "-masterforge-report.json",
                                             filetypes=[("JSON reports", "*.json")])
        if target:
            Path(target).write_text(json.dumps(self.report, indent=2, ensure_ascii=False), encoding="utf-8")
            self.status = f"Saved processing report: {target}"
            self.status_label.configure(text=self.status)

    def _switch_ab(self):
        playing = bool(self.play_proc and self.play_proc.poll() is None)
        pos = (max(0., time.monotonic() - self.play_start + self.play_offset)
               if playing else (float(self.seek.get()) if hasattr(self, 'seek') else 0.0))
        if playing:
            self.stop_play()
        self._sync_waveform_view(position=pos)
        if playing:
            self._start_play(float(self.seek.get()))

    def _seek_visual(self, value):
        if not self._seeking or not self.source_info:
            return
        pos = float(value)
        self.time_label.configure(text=f"{fmt_time(pos)} / {fmt_time(self.source_info['duration'])}")

    def _seek_release(self, event):
        if not self.source_info:
            return
        pos = float(self.seek.get())
        playing = bool(self.play_proc and self.play_proc.poll() is None)
        self.stop_play()
        self.seek.set(pos)
        self._seeking = False
        self._update_playhead()
        if playing:
            self._start_play(pos)

    def stop_play(self):
        proc = self.play_proc
        self.play_proc = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.play_offset = 0
        if hasattr(self, "play_button"):
            self.play_button.configure(text="▶  PLAY")

    def toggle_play(self):
        if self.play_proc and self.play_proc.poll() is None:
            self.stop_play()
        else:
            self._start_play(float(self.seek.get()) if self.source_info else 0)

    def _start_play(self, offset: float):
        if not self.source or not self.source_info or not self.engine:
            return
        dest = self.master if self.ab_mode.get() == "Mastered" and self.master else self.source
        if not dest:
            return
        player = ffplay_binary(self.engine.ffmpeg)
        if not player:
            messagebox.showinfo("Playback setup", "Audio preview uses FFplay. Install the full FFmpeg distribution (including ffplay) to enable A/B playback. Mastering and exports still work without FFplay.")
            return
        info = self._active_info() or self.source_info
        duration = float(info["duration"])
        offset = min(max(0., offset), max(0., duration - .05))
        if hasattr(self, 'seek'):
            self.seek.set(offset)
        playback_gain = 0.
        if (self.level_match.get() and dest == self.master and self.report and self.original_meter):
            playback_gain = max(-15., min(0., float(self.original_meter["input_i"]) - float(self.report["output"]["input_i"])))
        args = [player, "-hide_banner", "-loglevel", "error", "-nodisp", "-autoexit", "-ss", str(offset)]
        if playback_gain < -0.01:
            args.extend(["-af", f"volume={playback_gain:.2f}dB"])
        args.append(str(dest))
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.play_proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL, creationflags=flags)
            self.play_start = time.monotonic()
            self.play_offset = offset
            self.play_button.configure(text="Ⅱ  PAUSE")
        except OSError as exc:
            messagebox.showerror("Playback unavailable", str(exc))

    def _update_playhead(self):
        """Move the waveform cursor without redrawing all audio bars."""
        info = self._active_info()
        if not info or not hasattr(self, "wave_canvas") or not self.wave_canvas.winfo_exists():
            return
        duration = max(0.01, float(info["duration"]))
        position = float(self.seek.get()) if hasattr(self, "seek") else 0.0
        canvas = self.wave_canvas
        width = max(200, canvas.winfo_width())
        x = 8 + (width - 16) * min(1.0, max(0.0, position / duration))
        if canvas.find_withtag("playhead"):
            canvas.coords("playhead", x, 0, x, max(10, canvas.winfo_height()-22))
        if hasattr(self, "time_label"):
            self.time_label.configure(text=f"{fmt_time(position)} / {fmt_time(duration)}")

    def _play_tick(self):
        info = self._active_info()
        if info and hasattr(self, "seek"):
            current = self.play_offset
            if self.play_proc:
                if self.play_proc.poll() is None:
                    current += time.monotonic() - self.play_start
                else:
                    self.play_proc = None
                    self.play_button.configure(text="▶  PLAY")
                    current = min(current, float(info["duration"]))
                    self.play_offset = current
            if not self._seeking and self.play_proc is not None:
                self.seek.set(min(current, float(info["duration"])))
            self._update_playhead()
        if self.root.winfo_exists():
            self._tick_after = self.root.after(250, self._play_tick)

    def _shutdown(self):
        for after_id in (getattr(self, '_poll_after', None), getattr(self, '_tick_after', None)):
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        self.stop_play()
        if self.engine:
            self.engine.cancel()
        try:
            self.temp.cleanup()
        except OSError:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        icon = Path(__file__).resolve().parent / "assets" / "icon.ico"
        if os.name == "nt" and icon.is_file():
            root.iconbitmap(str(icon))
    except Exception:
        pass
    # Visual refresh: same Python mastering engine and installation paths.
    from .polished_ui import PolishedMasterForgeWindow
    PolishedMasterForgeWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
