"""Regression checks for package-aware launch and frozen self-test mode."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from masterforge_python.engine import Engine, VERSION
from masterforge_python.main import Engine as UIEngine
import run_masterforge


class PackagingTests(unittest.TestCase):
    def test_07_ui_imports_same_package_engine(self):
        self.assertIs(UIEngine, Engine)
        self.assertEqual(run_masterforge.Engine, Engine)

    def test_08_entrypoint_selftest_uses_executable_ffmpeg(self):
        with tempfile.TemporaryDirectory(prefix="masterforge-packaging-") as folder:
            report = Path(folder) / "self-test.txt"
            result = subprocess.run(
                [sys.executable, str(Path(run_masterforge.__file__)),
                 "--self-test", str(report)], capture_output=True, text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(report.exists())
            self.assertIn("READY: MasterForge AI", report.read_text(encoding="utf-8"))
            self.assertIn("masterforge_python.engine", report.read_text(encoding="utf-8"))
