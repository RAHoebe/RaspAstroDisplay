import configparser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deploy import display

BEFORE = '''# Preserve unrelated settings
[input]
xkb_layout = us
[output:DSI-1]
mode = 800x480@60049
position = 0,0
transform = 180
[autostart]
astro = /home/pi/RaspDisplay/deploy/start-kiosk.sh
screensaver = false
[input-device:raspberrypi-ts]
output = DSI-1
'''


class DisplayTests(unittest.TestCase):
    def test_default_does_not_change_original_kiosk(self):
        with tempfile.TemporaryDirectory() as root:
            chosen = display.load_selection(Path(root) / 'absent.json')
        self.assertEqual(chosen['rotation'], '180')
        self.assertEqual(display.kiosk_args(chosen), ['--window-size=800,480', '--force-device-scale-factor=1'])

    def test_touch2_and_upside_down_remain_landscape(self):
        for flipped, rotation in [(False, '90'), (True, '270')]:
            chosen = display.selection('touch2', flipped)
            self.assertEqual(chosen['rotation'], rotation)
            self.assertEqual(display.kiosk_args(chosen), ['--window-size=853,480', '--force-device-scale-factor=1.5'])
        self.assertEqual(display.selection('original', True)['rotation'], 'normal')
        self.assertEqual(display.kiosk_args(display.selection('touch2', compact=True)),
                         ['--window-size=1024,576', '--force-device-scale-factor=1.25'])

    def test_touch_detection_ignores_pointer_and_keyboard(self):
        devices = ('N: Name="Keyboard"\nB: PROP=0\nB: EV=120013\n\n'
                   'N: Name="Touchpad"\nB: PROP=5\nB: EV=b\n\n'
                   'N: Name="Goodix Capacitive TouchScreen"\nB: PROP=2\nB: EV=b\n\n')
        self.assertEqual(display.touch_names(devices), ['Goodix Capacitive TouchScreen'])
        self.assertEqual(display.touch_names(devices.replace('Goodix Capacitive TouchScreen', 'raspberrypi-ts')),
                         ['raspberrypi-ts'])

    def test_hardware_must_match_before_writes(self):
        old = [dict(output='DSI-1', modes=['800x480'])]
        new = [dict(output='DSI-1', modes=['720x1280'])]
        chosen = display.selection('touch2')
        for displays, names in [(old, ['touch']), (new, []), (new, ['a', 'b']),
                                (new + [dict(output='HDMI-A-1', modes=[])], ['touch'])]:
            with self.assertRaises(ValueError):
                display.check_hardware(chosen, displays, names)
        self.assertEqual(display.check_hardware(chosen, new, ['a', 'b'], 'b'), ('DSI-1', 'b'))
        with self.assertRaises(ValueError):
            display.check_hardware(chosen, new, ['a'], 'missing')

    def test_round_trip_preserves_autostart_and_touch_follows_output(self):
        new = display.wayfire_config(BEFORE, display.selection('touch2'), 'DSI-1', 'Goodix TouchScreen')
        cfg = configparser.ConfigParser()
        cfg.read_string(new)
        self.assertEqual(cfg['output:DSI-1']['transform'], '90')
        self.assertNotIn('mode', cfg['output:DSI-1'])
        self.assertEqual(cfg['input-device:Goodix TouchScreen']['output'], 'DSI-1')
        self.assertIn('[autostart]\nastro = /home/pi/RaspDisplay/deploy/start-kiosk.sh\nscreensaver = false\n', new)
        self.assertTrue(new.startswith('# Preserve unrelated settings\n[input]\nxkb_layout = us\n'))
        self.assertEqual(display.wayfire_config(new, display.selection('touch2'), 'DSI-1', 'Goodix TouchScreen'), new)
        old = display.wayfire_config(new, display.selection(), 'DSI-1', 'raspberrypi-ts')
        cfg.read_string(old)
        self.assertEqual(cfg['output:DSI-1']['transform'], '180')

    def test_existing_touch_fix_is_noop(self):
        self.assertEqual(display.edit_section(BEFORE, 'input-device:raspberrypi-ts', dict(output='DSI-1')), BEFORE)

    def test_backup_and_selection_survive_reload(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            wf, profile = root / 'wayfire.ini', root / 'profile.json'
            wf.write_text(BEFORE)
            data = dict(profile='touch2', flipped=True, compact=False)
            backup = display.save_changes('new config', data, wf, profile, root / 'backups')
            self.assertEqual((backup / 'wayfire.ini').read_text(), BEFORE)
            self.assertTrue((backup / 'no-previous-profile').exists())
            self.assertEqual(display.load_selection(profile)['rotation'], '270')
            self.assertEqual(wf.read_text(), 'new config')
            profile.write_text(json.dumps(dict(profile='touch2', flipped='false', compact=False)))
            with self.assertRaises(ValueError):
                display.load_selection(profile)

    def test_failed_wayfire_write_restores_both_files(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            wf, profile = root / 'wayfire.ini', root / 'profile.json'
            wf.write_text(BEFORE)
            original = dict(profile='original', flipped=False, compact=False)
            profile.write_text(json.dumps(original))
            real_write = display.atomic_write

            def fail_wayfire(path, text):
                if path == wf:
                    raise OSError('simulated write failure')
                real_write(path, text)

            with patch.object(display, 'atomic_write', side_effect=fail_wayfire):
                with self.assertRaises(OSError):
                    display.save_changes('new', dict(profile='touch2', flipped=False, compact=False),
                                         wf, profile, root / 'backups')
            self.assertEqual(wf.read_text(), BEFORE)
            self.assertEqual(json.loads(profile.read_text()), original)


if __name__ == '__main__':
    unittest.main()
