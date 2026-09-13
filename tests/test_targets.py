from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from equipment import DEFAULT_SCOPES, DEFAULT_EQUIPMENT, validate_equipment, diagonal_field
from targets import CATALOG, metadata, view_geometry, cutout_path, image_lock


class FieldsTests(unittest.TestCase):
    def test_fields_match_physical_sensor_and_diagonal(self):
        dwarf, seestar = DEFAULT_SCOPES
        self.assertAlmostEqual(dwarf['width'], 3.189, places=2)
        self.assertAlmostEqual(dwarf['height'], 1.794, places=2)
        diag = math.degrees(2*math.atan(math.hypot(math.tan(math.radians(seestar['width']/2)), math.tan(math.radians(seestar['height']/2)))))
        self.assertAlmostEqual(diag, 2.8, places=10)
        self.assertLess(seestar['width'], seestar['height'])
        self.assertAlmostEqual(seestar['width'], 1.373, places=2)

    def test_andromeda_ratio_is_length_not_area(self):
        ratio = CATALOG['m31']['major']/60/max(DEFAULT_SCOPES[0]['width'], DEFAULT_SCOPES[0]['height'])
        self.assertAlmostEqual(ratio, .9294, places=3)

    def test_fov_fits_viewport_and_target_zoom_can_crop_roi(self):
        for ident, obj in CATALOG.items():
            target=dict(id=ident, **obj)
            for scope in DEFAULT_SCOPES:
                g=view_geometry(target,scope,'fov',0)
                self.assertFalse(g['roi_outside'])
                # Image and frame share the tangent scale; pixel aspect derives from optics.
                width=g['roi'][1][0]-g['roi'][0][0]
                height=g['roi'][2][1]-g['roi'][1][1]
                expected=math.tan(math.radians(scope['width']/2))/math.tan(math.radians(scope['height']/2))
                self.assertAlmostEqual(width/height,expected,places=9)
        tiny=dict(id='m57', **CATALOG['m57'])
        self.assertTrue(view_geometry(tiny,DEFAULT_SCOPES[0],'target',0)['roi_outside'])

    def test_planet_diameter_changes_with_distance(self):
        near=metadata('jupiter', 600_000_000)['major']*60
        far=metadata('jupiter', 900_000_000)['major']*60
        self.assertTrue(48 < near < 50)
        self.assertAlmostEqual(near/far,1.5,places=6)
        self.assertIn('zonder ringen',metadata('saturn',1_300_000_000)['size_note'])

    def test_custom_scope_validation(self):
        good=dict(selected='custom-test',custom=[dict(id='custom-test',name='Mijn telescoop',width=2.3,height=1.4)])
        self.assertEqual(validate_equipment(good)['selected'],'custom-test')
        for bad in [dict(good,selected='missing'),dict(good,custom=good['custom']*2),None]:
            with self.assertRaises(ValueError):validate_equipment(bad)
        for invalid in [float('nan'),float('inf'),0,-1,21]:
            bad=deepcopy(good);bad['custom'][0]['width']=invalid
            with self.assertRaises(ValueError):validate_equipment(bad)

    def test_image_cache_reuse_and_failure_does_not_cache_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('targets.fetch',return_value=b'\xff\xd8'+b'1'*1100) as fetch:
                first=cutout_path(folder,'m31',.004)
                self.assertEqual(cutout_path(folder,'m31',.004),first)
                self.assertEqual(fetch.call_count,1)
                self.assertIn('https://alasky.cds.unistra.fr/',fetch.call_args.args[0])
            with patch('targets.fetch',return_value=b'error'):
                with self.assertRaises(ValueError):cutout_path(folder,'m31',.003)
            self.assertEqual(len(list(Path(folder).rglob('*.jpg'))),1)

    def test_image_busy_is_retryable(self):
        with tempfile.TemporaryDirectory() as folder, image_lock:
            with self.assertRaises(BlockingIOError):cutout_path(folder,'m31',.003)


if __name__ == '__main__':unittest.main()
