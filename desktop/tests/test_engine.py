"""Local integration tests; all audio remains in temporary folders."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

from masterforge_python.engine import Engine, Settings, MasterForgeError, VERSION


class MasterForgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="masterforge-test-")
        cls.path = Path(cls.temp.name)
        cls.engine = Engine()
        cls.source = cls.path / "test-source.wav"
        command = [cls.engine.ffmpeg, "-hide_banner", "-nostdin", "-y", "-v", "error",
                   "-f", "lavfi", "-i", "sine=frequency=180:duration=7:sample_rate=48000",
                   "-f", "lavfi", "-i", "sine=frequency=2100:duration=7:sample_rate=48000",
                   "-filter_complex", "[0:a][1:a]amix=inputs=2:weights=1 0.55,volume=0.50,pan=stereo|c0=c0|c1=0.82*c0[a]",
                   "-map", "[a]", "-c:a", "pcm_s16le", str(cls.source)]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_01_input_probe_and_invalid_settings(self):
        info = self.engine.probe(self.source)
        self.assertEqual(info["channels"], 2)
        self.assertGreater(info["duration"], 6)
        for bad in [Settings(preset="unknown"), Settings(target=0), Settings(warmth=100)]:
            with self.assertRaises(MasterForgeError):
                bad.validate()

    def test_02_waveform_and_analysis(self):
        waveform = self.engine.waveform(self.source)
        self.assertGreater(len(waveform), 100)
        self.assertTrue(all(0 <= x <= 1 for x in waveform))
        tone = self.engine.analyze_tone(self.source)
        self.assertEqual(len(tone["bands"]), 5)
        self.assertGreater(tone["correlation"], 0)

    def test_02b_long_waveform_includes_final_minute(self):
        # A 130-second song: a tone in the first 5 seconds, silence for
        # 120 seconds, and another tone in the last 5 seconds. Its final
        # activity must be visible at the far right of the full-track view.
        long_source = self.path / "long-waveform-test.flac"
        subprocess.run([
            self.engine.ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=1400:sample_rate=16000:duration=5",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono:d=120",
            "-f", "lavfi", "-i", "sine=frequency=1400:sample_rate=16000:duration=5",
            "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]",
            "-map", "[a]", "-c:a", "flac", str(long_source)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.assertGreater(self.engine.probe(long_source)["duration"], 120)
        peaks = self.engine.waveform(long_source, points=360)
        self.assertEqual(len(peaks), 360)
        self.assertGreater(max(peaks[:18]), .4, "Opening audio should be visible")
        self.assertLess(max(peaks[40:310]), .01, "Long silent section should remain silent")
        self.assertGreater(max(peaks[-18:]), .4, "Final audio should be visible at right edge")

    def test_02d_tone_analysis_uses_audio_after_first_minute(self):
        """Changing the outro while leaving the intro identical must affect Signature."""
        low_only = self.path / "full-track-low-only.flac"
        changing = self.path / "full-track-with-bright-outro.flac"
        # Two tracks both start with the same 42 seconds of 180 Hz audio.
        # The final 38 seconds contain very different spectral content.
        for outfile, final_hz in ((low_only, 180), (changing, 5300)):
            subprocess.run([
                self.engine.ffmpeg, "-hide_banner", "-nostdin", "-y", "-v", "error",
                "-f", "lavfi", "-i", "sine=frequency=180:duration=42:sample_rate=16000",
                "-f", "lavfi", "-i", f"sine=frequency={final_hz}:duration=38:sample_rate=16000",
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1,pan=stereo|c0=c0|c1=0.8*c0[a]",
                "-map", "[a]", "-c:a", "flac", str(outfile),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        low = self.engine.analyze_tone(low_only, 2)
        bright = self.engine.analyze_tone(changing, 2)
        self.assertEqual(low["analysis_coverage"], "entire_recording")
        self.assertEqual(bright["analysis_coverage"], "entire_recording")
        self.assertGreater(low["seconds_analyzed"], 79.9)
        self.assertGreater(bright["seconds_analyzed"], 79.9)
        self.assertGreater(bright["bands"][4], low["bands"][4] + 10,
                           "An outro with strong high frequencies must influence whole-song tone")
        original_metrics = {"input_i": -15., "input_lra": 4.}
        _, low_recipe = self.engine.recipe(Settings(preset="signature", target=-11),
                                           original_metrics, low, 2)
        _, bright_recipe = self.engine.recipe(Settings(preset="signature", target=-11),
                                              original_metrics, bright, 2)
        self.assertNotEqual(low_recipe["presence_db"], bright_recipe["presence_db"],
                            "Changing only the second half must change Signature's EQ decisions")

    def test_02c_raw_waveforms_preserve_actual_gain_difference(self):
        """The new A/B comparison must not independently normalize each file."""
        boosted = self.path / "boosted-waveform.wav"
        subprocess.run([
            self.engine.ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-y",
            "-i", str(self.source), "-af", "volume=2", str(boosted)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        original = self.engine.waveform(self.source, normalized=False)
        louder = self.engine.waveform(boosted, normalized=False)
        self.assertEqual(len(original), len(louder))
        self.assertGreater(max(louder), max(original) * 1.8)
        self.assertGreater(sum(louder), sum(original) * 1.8)

    def test_03_signature_render_and_reports(self):
        self.out = self.path / "signature.wav"
        report = self.engine.master(self.source, self.out, Settings(preset="signature", target=-11))
        self.assertTrue(self.out.is_file())
        probe = self.engine.probe(self.out)
        self.assertEqual(probe["sample_rate"], 48000)
        self.assertEqual(probe["channels"], 2)
        self.assertIn("output", report)
        self.assertIn("recipe", report)
        self.assertEqual(report["preset"], "signature")
        profile = report["recipe"]["sampled_profile"]
        self.assertEqual(profile["analysis_coverage"], "entire_recording")
        self.assertAlmostEqual(profile["seconds_analyzed"], self.engine.probe(self.source)["duration"], delta=.05)
        self.assertLess(report["output"]["input_tp"], .5)
        self.assertGreater(report["output"]["input_i"], report["input"]["input_i"])

    def test_03b_dynamic_sections_and_gain_envelope(self):
        """Quiet verses, dense choruses and sharp transients are not one preset."""
        import wave
        import struct
        import math
        sample_rate = 12000
        # Deliberately different passages and brief prominent attacks.
        source = self.path / "dynamic-scene-input.wav"
        with wave.open(str(source), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            for second in range(18):
                a = .04 if second < 6 else (.45 if second < 12 else .14)
                raw = bytearray()
                for i in range(sample_rate):
                    t = second + i / sample_rate
                    sample = a * math.sin(2 * math.pi * 220 * t)
                    if second >= 12 and i < 30:
                        sample = .88 * (1 - i / 30)
                    raw.extend(struct.pack('<h', round(max(-1, min(1, sample)) * 30000)))
                output.writeframes(raw)
        a = self.engine.analyze_sections(source, preset='signature')
        self.assertGreaterEqual(a['seconds_analyzed'], 17.99)
        self.assertGreater(a['scene_seconds']['quiet'], 3.9)
        self.assertGreater(a['scene_seconds']['dense'], 3.9)
        self.assertGreater(a['scene_seconds']['transient'], 0.0)
        quiet = [s['gain_db'] for s in a['sections'] if s['scene'] == 'quiet']
        dense = [s['gain_db'] for s in a['sections'] if s['scene'] == 'dense']
        self.assertGreater(max(quiet), 0.10)
        self.assertLess(min(dense), -0.10)
        envelope = self.path / 'scene-automation.wav'
        self.engine.write_gain_envelope(envelope, a)
        with wave.open(str(envelope), 'rb') as control:
            self.assertEqual(control.getframerate(), 200)
            signal = control.readframes(control.getnframes())
            samples = struct.unpack('<' + 'h' * (len(signal)//2), signal)
            self.assertGreater(max(samples)-min(samples), 200)
            # Smoothstep between segments: adjacent control samples should not
            # jump abruptly and introduce audible scene boundary clicks.
            self.assertLess(max(abs(x-y) for x,y in zip(samples,samples[1:])), 50)

    def test_03c_dynamic_master_keeps_track_length_and_reports_sections(self):
        source = self.path / 'dynamic-scene-input.wav'
        if not source.is_file():
            self.test_03b_dynamic_sections_and_gain_envelope()
        output = self.path / 'scene-signature-master.wav'
        report = self.engine.master(source, output, Settings(preset='signature', target=-11))
        self.assertTrue(output.is_file())
        self.assertAlmostEqual(self.engine.probe(source)['duration'], self.engine.probe(output)['duration'], delta=.05)
        scenes = report['dynamic_analysis']
        self.assertEqual(scenes['analysis_coverage'], 'entire_recording')
        self.assertGreater(scenes['scene_seconds']['quiet'], 0)
        self.assertGreater(scenes['scene_seconds']['dense'], 0)
        self.assertGreater(len(scenes['sections']), 5)
        self.assertTrue(report['recipe']['compressor_used'])
        self.assertLess(report['output']['input_tp'], .5)
        self.assertGreater(report['output']['input_i'], report['input']['input_i'])

    def test_03d_dynamic_gain_changes_actual_audio_by_section(self):
        """Automation must alter the rendered PCM, not just JSON report metadata."""
        import math
        import wave
        source = self.path / 'dynamic-scene-input.wav'
        if not source.is_file():
            self.test_03b_dynamic_sections_and_gain_envelope()
        analysis = self.engine.analyze_sections(source, preset='signature')
        control = self.path / 'real-section-control.wav'
        flat_control = self.path / 'flat-section-control.wav'
        self.engine.write_gain_envelope(control, analysis)
        flat = {**analysis, 'sections': [{**s, 'gain_db': 0.0} for s in analysis['sections']]}
        self.engine.write_gain_envelope(flat_control, flat)
        renders = []
        for label, ctr in [('adaptive', control), ('flat', flat_control)]:
            dest = self.path / f'{label}-gain.wav'
            graph = self.engine.dynamic_graph([], 'anull')
            self.engine.run(['-v','error','-y','-i',str(source),'-i',str(ctr),
                             '-filter_complex',graph,'-map','[out]',
                             '-ac','2','-ar','48000','-c:a','pcm_s16le',str(dest)])
            renders.append(dest)
        def rms_at(path, start, end):
            with wave.open(str(path), 'rb') as wav:
                sr = wav.getframerate()
                channels = wav.getnchannels()
                wav.setpos(round(start*sr))
                raw=wav.readframes(round((end-start)*sr))
            from array import array
            vals = array('h'); vals.frombytes(raw)
            return math.sqrt(sum(v*v for v in vals)/len(vals))
        adaptive, flat = renders
        quiet_shift = 20*math.log10(rms_at(adaptive,2.5,3.5)/rms_at(flat,2.5,3.5))
        dense_shift = 20*math.log10(rms_at(adaptive,8.5,9.5)/rms_at(flat,8.5,9.5))
        self.assertGreater(quiet_shift,.10)
        self.assertLess(dense_shift,-.10)
        self.assertGreater(quiet_shift-dense_shift,.25)

    def test_04_wav_mp3_m4a_exports(self):
        master = self.path / "signature.wav"
        if not master.exists():
            self.engine.master(self.source, master, Settings(preset="signature", target=-11))
        for fmt in ("wav", "mp3", "m4a"):
            exported = self.path / f"result.{fmt}"
            self.engine.export(master, exported, fmt, 256)
            p = self.engine.probe(exported)
            self.assertGreater(p["duration"], 6)
            self.assertEqual(p["channels"], 2)
            if fmt == "mp3": self.assertEqual(p["codec"], "mp3")
            if fmt == "m4a": self.assertEqual(p["codec"], "aac")
            if fmt == "wav": self.assertEqual(p["codec"], "pcm_s24le")

    def test_05_probe_without_ffprobe_windows_style_codec_tags(self):
        # The packaged Windows app can have FFmpeg without ffprobe. FFmpeg's
        # metadata output may include "([1][0][0][0] / 0x0001)" after pcm_s24le.
        # Its codec field must match the canonical ffprobe name exactly.
        fallback = Engine(ffmpeg=self.engine.ffmpeg)
        fallback.ffprobe = None
        master = self.path / "signature.wav"
        if not master.exists():
            self.engine.master(self.source, master, Settings(preset="signature", target=-11))
        for fmt, expected in (("wav", "pcm_s24le"), ("mp3", "mp3"), ("m4a", "aac")):
            exported = self.path / f"fallback-export.{fmt}"
            self.engine.export(master, exported, fmt, 256)
            info = fallback.probe(exported)
            self.assertEqual(info["codec"], expected, f"Fallback codec parsing failed for {fmt}")
            self.assertEqual(info["channels"], 2)

    def test_06_original_not_overwritten(self):
        with self.assertRaises(MasterForgeError):
            self.engine.master(self.source, self.source, Settings())


if __name__ == "__main__":
    unittest.main(verbosity=2)
