from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import numpy as np
from skyfield.api import Star
from astro import Astronomy, first_night_mask, fixed_altitude_grid, observing_minutes
from targets import CATALOG, metadata, view_geometry
from equipment import DEFAULT_SCOPES

EDE=dict(name='Ede',latitude=52.03333,longitude=5.65833,elevation=20,timezone='Europe/Amsterdam')


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Astronomy(Path(__file__).resolve().parents[1]/'.runtime')

    def test_broad_catalog_and_named_nebulae(self):
        self.assertGreater(len(CATALOG),12000)
        self.assertGreater(sum(t['category']=='nebula' for t in CATALOG.values()),400)
        for ident in ['m42','m8','m16','ngc7000','ic1805','ngc6888','b33']:
            self.assertEqual(CATALOG[ident]['category'],'nebula',ident)
        self.assertTrue(all(0<=t['ra']<360 and -90<=t['dec']<=90 for t in CATALOG.values()))

    def test_first_night_excludes_tomorrows_second_evening(self):
        self.assertEqual(first_night_mask([-12,-8,0,20,0,-8,-12]).tolist(),[True,True,False,False,False,False,False])
        self.assertEqual(first_night_mask([15,0,-8,-12,-4,10]).tolist(),[False,False,True,True,False,False])
        self.assertFalse(first_night_mask([10,5,0]).any())

    def test_catalog_grid_agrees_with_full_skyfield_positions(self):
        now=datetime(2026,9,13,18,tzinfo=timezone.utc)
        e=self.engine;_,obs=e.observer(52.03333,5.65833,20)
        t=e.ts.from_datetime(now)
        grid=e.ts.from_datetimes([now+timedelta(hours=i) for i in range(0,25,4)])
        for ident in ['m31','ngc7000','ic1805','m8','m45']:
            c=CATALOG[ident];star=Star(ra_hours=c['ra']/15,dec_degrees=c['dec'])
            ra,dec,_=obs.at(t).observe(star).apparent().radec(epoch=t)
            approximate=fixed_altitude_grid([ra.hours],[dec.degrees],grid.gast,52.03333,5.65833)[0]
            exact=obs.at(grid).observe(star).apparent().altaz()[0].degrees
            self.assertLess(float(np.max(np.abs(approximate-exact))),.02,ident)

    def test_morning_uses_upcoming_night_and_current_altitude_order(self):
        now=datetime(2026,9,14,8,tzinfo=timezone.utc)
        a=self.engine.calculate(EDE,now)
        self.assertEqual(datetime.fromisoformat(a['target_night_start']).date(),now.date())
        self.assertGreater(datetime.fromisoformat(a['target_night_start']).hour,16)
        rows=a['targets']
        self.assertEqual([r['altitude'] for r in rows],sorted([r['altitude'] for r in rows],reverse=True))
        self.assertIn('moon',[r['id'] for r in rows])
        self.assertNotIn('mars',[r['id'] for r in rows])
        self.assertEqual(sum(r['category']=='planet' for r in rows),3)
        visible=[r for r in rows if r['category']=='nebula' and (r['best_altitude'] or -90)>0]
        self.assertGreater(len(visible),100)
        self.assertTrue(any(r['altitude']<0 for r in visible))

    def test_unknown_sizes_do_not_invent_percentages(self):
        ident=next(k for k,v in CATALOG.items() if v['major'] is None)
        target=metadata(ident,1)
        g=view_geometry(target,DEFAULT_SCOPES[0],'target',0)
        self.assertIsNone(target['major'])
        self.assertIsNone(g['target_pixels'])
        self.assertTrue(g['size_unknown'])
        self.assertGreater(g['field_width'],0)

    def test_observing_duration_uses_contiguous_dark_intervals(self):
        rows=[[40,40,40,40,40,40],[40,20,40,40,20,40],[0,0,0,0,0,0]]
        self.assertEqual(observing_minutes(rows,np.array([False,True,True,True,True,False])).tolist(),[30,10,0])
        self.assertEqual(observing_minutes(rows,np.zeros(6,dtype=bool)).tolist(),[0,0,0])


if __name__=='__main__':unittest.main()
