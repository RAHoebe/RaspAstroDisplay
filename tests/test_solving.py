import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from astropy.io import fits

from solving import matched_stars, solve, run_attempt


def correspondences(path, offset=.3, compact=False):
    xx, yy = np.meshgrid(np.linspace(10,190,5), np.linspace(10,90,4))
    if compact:
        xx, yy = xx/100+20, yy/100+20
    cols=[fits.Column(name=k, format='D', array=v.ravel()) for k,v in
          [('field_x',xx),('field_y',yy),('index_x',xx+offset),('index_y',yy)]]
    fits.BinTableHDU.from_columns(cols).writeto(path,overwrite=True)


class SolverTests(unittest.TestCase):
    def test_matches_require_accuracy_and_spatial_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'stars.corr'
            correspondences(p)
            q=matched_stars(p,200,100)
            self.assertEqual(q['matched_stars'],20)
            self.assertAlmostEqual(q['median_residual_pixels'],.3)
            self.assertEqual(q['stars'][0][:2],[9,90])
            for offset,compact in [(10,False),(.3,True)]:
                correspondences(p,offset,compact)
                with self.assertRaises(ValueError): matched_stars(p,200,100)

    def test_fallback_ignores_position_after_nearby_failure_and_flips_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); image=Image.fromarray(np.tile(np.arange(100,dtype=np.uint8)[:,None],(1,200))).convert('RGB')
            commands=[]
            def run(cmd,where,name,timeout):
                commands.append(cmd)
                if name=='astrometry-near': return False
                data=fits.getdata(folder/'solve-input.fits')
                self.assertEqual(data[0,0],99)
                self.assertEqual(data[-1,0],0)
                (folder/'astrometry-blind.wcs').write_bytes(b'solved')
                correspondences(folder/'astrometry-blind.corr')
                return True
            with patch('solving.astrometry_available',return_value=True), patch('solving.astrometry_paths',return_value=('solve-field',folder)), patch('solving.run_attempt',side_effect=run):
                solver,q=solve(image,folder/'own.png',folder,dict(ra=10,dec=20),1,folder/'missing',folder,lambda *a,**k:None)
            self.assertEqual(solver,'Astrometry.net local')
            self.assertIn('--ra',commands[0]);self.assertNotIn('--ra',commands[1])
            self.assertFalse((folder/'solve-input.fits').exists())
            self.assertEqual(q['matched_stars'],20)

    def test_astap_timeout_does_not_prevent_second_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'astap').touch();(p/'d50-test.1476').touch()
            def run(cmd,folder,name,timeout):
                if name=='astap-1': return False
                (folder/'astap-2.wcs').write_bytes(b'solved'); return True
            with patch('solving.run_attempt',side_effect=run) as mocked:
                solver,_=solve(Image.new('RGB',(200,100)),p/'own.png',p,dict(ra=10,dec=20),1,p/'astap',p,lambda *a,**k:None)
            self.assertEqual(solver,'ASTAP local');self.assertEqual(mocked.call_count,2)

    def test_timeout_terminates_solver(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(run_attempt([sys.executable,'-c','import time; time.sleep(5)'],Path(tmp),'timeout',.1))
