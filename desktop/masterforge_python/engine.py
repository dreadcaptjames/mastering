"""MasterForge AI Python Desktop — fully local FFmpeg mastering engine.

This is a new Python implementation of the v0.8.2 desktop processing recipe.
No Electron, Node.js, web server, or audio uploads are involved.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import threading
import time

VERSION = "0.10.1"
PRESETS = ("natural", "balanced", "impact", "signature")
TARGETS = (-16, -14, -12, -11, -10, -9)
BITRATES = (128, 192, 256, 320)


class MasterForgeError(Exception):
    """A recoverable mastering problem with user-facing text."""


@dataclass(frozen=True)
class Settings:
    preset: str = "balanced"
    warmth: float = 0.0
    clarity: float = 0.0
    intensity: float = 0.0
    target: int = -12

    def validate(self) -> "Settings":
        if self.preset not in PRESETS:
            raise MasterForgeError("Choose a valid mastering style.")
        if not all(math.isfinite(x) for x in (self.warmth, self.clarity, self.intensity)):
            raise MasterForgeError("Mastering controls must be finite numbers.")
        if any(abs(x) > bound for x, bound in ((self.warmth, 3), (self.clarity, 3), (self.intensity, 2))):
            raise MasterForgeError("Mastering controls are outside their permitted range.")
        if self.target not in TARGETS:
            raise MasterForgeError("Choose a supported loudness target.")
        return self


def ffmpeg_binary() -> str:
    """Prefer provided system tools; fall back to bundled imageio FFmpeg if available."""
    suffix = ".exe" if os.name == "nt" else ""
    candidates = []
    env = os.environ.get("MASTERFORGE_FFMPEG", "")
    if env:
        candidates.append(env)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates.extend([str(base / ("ffmpeg" + suffix)), str(base / "bin" / ("ffmpeg" + suffix))])
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, FileNotFoundError, OSError):
        raise MasterForgeError(
            "FFmpeg wasn't found. Install FFmpeg (CachyOS: sudo pacman -S ffmpeg), "
            "or install the optional bundled binary with: python -m pip install imageio-ffmpeg"
        ) from None


def ffprobe_binary(ffmpeg: str) -> str | None:
    suffix = ".exe" if os.name == "nt" else ""
    env = os.environ.get("MASTERFORGE_FFPROBE", "")
    names = [env, str(Path(ffmpeg).with_name("ffprobe" + suffix)), shutil.which("ffprobe")]
    return next((n for n in names if n and Path(n).is_file()), None)


def ffplay_binary(ffmpeg: str) -> str | None:
    suffix = ".exe" if os.name == "nt" else ""
    env = os.environ.get("MASTERFORGE_FFPLAY", "")
    names = [env, str(Path(ffmpeg).with_name("ffplay" + suffix)), shutil.which("ffplay")]
    return next((n for n in names if n and Path(n).is_file()), None)


class Engine:
    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None):
        self.ffmpeg = ffmpeg or ffmpeg_binary()
        self.ffprobe = ffprobe or ffprobe_binary(self.ffmpeg)
        self._running_lock = threading.Lock()
        self._running: subprocess.Popen | None = None
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()
        with self._running_lock:
            child = self._running
        if child and child.poll() is None:
            child.terminate()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def run(self, args: list[str], *, capture: bool = False, timeout: float = 900) -> subprocess.CompletedProcess:
        if self._cancel.is_set():
            raise MasterForgeError("Operation cancelled.")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with self._running_lock:
            proc = subprocess.Popen(
                [self.ffmpeg, "-nostdin", *args], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.PIPE, creationflags=flags,
            )
            self._running = proc
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise MasterForgeError("Audio processing timed out. Try a shorter file or a faster computer.") from None
        finally:
            with self._running_lock:
                if self._running is proc:
                    self._running = None
        if self._cancel.is_set():
            raise MasterForgeError("Operation cancelled.")
        if proc.returncode != 0:
            error = stderr.decode(errors="replace")[-1800:]
            raise MasterForgeError("FFmpeg could not complete the operation. " + (error.splitlines()[-1] if error else "Please check the audio file."))
        return subprocess.CompletedProcess([self.ffmpeg, *args], proc.returncode, stdout, stderr)

    def probe(self, source: Path) -> dict:
        source = Path(source)
        if not source.is_file():
            raise MasterForgeError("Choose an existing audio file.")
        if self.ffprobe:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            result = subprocess.run(
                [self.ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)],
                capture_output=True, text=True, timeout=45, creationflags=flags,
            )
            if result.returncode != 0:
                raise MasterForgeError("The selected file is not a readable audio recording.")
            data = json.loads(result.stdout)
            streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
            if not streams:
                raise MasterForgeError("This file does not contain an audio stream.")
            stream = streams[0]
            channels = int(stream.get("channels") or 0)
            if channels not in (1, 2):
                raise MasterForgeError("Only mono and stereo audio inputs are supported.")
            duration = float(data.get("format", {}).get("duration") or stream.get("duration") or 0)
            if not math.isfinite(duration) or duration < 0.05:
                raise MasterForgeError("Unable to determine the audio length.")
            return {"duration": duration, "channels": channels,
                    "sample_rate": int(stream.get("sample_rate") or 0),
                    "codec": stream.get("codec_name", "unknown"),
                    "size_bytes": source.stat().st_size}
        # FFmpeg's metadata-only probe (does not require ffprobe). Useful in a
        # standalone Windows package with imageio-ffmpeg's FFmpeg binary.
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([self.ffmpeg, "-hide_banner", "-i", str(source)],
                           capture_output=True, timeout=45, creationflags=flags)
        output = r.stderr.decode(errors="replace")
        dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        aud = re.search(r"Stream\s*#.*?Audio:\s*([^,\n]+),\s*(\d+)\s*Hz,\s*([^,\n]+)", output)
        if not dur or not aud:
            raise MasterForgeError("Unable to read audio details. Install ffprobe for more format support.")
        duration = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])
        layout = aud[3].lower()
        channels = 1 if "mono" in layout else (2 if "stereo" in layout else 0)
        if channels not in (1, 2):
            raise MasterForgeError("Only mono and stereo recordings are supported.")
        # FFmpeg's human-readable output sometimes includes codec metadata,
        # for example: "pcm_s24le ([1][0][0][0] / 0x0001)" on Windows.
        # The structured ffprobe path returns only "pcm_s24le", so normalize
        # the fallback to the same canonical codec name. Do not mistake the
        # parenthetical codec tag for part of the codec identifier.
        codec = re.match(r"[A-Za-z0-9_]+", aud[1].strip())
        if not codec:
            raise MasterForgeError("Unable to identify the audio codec; install ffprobe for more format support.")
        return {"duration": duration, "channels": channels,
                "sample_rate": int(aud[2]), "codec": codec.group(0).lower(),
                "size_bytes": source.stat().st_size}

    @staticmethod
    def loudnorm_from_log(log: str) -> dict:
        matches = re.findall(r'\{\s*"input_i"[\s\S]*?\}', log)
        if not matches:
            raise MasterForgeError("Could not measure loudness; check that FFmpeg has the loudnorm filter.")
        data = json.loads(matches[-1])
        for name in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
            try:
                value = float(data[name])
            except (TypeError, KeyError, ValueError):
                raise MasterForgeError("Loudness measurement returned an invalid value.") from None
            if not math.isfinite(value):
                # A few encoders return -inf on digital silence.
                raise MasterForgeError("This recording is silent or cannot be metered reliably.")
        return {k: float(v) if k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset") else v
                for k, v in data.items()}

    def meter(self, source: Path, filters: list[str] | None = None,
              target: float = -14, ceiling: float = -1.2, timeout: float = 900) -> dict:
        chain = (filters or []) + [f"loudnorm=I={target:.2f}:TP={ceiling:.2f}:LRA=11:print_format=json"]
        result = self.run(["-hide_banner", "-v", "info", "-i", str(source),
                           "-map", "0:a:0", "-vn", "-af", ",".join(chain),
                           "-f", "null", "-"], capture=False, timeout=timeout)
        return self.loudnorm_from_log(result.stderr.decode(errors="replace"))

    def analyze_tone(self, source: Path, channels: int = 2,
                     *, timeout: float = 900) -> dict:
        """Profile tone and stereo energy across *all* decoded audio, not an intro.

        Decode 16-kHz stereo PCM in small chunks so multi-minute tracks do not
        consume proportional amounts of RAM.  Preserve the existing five-band
        biquad calculation, allowing previously calibrated Signature settings
        to use full-song rather than opening-section statistics.
        """
        sr = 16000
        filters = []
        for hz in (70, 185, 590, 2300, 5600):
            w = 2 * math.pi * hz / sr
            alpha = math.sin(w) / (2 * .78)
            a0 = 1 + alpha
            filters.append([alpha / a0, -alpha / a0, -2 * math.cos(w) / a0,
                            (1 - alpha) / a0, 0., 0., 0., 0., 0.])
        # filter row: b0,b2,a1,a2,x1,x2,y1,y2,power
        if self._cancel.is_set():
            raise MasterForgeError("Operation cancelled.")
        args = [self.ffmpeg, "-nostdin", "-hide_banner", "-v", "error",
                "-i", str(source), "-map", "0:a:0", "-vn",
                "-ar", str(sr), "-ac", "2", "-f", "f32le", "-"]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            with self._running_lock:
                proc = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=flags)
                self._running = proc
        except OSError as exc:
            raise MasterForgeError(f"Unable to analyze recording: {exc}") from exc

        count = 0
        midsq = sidesq = l2 = r2 = cross = 0.0
        started = time.monotonic()
        carry = b""
        try:
            assert proc.stdout is not None and proc.stderr is not None
            while True:
                if self._cancel.is_set():
                    raise MasterForgeError("Operation cancelled.")
                if time.monotonic() - started > timeout:
                    raise MasterForgeError("Whole-song analysis timed out. Try a shorter recording.")
                block = proc.stdout.read(65536)
                if not block:
                    break
                block = carry + block
                usable = len(block) - len(block) % 8  # stereo float32 frames
                carry = block[usable:]
                if not usable:
                    continue
                pcm = array("f")
                pcm.frombytes(block[:usable])
                if sys.byteorder != "little":
                    pcm.byteswap()
                for i in range(0, len(pcm), 2):
                    left, right = pcm[i], pcm[i + 1]
                    if not math.isfinite(left) or not math.isfinite(right):
                        continue
                    mid, side = (left + right) / 2, (left - right) / 2
                    midsq += mid * mid
                    sidesq += side * side
                    l2 += left * left
                    r2 += right * right
                    cross += left * right
                    count += 1
                    for f in filters:
                        y = f[0] * mid + f[1] * f[5] - f[2] * f[6] - f[3] * f[7]
                        f[5], f[4] = f[4], mid
                        f[7], f[6] = f[6], y
                        f[8] += y * y
            error = proc.stderr.read().decode(errors="replace")
            if proc.wait(timeout=30) != 0:
                raise MasterForgeError("Could not analyze the full song. " +
                                       (error.splitlines()[-1] if error else "Check the audio file."))
            if carry:
                raise MasterForgeError("Audio decoder returned an incomplete frame during analysis.")
            if count < 1000:
                raise MasterForgeError("Not enough decoded audio for tonal analysis.")
            def db(x: float) -> float:
                return 20 * math.log10(max(x, 1e-12))
            ref = math.sqrt(midsq / count) or 1e-12
            return {
                "bands": [round(db(math.sqrt(f[8] / count) / ref), 2) for f in filters],
                "correlation": 1. if channels == 1 else round(cross / max(math.sqrt(l2 * r2), 1e-12), 3),
                "side_mid_db": -100. if channels == 1 else round(db(math.sqrt(sidesq / max(midsq, 1e-12))), 2),
                "seconds_analyzed": round(count / sr, 2),
                "analysis_coverage": "entire_recording",
                "analysis_method": "streamed_full_track_biquad",
            }
        except subprocess.TimeoutExpired as exc:
            raise MasterForgeError("Whole-song analysis timed out. Try a shorter recording.") from exc
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            with self._running_lock:
                if self._running is proc:
                    self._running = None

    @staticmethod
    def _percentile(numbers: list[float], fraction: float) -> float:
        if not numbers:
            return -80.0
        ordered = sorted(numbers)
        rank = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
        i = int(rank)
        return ordered[i] * (1 - (rank - i)) + ordered[min(i + 1, len(ordered) - 1)] * (rank - i)

    def analyze_sections(self, source: Path, *, preset: str = "signature", timeout: float = 900,
                         section_seconds: float = 2.0) -> dict:
        """Stream the *whole song* and measure short-term energy and crest factor.

        The scene classifier uses each section relative to the recording's own
        percentiles: it does not assume verses or choruses occur at particular
        timestamps. Peaks are measured on downsampled monitoring audio, and are
        used ONLY for deciding gentle gain automation, never limiting or metering.
        """
        source = Path(source)
        if preset not in PRESETS:
            raise MasterForgeError("Invalid mastering style for dynamic analysis.")
        sr = 8000
        samples_per_section = round(sr * section_seconds)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        args = [self.ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-i", str(source),
                "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
        if self._cancel.is_set():
            raise MasterForgeError("Operation cancelled.")
        with self._running_lock:
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, creationflags=flags)
            self._running = proc
        sections = []
        seconds = 0.0
        n = 0
        power = peak = 0.0
        started = time.monotonic()
        try:
            assert proc.stdout is not None and proc.stderr is not None
            carry = b""
            while True:
                if self._cancel.is_set():
                    raise MasterForgeError("Operation cancelled.")
                if time.monotonic() - started > timeout:
                    raise MasterForgeError("Dynamic section analysis timed out.")
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                chunk = carry + chunk
                usable = len(chunk) - (len(chunk) % 4)
                carry = chunk[usable:]
                pcm = array("f")
                pcm.frombytes(chunk[:usable])
                if sys.byteorder != "little":
                    pcm.byteswap()
                for sample in pcm:
                    if not math.isfinite(sample):
                        sample = 0.0
                    n += 1
                    power += sample * sample
                    peak = max(peak, abs(sample))
                    if n == samples_per_section:
                        rms = math.sqrt(power / n)
                        crest = 20 * math.log10(max(peak, 1e-9) / max(rms, 1e-9))
                        sections.append({"start_seconds": round(seconds, 3),
                                         "end_seconds": round(seconds + n / sr, 3),
                                         "rms_dbfs": round(20 * math.log10(max(rms, 1e-9)), 3),
                                         "crest_db": round(crest, 2)})
                        seconds += n / sr
                        n = 0
                        power = peak = 0.0
            if n:
                rms = math.sqrt(power / n)
                crest = 20 * math.log10(max(peak, 1e-9) / max(rms, 1e-9))
                sections.append({"start_seconds": round(seconds, 3),
                                 "end_seconds": round(seconds + n / sr, 3),
                                 "rms_dbfs": round(20 * math.log10(max(rms, 1e-9)), 3),
                                 "crest_db": round(crest, 2)})
                seconds += n / sr
            error = proc.stderr.read().decode(errors="replace")
            if proc.wait(timeout=30) != 0:
                raise MasterForgeError("Unable to analyze song sections. " +
                                       (error.splitlines()[-1] if error else "Check the recording."))
            if len(sections) == 0 or seconds < 0.1:
                raise MasterForgeError("Not enough audio for dynamic mastering analysis.")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            with self._running_lock:
                if self._running is proc:
                    self._running = None

        active = [x["rms_dbfs"] for x in sections if x["rms_dbfs"] > -65]
        if not active:
            raise MasterForgeError("Song is silent or too quiet for dynamic section analysis.")
        p25 = self._percentile(active, .25)
        median = self._percentile(active, .5)
        p75 = self._percentile(active, .75)
        crest_med = self._percentile([x["crest_db"] for x in sections if x["rms_dbfs"] > -65], .5)
        spread = p75 - p25
        strength = {"natural": .16, "balanced": .47, "impact": .66, "signature": .78}[preset]
        scene_seconds = {"quiet": 0.0, "steady": 0.0, "dense": 0.0, "transient": 0.0, "silence": 0.0}
        for segment in sections:
            rms = segment["rms_dbfs"]
            transient = segment["crest_db"] >= max(10., crest_med + 3.0)
            if rms <= -65:
                scene = "silence"
            elif transient:
                scene = "transient"
            elif spread < 2.0:
                scene = "steady"
            elif rms <= p25:
                scene = "quiet"
            elif rms >= p75:
                scene = "dense"
            else:
                scene = "steady"
            # dB offsets remain deliberately subtle. Loudness normalization
            # happens *after* this automation and retains the overall target.
            if scene == "quiet":
                gain = strength * min(.85, .24 + max(0, median - rms) * .075)
            elif scene == "dense":
                gain = -strength * min(.82, .22 + max(0, rms - median) * .08)
            elif scene == "transient":
                # Do not clamp sharp attacks just because the section is loud.
                gain = 0.0 if rms >= median else strength * .10
            else:
                gain = 0.0
            segment["scene"] = scene
            segment["gain_db"] = round(gain, 3)
            scene_seconds[scene] += segment["end_seconds"] - segment["start_seconds"]
        return {"analysis_coverage": "entire_recording", "seconds_analyzed": round(seconds, 3),
                "window_seconds": section_seconds, "p25_dbfs": round(p25, 2),
                "median_dbfs": round(median, 2), "p75_dbfs": round(p75, 2),
                "scene_seconds": {k: round(v, 2) for k, v in scene_seconds.items()},
                "max_abs_gain_db": round(max(abs(x["gain_db"]) for x in sections), 3),
                "sections": sections}

    @staticmethod
    def write_gain_envelope(path: Path, analysis: dict, *, sample_rate: int = 200) -> None:
        """Build a smooth PCM control signal; 0.5 represents unity after x2.

        Section centers are joined with cubic smoothsteps, so adjacent scene
        transitions cannot create a sudden gain jump or boundary click. This
        control WAV is used by FFmpeg's `amultiply` filter on the actual audio.
        """
        sections = analysis["sections"]
        if not sections:
            raise MasterForgeError("No song sections available for automation.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        centers = [(x["start_seconds"] + x["end_seconds"]) / 2 for x in sections]
        gains = [x["gain_db"] for x in sections]
        frames = int(math.ceil((analysis["seconds_analyzed"] + 2.0) * sample_rate))
        with wave.open(str(path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(sample_rate)
            cursor = 0
            pending = bytearray()
            for i in range(frames):
                t = i / sample_rate
                while cursor + 1 < len(centers) and t > centers[cursor + 1]:
                    cursor += 1
                if cursor + 1 >= len(centers):
                    gain = gains[-1]
                elif t < centers[0]:
                    gain = gains[0]
                else:
                    blend = max(0.0, min(1.0, (t - centers[cursor]) /
                                                (centers[cursor + 1] - centers[cursor])))
                    blend = blend * blend * (3 - 2 * blend)
                    gain = gains[cursor] * (1 - blend) + gains[cursor + 1] * blend
                amplitude = 0.5 * (10.0 ** (gain / 20.0))
                pending.extend(struct.pack("<h", round(max(0.0, min(.999, amplitude)) * 32767)))
                if len(pending) >= 8192:
                    out.writeframesraw(pending)
                    pending.clear()
            if pending:
                out.writeframesraw(pending)

    @staticmethod
    def dynamic_graph(filters: list[str], final_filter: str) -> str:
        """Make the pre-measure and render chains bit-for-bit structurally identical."""
        chain = ",".join([*filters, "aresample=48000"])
        return (f"[0:a:0]{chain}[tonal];"
                "[1:a:0]aresample=48000,pan=stereo|c0=c0|c1=c0,volume=2[control];"
                f"[tonal][control]amultiply,{final_filter}[out]")

    def meter_dynamic(self, source: Path, control: Path, filters: list[str],
                      target: float, ceiling: float, timeout: float = 900) -> dict:
        norm = f"loudnorm=I={target:.2f}:TP={ceiling:.2f}:LRA=11:print_format=json"
        graph = self.dynamic_graph(filters, norm)
        result = self.run(["-hide_banner", "-v", "info", "-i", str(source), "-i", str(control),
                           "-filter_complex", graph, "-map", "[out]", "-f", "null", "-"],
                          timeout=timeout)
        return self.loudnorm_from_log(result.stderr.decode(errors="replace"))

    def supports_filter(self, name: str) -> bool:
        if not hasattr(self, "_filters_available"):
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            result = subprocess.run([self.ffmpeg, "-hide_banner", "-filters"],
                                    capture_output=True, text=True, timeout=30, creationflags=flags)
            self._filters_available = result.stdout if result.returncode == 0 else ""
        return bool(re.search(rf"\b{re.escape(name)}\b", self._filters_available))

    def waveform(self, source: Path, points: int = 360, *, normalized: bool = True) -> list[float]:
        """Summarize the *entire* recording into time-aligned waveform peaks.

        Stream decoded stereo PCM instead of decoding to a 150 Hz audio stream.
        Resampling to 150 Hz discarded almost all musical frequencies and could
        make large sections of a song appear blank. Streaming keeps memory flat
        even for very long recordings. Both channels contribute to each peak.
        """
        points = int(points)
        if points < 1 or points > 8192:
            raise MasterForgeError("Waveform resolution must be between 1 and 8192 points.")
        source = Path(source)
        duration = float(self.probe(source)["duration"])
        preview_rate = 16000  # Broad-band visual overview; not the mastering signal.
        expected_frames = max(1, round(duration * preview_rate))
        peaks = [0.0] * points
        frame_index = 0
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        if self._cancel.is_set():
            raise MasterForgeError("Operation cancelled.")
        args = [self.ffmpeg, "-nostdin", "-hide_banner", "-v", "error",
                "-i", str(source), "-map", "0:a:0", "-vn",
                "-ac", "2", "-ar", str(preview_rate), "-f", "f32le", "-"]
        try:
            with self._running_lock:
                proc = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=flags)
                self._running = proc
            try:
                assert proc.stdout is not None and proc.stderr is not None
                remainder = b""
                while True:
                    if self._cancel.is_set():
                        proc.terminate()
                        raise MasterForgeError("Operation cancelled.")
                    block = proc.stdout.read(65536)
                    if not block:
                        break
                    block = remainder + block
                    usable = len(block) - len(block) % 8  # stereo f32 frames
                    remainder = block[usable:]
                    samples = array("f")
                    samples.frombytes(block[:usable])
                    if sys.byteorder != "little":
                        samples.byteswap()
                    for i in range(0, len(samples), 2):
                        bucket = min(points - 1, frame_index * points // expected_frames)
                        value = max(abs(samples[i]), abs(samples[i + 1]))
                        if math.isfinite(value) and value > peaks[bucket]:
                            peaks[bucket] = value
                        frame_index += 1
                error = proc.stderr.read().decode(errors="replace")
                if proc.wait(timeout=30) != 0:
                    raise MasterForgeError("Could not draw the waveform. " +
                                           (error.splitlines()[-1] if error else "Check the audio file."))
                if frame_index == 0:
                    raise MasterForgeError("No audio samples could be decoded for the waveform.")
                # Original/mastered comparison requires absolute (sample-peak)
                # amplitudes so both waveforms share the same gain reference.
                # Keep legacy independent normalization for callers asking for it.
                if not normalized:
                    return peaks
                ordered = sorted(peaks)
                percentile = ordered[min(len(ordered) - 1, int(len(ordered) * .98))]
                scale = max(percentile, max(peaks) * .45, .0001)
                return [min(1.0, value / scale) for value in peaks]
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()
                with self._running_lock:
                    if self._running is proc:
                        self._running = None
        except OSError as exc:
            raise MasterForgeError(f"Unable to create waveform preview: {exc}") from exc

    @staticmethod
    def recipe(settings: Settings, metrics: dict, spectral: dict, channels: int) -> tuple[list[str], dict]:
        reference = settings.preset == "signature"
        bases = {"natural": [.1, .1, -.1, 0], "balanced": [.4, .5, -.4, 0],
                 "impact": [.8, .8, -.8, 0], "signature": [1.95, 2.0, -3.1, .9]}
        bass, presence, lowmid, air = bases[settings.preset]
        if reference:
            b = spectral["bands"]
            bass_vs_mid = b[1] - b[2]
            hi_vs_pres = b[4] - b[3]
            bass = clamp(2.0 - .27 * (bass_vs_mid - (-1.0)), .35, 2.7)
            lowmid = clamp(-3.15 - .23 * (b[2] - (-5.5)), -4.2, -1.4)
            presence = clamp(2.0 - .24 * (hi_vs_pres - (-7.5)), .3, 2.9)
            air = clamp(.85 - .16 * (hi_vs_pres - (-7.5)), 0, 1.3)
        bass = clamp(bass + settings.warmth * .55, -2.4, 2.7)
        presence = clamp(presence + settings.clarity * .4, -2.2, 2.9)
        air = clamp(air + settings.clarity * .18, -1, 1.4)
        chain = ["highpass=f=26", f"bass=f=115:g={bass:.3f}",
                 f"equalizer=f=560:width_type=q:width=0.75:g={lowmid:.3f}",
                 f"equalizer=f=4400:width_type=q:width=0.7:g={presence:.3f}",
                 f"treble=f=8500:g={air:.3f}"]
        width = 1.
        if (reference and channels == 2 and .32 < spectral["correlation"] < .985
                and spectral["side_mid_db"] > -24):
            width = clamp(1.22 - (.60 - spectral["correlation"]) * .14, 1.11, 1.25)
            chain.append(f"extrastereo=m={width:.3f}:c=0")
        compress = (settings.preset != "natural"
                    and float(metrics["input_i"]) < (-17 if reference else -12)
                    and float(metrics["input_lra"]) >= (8 if reference else 5.5))
        if compress and not reference:
            ratio = 1.17 if reference else clamp(
                (1.3 if settings.preset == "balanced" else 1.58) + settings.intensity * .12, 1.1, 1.9)
            chain.append(f"acompressor=threshold=0.18:ratio={ratio:.3f}:attack={45 if reference else 33}:release={280 if reference else 210}:knee=5")
        # Dynamics are time-varying. FFmpeg's RMS detector follows the audio,
        # with slower attack preserving short transients; parallel mix reduces
        # excessive gain reduction on dense choruses. The full-song gain curve
        # below provides a second, independently section-aware control layer.
        if reference:
            chain.append("acompressor=threshold=0.145:ratio=1.25:attack=55:release=280:knee=5:mix=0.65:detection=rms")
        # The dynamic frequency filters are optional for builds with older
        # FFmpeg (the gain curve and compressor remain fully dynamic).
        # Applied later by `master` based on detected FFmpeg filter support.
        return chain, {"bass_db": round(bass, 3), "presence_db": round(presence, 3),
                       "air_db": round(air, 3), "low_mid_db": round(lowmid, 3),
                       "stereo_width_multiplier": round(width, 3),
                       "compressor_used": bool(reference or compress), "compressor_behavior": "continuous_parallel_rms" if reference else ("conditional" if compress else "off"), "sampled_profile": spectral,
                       "tonal_analysis_scope": "full_song",
                       "description": ("Adaptive Signature EQ and guarded widening" if reference else "Conservative finishing EQ")}

    def master(self, source: Path, result_wav: Path, settings: Settings,
               status: Callable[[str], None] | None = None) -> dict:
        settings.validate()
        source, result_wav = Path(source).resolve(), Path(result_wav).resolve()
        if source == result_wav:
            raise MasterForgeError("Never overwrite the original recording.")
        self.reset_cancel()
        announce = status or (lambda _: None)
        announce("Reading audio information…")
        info = self.probe(source)
        if info["duration"] > 6 * 60 * 60:
            raise MasterForgeError("This version supports up to six hours per recording.")
        goal = clamp(settings.target + (-1 if settings.preset == "natural" else 0)
                     + settings.intensity * (.2 if settings.preset == "signature" else .4), -18, -9)
        ceiling = -1.1 if settings.preset == "signature" else (-1.2 if goal <= -14 else -1.5)
        long_timeout = max(240, min(60 * 60 * 8, info["duration"] * 12 + 60))
        announce("Measuring original loudness…")
        original = self.meter(source, target=goal, ceiling=ceiling, timeout=long_timeout)
        announce("Analyzing tone and stereo across the entire song…")
        spectrum = self.analyze_tone(source, info["channels"], timeout=long_timeout)
        filters, recipe = self.recipe(settings, original, spectrum, info["channels"])
        announce("Mapping quiet passages, dense sections and transient peaks…")
        sections = self.analyze_sections(source, preset=settings.preset, timeout=long_timeout)
        # Frequency-dependent compression acts *during* playback, rather than
        # applying the same EQ cut to every verse, chorus and snare hit.
        if settings.preset == "signature" and self.supports_filter("adynamicequalizer"):
            filters.extend([
                "adynamicequalizer=mode=cutabove:auto=adaptive:dfrequency=560:dqfactor=1.0:tfrequency=560:tqfactor=1.1:ratio=1.18:range=1.6:attack=42:release=235",
                "adynamicequalizer=mode=cutabove:auto=adaptive:dfrequency=6200:dqfactor=1.0:tfrequency=6200:tqfactor=1.4:ratio=1.12:range=1.4:attack=9:release=125",
            ])
            recipe["dynamic_eq"] = "Adaptive 560 Hz low-mid and 6.2 kHz harshness control"
        else:
            recipe["dynamic_eq"] = "Unavailable on this FFmpeg; section gain and program compressor active"
        recipe["dynamic_sections"] = {
            "scene_seconds": sections["scene_seconds"], "window_seconds": sections["window_seconds"],
            "max_abs_gain_db": sections["max_abs_gain_db"],
            "seconds_analyzed": sections["seconds_analyzed"],
        }
        announce("Creating smooth automation for changing song sections…")
        result_wav.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="masterforge-dynamic-") as temp:
            envelope = Path(temp) / "scene-envelope.wav"
            self.write_gain_envelope(envelope, sections)
            announce("Measuring the time-varying processing chain…")
            pre = self.meter_dynamic(source, envelope, filters, goal, ceiling, timeout=long_timeout)
            norm = (f"loudnorm=I={goal:.2f}:TP={ceiling:.2f}:LRA=11:"
                    f"measured_I={pre['input_i']}:measured_TP={pre['input_tp']}:"
                    f"measured_LRA={pre['input_lra']}:measured_thresh={pre['input_thresh']}:"
                    f"offset={pre['target_offset']}:linear=true:print_format=json")
            graph = self.dynamic_graph(filters, norm)
            announce("Rendering the dynamic 24-bit studio master…")
            try:
                self.run(["-hide_banner", "-y", "-v", "warning", "-i", str(source),
                          "-i", str(envelope), "-filter_complex", graph, "-map", "[out]",
                          "-ac", "2", "-ar", "48000", "-c:a", "pcm_s24le", str(result_wav)],
                         timeout=long_timeout)
                announce("Verifying final loudness, true peaks and duration…")
                final = self.meter(result_wav, target=goal, ceiling=ceiling, timeout=long_timeout)
                rendered_duration = self.probe(result_wav)["duration"]
                if abs(rendered_duration - info["duration"]) > .2:
                    raise MasterForgeError("The dynamic master has an incorrect duration; the export was discarded.")
            except Exception:
                result_wav.unlink(missing_ok=True)
                raise
        warnings = []
        if final["input_tp"] > ceiling + .25:
            warnings.append("Measured true peak exceeded the intended ceiling; verify before release.")
        if final["input_i"] < goal - 1.5:
            warnings.append("The requested loudness could not be reached without exceeding constraints.")
        if goal >= -10:
            warnings.append("Aggressive loudness may reduce dynamics. Listen critically.")
        if original["input_lra"] <= 2:
            warnings.append("The source has limited dynamics; mastering cannot recover missing detail.")
        return {"application": "MasterForge AI Python Desktop", "version": VERSION,
                "preset": settings.preset, "target_lufs": round(goal, 2),
                "intended_ceiling_dbtp": ceiling, "source": str(source),
                "source_details": info, "input": original, "pre_master": pre,
                "dynamic_analysis": sections,
                "output": final, "recipe": recipe, "warnings": warnings,
                "meter_note": "Measured LUFS/true-peak from FFmpeg's loudnorm filter. Independent verification recommended."}

    def export(self, master_wav: Path, output: Path, fmt: str, bitrate: int = 256) -> None:
        fmt = fmt.lower()
        if fmt not in ("wav", "mp3", "m4a"):
            raise MasterForgeError("Select WAV, MP3 or M4A.")
        if fmt != "wav" and bitrate not in BITRATES:
            raise MasterForgeError("Bitrate must be 128, 192, 256 or 320 kbps.")
        master_wav, output = Path(master_wav).resolve(), Path(output).resolve()
        if not master_wav.is_file():
            raise MasterForgeError("Create a master before exporting.")
        if master_wav == output:
            raise MasterForgeError("Choose a different output path.")
        output.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "wav":
            shutil.copyfile(master_wav, output)
        else:
            cmd = ["-hide_banner", "-y", "-v", "error", "-i", str(master_wav),
                   "-map", "0:a:0", "-vn", "-map_metadata", "-1", "-ac", "2",
                   "-c:a", "libmp3lame" if fmt == "mp3" else "aac",
                   "-b:a", f"{bitrate}k"]
            if fmt == "m4a":
                cmd += ["-movflags", "+faststart"]
            cmd.append(str(output))
            try:
                self.run(cmd, timeout=1800)
            except Exception:
                output.unlink(missing_ok=True)
                raise
        if not output.is_file() or output.stat().st_size < 200:
            raise MasterForgeError("Export failed: no valid audio was written.")


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
