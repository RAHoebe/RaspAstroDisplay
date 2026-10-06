import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from xml.etree import ElementTree
from datetime import datetime
from zoneinfo import ZoneInfo

TEMP = tempfile.TemporaryDirectory()
os.environ.setdefault('ASTRO_STATE', TEMP.name)
import app
from skykaart import night_chart, chart_svg

ROOT = Path(__file__).resolve().parents[1]
EDE = dict(name='Ede', latitude=52.03333, longitude=5.65833, elevation=20, timezone='Europe/Amsterdam')


class SkykaartTests(unittest.TestCase):
    def chart(self, ident='m1', evening='2026-10-01', **coords):
        c = dict(EDE, **coords)
        return night_chart(str(ROOT / '.runtime'), ident, evening, c['latitude'], c['longitude'], c['elevation'], c['timezone'])

    def test_full_night_is_pinned_and_positions_are_physical(self):
        chart = self.chart()
        start = datetime.fromisoformat(chart['start']).astimezone(ZoneInfo(EDE['timezone']))
        end = datetime.fromisoformat(chart['end']).astimezone(ZoneInfo(EDE['timezone']))
        self.assertEqual(start.date().isoformat(), '2026-10-01')
        self.assertEqual(end.date().isoformat(), '2026-10-02')
        self.assertEqual(chart['samples'][0]['time'], start.timestamp())
        self.assertEqual(chart['samples'][-1]['time'], end.timestamp())
        for r in chart['samples']:
            self.assertTrue(-90 <= r['altitude'] <= 90)
            self.assertTrue(0 <= r['azimuth'] <= 360)
        self.assertGreater(max(r['altitude'] for r in chart['samples']), 30)
        self.assertIsNotNone(chart['best'])
        self.assertGreater(len(chart['stars']), 8000)
        self.assertEqual(chart['constellation'], 'Taurus')
        self.assertTrue(all(s['sun'] < -18 for s in chart['samples'] if chart['best']['start'] <= s['time'] <= chart['best']['end']))

    def test_dst_repeated_hour_has_distinct_zone_labels(self):
        chart = self.chart(evening='2026-10-24')
        labels = [datetime.fromtimestamp(r['time'], ZoneInfo(EDE['timezone'])).strftime('%H:%M %Z') for r in chart['samples']]
        self.assertTrue(any('CEST' in label for label in labels))
        self.assertTrue(any('CET' in label and 'CEST' not in label for label in labels))
        self.assertEqual(len({r['time'] for r in chart['samples']}), len(labels))

    def test_fixed_planet_moon_and_polar_charts(self):
        for ident in ('m31', 'moon', 'venus', 'jupiter', 'saturn'):
            svg = chart_svg(self.chart(ident), ident, EDE['timezone'])
            ElementTree.fromstring(svg)
        polar = self.chart(latitude=78.2, longitude=15.6, evening='2026-12-21')
        self.assertIsNone(polar['events']['sunrise'])
        self.assertEqual(polar['samples'][-1]['time'] - polar['samples'][0]['time'], 86400)

    def test_saved_url_keeps_date_location_and_escapes_html(self):
        chart = self.chart()
        params = dict(date='2026-10-01',latitude=EDE['latitude'],longitude=EDE['longitude'],elevation=20,timezone=EDE['timezone'],location='<script>alert(1)</script>')
        with patch.object(app, 'night_chart', return_value=chart) as compute:
            client = app.app.test_client()
            response = client.get('/skykaart/m1?' + urlencode(params))
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'2026-10-01', response.data)
            self.assertNotIn(b'<script>alert(1)</script>', response.data)
            self.assertIn(b'&lt;script&gt;', response.data)
            self.assertEqual(compute.call_args.args[2], '2026-10-01')
            self.assertEqual(compute.call_args.args[3], EDE['latitude'])
            download = client.get('/skykaart/m1?' + urlencode(dict(params, download='1')))
            self.assertEqual(download.mimetype, 'image/svg+xml')
            ElementTree.fromstring(download.data)
            self.assertIn('skykaart-m1-2026-10-01.svg', download.headers['Content-Disposition'])

    def test_invalid_requests_do_not_compute(self):
        with patch.object(app, 'night_chart') as compute:
            for suffix in ('?date=2026-02-30', '?date=2099-01-01', '?latitude=nan', '?latitude=91', '?timezone=Invalid/Place'):
                self.assertEqual(app.app.test_client().get('/skykaart/m1'+suffix).status_code, 400)
            self.assertEqual(app.app.test_client().get('/skykaart/missing?date=2026-10-01').status_code, 404)
            compute.assert_not_called()

    def test_ephemeris_failure_is_retryable(self):
        with patch.object(app, 'night_chart', side_effect=OSError('offline')), self.assertLogs('astro', level='ERROR'):
            self.assertEqual(app.app.test_client().get('/skykaart/m1?date=2026-10-01').status_code, 503)


if __name__ == '__main__':
    unittest.main()
