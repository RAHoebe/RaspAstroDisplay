from pathlib import Path
import tempfile
import unittest

from deploy.cursor import install_theme


class CursorThemeTests(unittest.TestCase):
    def test_installs_theme_in_xcursor_and_xdg_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            self.assertEqual(install_theme(home), 'AstroInvisible')
            for folder in (home / '.icons/AstroInvisible', home / '.local/share/icons/AstroInvisible'):
                self.assertTrue((folder / 'index.theme').is_file())
                self.assertEqual((folder / 'cursors/default').read_bytes()[-4:], b'\0\0\0\0')