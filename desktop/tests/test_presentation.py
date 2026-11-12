"""Headless checks for the Python Studio visual refresh."""
import unittest
from masterforge_python.main import MasterForgeWindow, PALETTES, AESTHETICS
from masterforge_python.polished_ui import PolishedMasterForgeWindow, blend


class PresentationTests(unittest.TestCase):
    def test_presentation_inherits_existing_engine_workflow(self):
        self.assertTrue(issubclass(PolishedMasterForgeWindow, MasterForgeWindow))
        self.assertIs(PolishedMasterForgeWindow.make_master, MasterForgeWindow.make_master)
        self.assertIs(PolishedMasterForgeWindow.open_audio, MasterForgeWindow.open_audio)
        self.assertIs(PolishedMasterForgeWindow.save_report, MasterForgeWindow.save_report)

    def test_themes_and_aesthetics_preserved(self):
        self.assertEqual(len(PALETTES), 6)
        self.assertEqual(len(AESTHETICS), 4)
        for palette in PALETTES.values():
            self.assertTrue(all(x in palette for x in ('bg','panel','accent','text','wave')))

    def test_color_blending(self):
        self.assertEqual(blend('#000000','#ffffff',0),'#000000')
        self.assertEqual(blend('#000000','#ffffff',1),'#ffffff')
