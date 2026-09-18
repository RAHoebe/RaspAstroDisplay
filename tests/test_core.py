import json
import gzip
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from astro import Astronomy, night_bounds
from providers import location_key

TEST_STATE = tempfile.TemporaryDirectory()
os.environ['ASTRO_STATE'] = TEST_STATE.name
import app

UTC = timezone.utc
EDE = dict(name='Ede', latitude=52.03333, longitude=5.65833, elevation=20, timezone='Europe/Amsterdam')


class CalendarTests(unittest.TestCase):
    def test_night_is_same_before_and_after_midnight(self):
        a = night_bounds(datetime(2026, 9, 13, 21, tzinfo=UTC), 'Europe/Amsterdam')
        b = night_bounds(datetime(2026, 9, 14, 2, tzinfo=UTC), 'Europe/Amsterdam')
        self.assertEqual(a, b)

    def test_dst_nights_have_real_elapsed_duration(self):
        spring = night_bounds(datetime(2026, 3, 28, 20, tzinfo=UTC), 'Europe/Amsterdam')
        autumn = night_bounds(datetime(2026, 10, 24, 20, tzinfo=UTC), 'Europe/Amsterdam')
        self.assertEqual(spring[1] - spring[0], timedelta(hours=23))
        self.assertEqual(autumn[1] - autumn[0], timedelta(hours=25))


class AstronomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Astronomy(Path(__file__).resolve().parents[1] / '.runtime')

    def test_ede_summer_has_no_astronomical_night(self):
        a = self.engine.calculate(EDE, datetime(2026, 6, 21, 19, tzinfo=UTC))
        self.assertEqual(a['dark'], [])
        self.assertIsNotNone(a['sunset'])

    def test_polar_winter_has_no_sunrise(self):
        c = dict(EDE, latitude=78.2, longitude=15.6)
        a = self.engine.calculate(c, datetime(2026, 12, 21, 12, tzinfo=UTC))
        self.assertIsNone(a['sunrise'])
        self.assertIsNone(a['sunset'])

    def test_usno_published_sunrise_reference(self):
        # USNO reference quoted by official Skyfield almanac documentation.
        start = datetime(2018, 9, 12, 4, tzinfo=UTC)
        end = datetime(2018, 9, 13, 4, tzinfo=UTC)
        events = self.engine.events(start.isoformat(), end.isoformat(), 40.8939, -83.8917, 0)
        expected = datetime(2018, 9, 12, 11, 13, 12, tzinfo=UTC)
        self.assertLess(abs((datetime.fromisoformat(events['sunrise']) - expected).total_seconds()), 60)

    def test_moon_and_targets_have_physical_ranges(self):
        a = self.engine.calculate(EDE, datetime(2026, 9, 13, 20, tzinfo=UTC))
        self.assertTrue(0 <= a['moon']['illumination'] <= 100)
        self.assertTrue(-90 <= a['moon']['altitude'] <= 90)
        self.assertTrue(350000 < a['moon']['distance_km'] < 420000)
        for t in a['targets']:
            self.assertTrue(0 <= t['moon_distance'] <= 180)
            if t['best_time']:
                self.assertGreaterEqual(datetime.fromisoformat(t['best_time']), datetime(2026, 9, 13, 20, tzinfo=UTC))

    def test_ede_against_independent_usno_reference(self):
        # Retrieved from aa.usno.navy.mil/api on 2026-09-13, tz=2.
        a = self.engine.calculate(EDE, datetime(2026, 9, 13, 15, tzinfo=UTC))
        expected = {'sunset': datetime(2026, 9, 13, 17, 57, tzinfo=UTC),
                    'set': datetime(2026, 9, 13, 18, 17, tzinfo=UTC),
                    'next_full': datetime(2026, 9, 26, 16, 49, tzinfo=UTC),
                    'next_new': datetime(2026, 10, 10, 15, 50, tzinfo=UTC)}
        for key, value in expected.items():
            actual = a['sunset'] if key == 'sunset' else a['moon'][key]
            self.assertLess(abs((datetime.fromisoformat(actual) - value).total_seconds()), 60, key)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.headers = {'X-Astro-Token': app.csrf}

    def test_reject_cross_origin_and_missing_token(self):
        self.assertEqual(self.client.post('/api/settings', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/settings', json={}, headers={**self.headers, 'Origin': 'https://other.example'}).status_code, 403)

    def test_reject_invalid_location_without_changing_config(self):
        before = dict(app.config)
        for location in [dict(EDE, latitude=91), dict(EDE, longitude=float('nan')), dict(EDE, timezone='Invalid/Place')]:
            self.assertEqual(self.client.post('/api/settings', json={'location': location}, headers=self.headers).status_code, 400)
        self.assertEqual(app.config, before)

    def test_reject_unrecognised_host(self):
        self.assertEqual(self.client.get('/api/status', headers={'Host': 'evil.example'}).status_code, 400)

    def test_cursor_hidden_only_on_pi_kiosk_url(self):
        kiosk = self.client.get('/?kiosk=1').data
        browser = self.client.get('/').data
        self.assertIn(b'class="kiosk"', kiosk)
        self.assertIn(b'<style>html.kiosk,html.kiosk *{cursor:none!important}</style>', kiosk)
        self.assertNotIn(b'class="kiosk"', browser)

    def test_equipment_requires_token_and_persists_validated_settings(self):
        from equipment import DEFAULT_EQUIPMENT
        value=dict(selected='custom-test',custom=[dict(id='custom-test',name='Test',width=2,height=1)])
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'STATE',Path(folder)), patch.object(app,'equipment',dict(DEFAULT_EQUIPMENT)):
            self.assertEqual(self.client.post('/api/equipment',json=value).status_code,403)
            response=self.client.post('/api/equipment',json=value,headers=self.headers)
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.client.get('/api/settings').json['equipment']['selected'],'custom-test')
            self.assertEqual(json.loads((Path(folder)/'equipment.json').read_text())['selected'],'custom-test')
            self.assertEqual(self.client.post('/api/equipment',json=dict(value,selected='unknown'),headers=self.headers).status_code,400)
            self.assertEqual(app.equipment['selected'],'custom-test')

    def test_target_view_rejects_unknown_target_scope_and_zoom(self):
        from targets import metadata
        target=metadata('m31',1)
        with patch.dict(app.data,astronomy={'updated_at':datetime.now(UTC).isoformat(),'targets':[target]}):
            self.assertEqual(self.client.get('/api/targets/m31/view').status_code,200)
            for url in ['/api/targets/missing/view','/api/targets/m31/view?scope=unknown','/api/targets/m31/view?zoom=unknown']:
                self.assertIn(self.client.get(url).status_code,[400,404])

    def test_cached_data_marks_age_and_never_uses_other_location(self):
        old = {'updated_at': (datetime.now(UTC)-timedelta(hours=2)).isoformat(), 'location_key': location_key(EDE)}
        with patch.dict(app.data, weather=old), patch.object(app, 'config', EDE):
            self.assertTrue(app.snapshot()['weather']['stale'])
        with patch.dict(app.data, weather=dict(old, location_key='0,0')):
            self.assertIsNone(app.snapshot()['weather'])

    def test_catalog_response_is_separate_compressed_and_location_bound(self):
        value = dict(updated_at=datetime.now(UTC).isoformat(), location_key=location_key(EDE),
                     targets=[dict(id='moon', altitude=-10)])
        with patch.dict(app.data, astronomy=value), patch.object(app, 'config', EDE):
            self.assertNotIn('targets', self.client.get('/api/status').json['astronomy'])
            response = self.client.get('/api/targets', headers={'Accept-Encoding':'gzip'})
            self.assertEqual(response.headers['Content-Encoding'], 'gzip')
            self.assertEqual(json.loads(gzip.decompress(response.data))['targets'], value['targets'])
            self.assertEqual(self.client.get('/api/targets').json['targets'], value['targets'])
        for unavailable in [dict(value, location_key='0,0'), {k:v for k,v in value.items() if k!='targets'}]:
            with patch.dict(app.data, astronomy=unavailable), patch.object(app, 'config', EDE):
                self.assertEqual(self.client.get('/api/targets').status_code, 503)

    def test_astronomy_cache_keeps_summary_and_positions_stay_in_memory(self):
        value = dict(updated_at=datetime.now(UTC).isoformat(), targets=[dict(id='moon')])
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'STATE', Path(folder)), patch.dict(app.data), patch.object(app, 'config', EDE), patch('app.time.sleep', side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                app.worker('astronomy', 60, lambda _: dict(value))
            self.assertNotIn('targets', json.loads((Path(folder)/'astronomy.json').read_text()))
            self.assertEqual(app.data['astronomy']['targets'], value['targets'])

    def test_failed_provider_does_not_erase_last_good_data(self):
        old = {'updated_at': datetime.now(UTC).isoformat(), 'location_key': location_key(EDE)}
        def failed(_):
            raise OSError('offline')
        with patch.dict(app.data, weather=old), patch.object(app, 'config', EDE), patch('app.time.sleep', side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                app.worker('weather', 900, failed)
            self.assertEqual(app.snapshot()['weather']['updated_at'], old['updated_at'])
            self.assertIn('weather', app.snapshot()['errors'])
        app.errors.clear()


if __name__ == '__main__':
    unittest.main()
