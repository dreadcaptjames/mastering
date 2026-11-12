"""Regression tests for independently persisted per-user mastering defaults."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
import unittest
from unittest.mock import patch

from masterforge_python.main import (
    FACTORY_MASTERING_DEFAULTS, LOUDNESS_CHOICES, normalized_mastering_defaults,
)
from masterforge_python.polished_ui import PolishedMasterForgeWindow


class DefaultValidationTests(unittest.TestCase):
    def test_factory_defaults_are_signature_and_streaming(self):
        result = normalized_mastering_defaults(None)
        self.assertEqual(result['preset'], 'signature')
        self.assertEqual(result['target'], '-14 LUFS · Streaming')
        self.assertEqual(result, FACTORY_MASTERING_DEFAULTS)
        self.assertIn(result['target'], LOUDNESS_CHOICES)

    def test_bad_preferences_are_rejected_without_crashing(self):
        result = normalized_mastering_defaults({
            'preset': 'unrecognized', 'target': '0 LUFS · Clipped',
            'warmth': float('nan'), 'clarity': 5000, 'intensity': 'not a number',
        })
        self.assertEqual(result, FACTORY_MASTERING_DEFAULTS)

    def test_legal_custom_defaults_survive_normalization(self):
        desired = dict(preset='impact', target='-16 LUFS · Open',
                       warmth=2.5, clarity=-1.25, intensity=1.0)
        self.assertEqual(normalized_mastering_defaults(desired), desired)


@unittest.skipIf(os.environ.get('DISPLAY') is None and os.name != 'nt', 'Tk desktop display required')
class PersistedPreferencesUITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='masterforge-preferences-test-')
        self.preferences = Path(self.temp.name) / 'preferences.json'
        self.mock_file = patch('masterforge_python.main.user_config_file', lambda: self.preferences)
        self.mock_file.start()
        self.root = None
        self.app = None

    def tearDown(self):
        self.close_window()
        self.mock_file.stop()
        self.temp.cleanup()

    def open_window(self):
        self.root = tk.Tk()
        self.app = PolishedMasterForgeWindow(self.root)
        self.root.update()

    def close_window(self):
        if self.app is not None:
            self.app._shutdown()
            self.app = None
            self.root = None

    def test_first_launch_and_save_persist_across_restart_and_theme_change(self):
        self.open_window()
        self.assertEqual(self.app.preset.get(), 'signature')
        self.assertEqual(self.app.target.get(), '-14 LUFS · Streaming')
        self.assertIn('Signature', self.app.saved_defaults_label.cget('text'))
        self.assertTrue(self.app.save_defaults_button.winfo_exists())
        self.app._choose_preset('natural')
        self.app.target.set('-10 LUFS · Loud')
        self.app.warmth.set(1.3)
        self.app.clarity.set(-0.5)
        self.app.intensity.set(0.75)
        self.app.save_mastering_defaults()
        self.assertEqual(self.app.startup_mastering['preset'], 'natural')
        self.assertIn('Natural', self.app.saved_defaults_label.cget('text'))
        self.app.select_theme('Midnight Violet')
        self.app.select_aesthetic('Hybrid')
        self.assertEqual(self.app.preset.get(), 'natural')
        self.assertEqual(self.app.target.get(), '-10 LUFS · Loud')
        self.close_window()
        saved=json.loads(self.preferences.read_text(encoding='utf-8'))
        self.assertEqual(saved['palette'], 'Midnight Violet')
        self.assertEqual(saved['mastering_defaults']['preset'], 'natural')
        self.open_window()
        self.assertEqual(self.app.aesthetic.get(), 'Hybrid')
        self.assertEqual(self.app.palette.get(), 'Midnight Violet')
        self.assertEqual(self.app.preset.get(), 'natural')
        self.assertEqual(self.app.target.get(), '-10 LUFS · Loud')
        self.assertAlmostEqual(self.app.warmth.get(), 1.3)
        self.assertAlmostEqual(self.app.clarity.get(), -0.5)
        self.assertAlmostEqual(self.app.intensity.get(), .75)
        # Unsaved changes should not replace the saved startup state.
        self.app._choose_preset('impact')
        self.app.target.set('-9 LUFS · Max Impact')
        self.close_window()
        self.open_window()
        self.assertEqual(self.app.preset.get(), 'natural')
        self.assertEqual(self.app.target.get(), '-10 LUFS · Loud')

    def test_reset_restores_initial_settings_without_resetting_theme(self):
        self.open_window()
        self.app.select_theme('Cyberwave')
        self.app._choose_preset('impact')
        self.app.target.set('-16 LUFS · Open')
        self.app.warmth.set(2.0)
        self.app.save_mastering_defaults()
        self.app.reset_mastering_defaults()
        self.assertEqual(self.app.preset.get(), 'signature')
        self.assertEqual(self.app.target.get(), '-14 LUFS · Streaming')
        self.assertEqual(self.app.warmth.get(), 0.0)
        self.assertEqual(self.app.palette.get(), 'Cyberwave')
        self.close_window()
        self.open_window()
        self.assertEqual(self.app.preset.get(), 'signature')
        self.assertEqual(self.app.target.get(), '-14 LUFS · Streaming')
        self.assertEqual(self.app.palette.get(), 'Cyberwave')

    def test_previous_theme_only_settings_upgrade_safely(self):
        self.preferences.parent.mkdir(parents=True, exist_ok=True)
        self.preferences.write_text(json.dumps({'palette': 'Ember Studio', 'aesthetic': 'Analog Hardware'}), encoding='utf-8')
        self.open_window()
        self.assertEqual(self.app.palette.get(), 'Ember Studio')
        self.assertEqual(self.app.preset.get(), 'signature')
        self.assertEqual(self.app.target.get(), '-14 LUFS · Streaming')
        self.app.save_mastering_defaults()
        result=json.loads(self.preferences.read_text(encoding='utf-8'))
        self.assertEqual(result['palette'], 'Ember Studio')
        self.assertEqual(result['aesthetic'], 'Analog Hardware')
        self.assertEqual(result['mastering_defaults']['preset'], 'signature')
