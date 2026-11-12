"""Regression checks: real duration, visible playhead, A/B waveform switching."""
import os
import unittest
from pathlib import Path
from unittest import mock
import tkinter as tk

from masterforge_python.polished_ui import PolishedMasterForgeWindow, TimelineScrubber


@unittest.skipIf(os.environ.get('DISPLAY') is None and os.name != 'nt', 'Needs a graphical display (e.g., xvfb-run)')
class TimelineUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = PolishedMasterForgeWindow(self.root)
        self.root.update()

    def tearDown(self):
        self.app._shutdown()

    def test_full_track_seek_and_visible_scrubber(self):
        app = self.app
        self.assertIsInstance(app.seek, TimelineScrubber)
        app.source = Path('/tmp/test-source.wav')
        app.source_info = {'duration': 219.4,'sample_rate':48000,'channels':2,'codec':'pcm_s16le'}
        app.original_waveform = [0.25] * 360
        app._sync_waveform_view(position=0)
        self.root.update()
        self.assertAlmostEqual(app.seek.duration,219.4)
        self.assertTrue(app.seek.find_all())  # Canvas renders its visible draggable thumb
        self.assertTrue(app.wave_canvas.find_withtag('playhead'))

        # Simulate a real mouse drag to 95% of the seek bar's width.
        width = app.seek.winfo_width()
        y = 19
        app.seek.event_generate('<ButtonPress-1>',x=16,y=y)
        app.seek.event_generate('<B1-Motion>',x=int(width*.95),y=y)
        app.seek.event_generate('<ButtonRelease-1>',x=int(width*.95),y=y)
        self.root.update()
        self.assertGreater(app.seek.get(),190)
        self.assertLessEqual(app.seek.get(),219.4)
        self.assertIn('03:39', app.time_label.cget('text'))

    def test_switch_source_and_master_after_render(self):
        app=self.app
        app.source = Path('/tmp/test-source.wav')
        app.source_info = {'duration':219.4,'sample_rate':48000,'channels':2,'codec':'pcm_s16le'}
        app.original_waveform=[.24,.52,.17,.25]*90
        app.master = Path('/tmp/test-master.wav')
        app.master_info = {'duration':219.2,'sample_rate':48000,'channels':2,'codec':'pcm_s24le'}
        app.master_waveform=[.81,.92,.71,.83]*90
        app._sync_waveform_view(position=151)
        self.assertIs(app.waveform,app.original_waveform)
        self.assertAlmostEqual(app.seek.duration,219.4)
        original_items=app.wave_canvas.find_all()
        app._select_ab('Mastered')
        self.root.update()
        self.assertIs(app.waveform,app.master_waveform)
        self.assertEqual(app.wave_title.cget('text'),'●  MASTERED WAVEFORM')
        self.assertAlmostEqual(app.seek.duration,219.2)
        self.assertAlmostEqual(app.seek.get(),151)
        self.assertIn('03:39',app.time_label.cget('text'))
        app._select_ab('Original')
        self.assertIs(app.waveform,app.original_waveform)
        self.assertEqual(app.wave_title.cget('text'),'●  ORIGINAL WAVEFORM')
        self.assertAlmostEqual(app.seek.get(),151)
        app.select_theme('Midnight Violet')
        self.root.update()
        self.assertAlmostEqual(app.seek.duration,219.4)
        self.assertAlmostEqual(app.seek.get(),151)
        self.assertIs(app.waveform,app.original_waveform)
        self.assertTrue(original_items)

    def test_playback_uses_real_seek_position_beyond_100_seconds(self):
        app=self.app
        app.source=Path('/tmp/long-input.wav')
        app.source_info={'duration':219.4,'sample_rate':48000,'channels':2,'codec':'pcm_s16le'}
        app.original_waveform=[.2]*360
        app.master=Path('/tmp/long-master.wav')
        app.master_info={'duration':219.4,'sample_rate':48000,'channels':2,'codec':'pcm_s24le'}
        app.master_waveform=[.7]*360
        app.ab_mode.set('Mastered')
        app._sync_waveform_view(position=185.25)
        fake_process=mock.MagicMock()
        fake_process.poll.return_value=None
        with mock.patch('masterforge_python.main.ffplay_binary',return_value='/fake/ffplay'), \
             mock.patch('masterforge_python.main.subprocess.Popen',return_value=fake_process) as popen:
            app._start_play(app.seek.get())
        cmd=popen.call_args.args[0]
        self.assertEqual(Path(cmd[-1]), app.master, 'Playback must use the selected file path on this operating system')
        self.assertEqual(cmd[cmd.index('-ss')+1],'185.25')
        self.assertAlmostEqual(app.play_offset,185.25)

    def test_switching_before_master_is_ready_does_not_fake_an_ab_waveform(self):
        app = self.app
        app._select_ab('Mastered')
        self.assertEqual(app.ab_mode.get(),'Original')
