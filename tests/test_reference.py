"""Independent planet-position comparison against PyEphem / XEphem algorithms."""
from datetime import datetime, timezone
import math
from pathlib import Path
import unittest
import ephem
from astro import Astronomy


class IndependentPositions(unittest.TestCase):
    def test_planet_positions_agree_with_pyephem(self):
        config = dict(name='Ede', latitude=52.03333, longitude=5.65833, elevation=20, timezone='Europe/Amsterdam')
        now = datetime(2026, 9, 13, 20, tzinfo=timezone.utc)
        engine = Astronomy(Path(__file__).resolve().parents[1] / '.runtime')
        actual = {t['name']: t for t in engine.calculate(config, now)['targets']}
        obs = ephem.Observer()
        obs.lat, obs.lon = str(config['latitude']), str(config['longitude'])
        obs.elevation, obs.pressure, obs.date = 20, 0, now.replace(tzinfo=None)
        for name, body in [('Maan', ephem.Moon()), ('Venus', ephem.Venus()), ('Jupiter', ephem.Jupiter()), ('Saturnus', ephem.Saturn())]:
            body.compute(obs)
            self.assertLess(abs(actual[name]['altitude'] - math.degrees(body.alt)), 0.15, name)
            self.assertLess(abs((actual[name]['azimuth'] - math.degrees(body.az) + 180) % 360 - 180), 0.6, name)
