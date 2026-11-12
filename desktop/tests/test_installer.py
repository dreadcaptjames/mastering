"""Static regression checks for Windows setup packaging."""
from pathlib import Path
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]

class InstallerRegressionTests(unittest.TestCase):
    def test_inno_setup_registers_clean_installer_and_uninstaller(self):
        script = (ROOT / 'installer' / 'MasterForgeAI.iss').read_text(encoding='utf-8')
        for item in ('AppId=', 'PrivilegesRequired=lowest', 'DefaultDirName={localappdata}',
                     '[Files]', '[Icons]', '[Tasks]', '[Run]', 'UninstallDisplayIcon=',
                     'MasterForge-AI.exe', 'MasterForge-AI-Setup-0.9.2'):
            self.assertIn(item,script)
        self.assertNotIn('PrivilegesRequired=admin',script)
    def test_builder_verifies_app_before_compiling(self):
        builder = (ROOT / 'BUILD-WINDOWS-INSTALLER.bat').read_text(encoding='utf-8')
        self.assertLess(builder.index('--self-test'), builder.index('"%ISCC%"'))
        self.assertIn('if not exist "dist\\MasterForge-AI.exe"',builder)
    def test_installer_assets_present(self):
        self.assertTrue((ROOT / 'masterforge_python' / 'assets' / 'icon.ico').is_file())
        self.assertTrue((ROOT / 'INSTALLATION-AND-PRIVACY.txt').is_file())

if __name__=='__main__': unittest.main()
