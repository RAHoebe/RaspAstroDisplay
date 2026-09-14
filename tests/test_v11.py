"""Regression cases for sunrise selection, complete forecasts and hardware dimming."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
from astro import Astronomy, night_mask
from display_control import DisplayController, validate
from forecast import blocks, forecast_periods
from planning import track, observing_plan
from backup import create_archive, restore_archive
from captures import CaptureStore

UTC = timezone.utc
EDE = dict(latitude=52.03333, longitude=5.65833, elevation=20, timezone='Europe/Amsterdam')


class NightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1] / '.runtime'
        cls.astro = Astronomy(cls.root)

    def test_exact_sunrise_switch(self):
        evening = self.astro.selected_night(EDE, datetime(2026,9,13,20,tzinfo=UTC))
        rise = datetime.fromisoformat(evening['sunrise'])
        before = self.astro.selected_night(EDE, rise-timedelta(microseconds=1))
        after = self.astro.selected_night(EDE, rise)
        self.assertEqual(before['night_start'], evening['night_start'])
        self.assertNotEqual(after['night_start'], before['night_start'])
        self.assertGreater(datetime.fromisoformat(after['night_start']), rise)

    def test_evening_midnight_and_morning_same_night(self):
        dates = [datetime(2026,9,13,21,tzinfo=UTC),datetime(2026,9,14,0,tzinfo=UTC),datetime(2026,9,14,4,tzinfo=UTC)]
        self.assertEqual(len({self.astro.selected_night(EDE,d)['night_start'] for d in dates}),1)

    def test_both_dst_switches_use_sunrise(self):
        for month,day in [(3,28),(10,24)]:
            night=self.astro.selected_night(EDE,datetime(2026,month,day,20,tzinfo=UTC))
            rise=datetime.fromisoformat(night['sunrise'])
            self.assertEqual(night['night_start'],self.astro.selected_night(EDE,rise-timedelta(seconds=1))['night_start'])
            self.assertNotEqual(night['night_start'],self.astro.selected_night(EDE,rise)['night_start'])

    def test_polar_day_and_night_use_local_noon(self):
        config=dict(EDE,latitude=78.2,longitude=15.6,timezone='Arctic/Longyearbyen')
        for month,hour in [(6,10),(12,11)]:
            noon=datetime(2026,month,21,hour,tzinfo=UTC)
            a=self.astro.selected_night(config,noon-timedelta(seconds=1))
            b=self.astro.selected_night(config,noon)
            self.assertTrue(a['no_sunrise'] and b['no_sunrise'])
            self.assertNotEqual(a['calendar_start'],b['calendar_start'])
            self.assertEqual(bool(b['dark']),month==12)

    def test_summer_no_astro_dark_but_has_selected_night(self):
        night=self.astro.selected_night(EDE,datetime(2026,6,21,8,tzinfo=UTC))
        self.assertFalse(night['dark'])
        self.assertFalse(night['no_sunrise'])
        self.assertTrue(night['sunset'] and night['sunrise'])

    def test_morning_hour_coverage_and_track_share_night(self):
        current=datetime(2026,9,14,5,11,tzinfo=UTC)
        data=self.astro.calculate(EDE,current)
        end=datetime.fromisoformat(data['night_end'])
        self.assertGreater((end-current).total_seconds(),86400)
        self.assertGreaterEqual(data['hours'][-1]['time'],end.timestamp())
        rows=track(str(self.root),'m31',EDE['latitude'],EDE['longitude'],20,int(current.timestamp()//300),EDE['timezone'],data['night_start'],data['night_end'])
        self.assertEqual(rows[0]['time'],datetime.fromisoformat(data['night_start']).timestamp())
        self.assertEqual(rows[-1]['time'],end.timestamp())
        eligible=[r for r in rows if r['night']]
        self.assertTrue(eligible)
        self.assertTrue(all(datetime.fromisoformat(data['night_start']).timestamp()<=r['time']<end.timestamp() for r in eligible))

    def test_advice_never_in_past_or_across_gaps(self):
        rows=[dict(time=i*600,altitude=60,sun=-20,moon=-5,moon_distance=70,night=True) for i in range(30)]
        result=observing_plan(rows,now=650)
        self.assertGreaterEqual(result['best']['start'],650)
        self.assertIsNone(observing_plan(rows,now=rows[-1]['time'])['best'])
        self.assertIsNone(observing_plan(rows[::3],now=0)['best'])

    def test_morning_moon_rise_is_not_skipped_by_evening_selection(self):
        now=datetime(2026,9,14,7,tzinfo=UTC)
        result=self.astro.calculate(EDE,now)
        rise=datetime.fromisoformat(result['moon']['rise'])
        self.assertGreater(rise,now)
        self.assertLess(rise,datetime.fromisoformat(result['calendar_start']))


class ForecastTests(unittest.TestCase):
    def weather(self):
        return dict(hours=[dict(time=i*3600,cloud_cover=20,temperature_2m=10) for i in range(72)])

    def test_entire_long_night_beyond_24h_in_eight_blocks(self):
        rows=blocks(self.weather(),23*3600,40*3600)
        self.assertLessEqual(len(rows),8)
        self.assertEqual(rows[0]['time'],23*3600)
        self.assertEqual(rows[-1]['end'],40*3600)
        self.assertEqual(sum(r['hours'] for r in rows),17)
        self.assertTrue(all(r['hours']<=3 and r['cloud_cover']==20 for r in rows))

    def test_missing_hour_null_and_nan_stay_unknown(self):
        for modification in ('missing','null','nan'):
            w=self.weather()
            if modification=='missing':w['hours'].pop(20)
            else:w['hours'][20]['cloud_cover']=None if modification=='null' else float('nan')
            rows=blocks(w,20*3600,38*3600)
            self.assertIsNone(rows[0]['cloud_cover'])
            self.assertEqual(rows[1]['cloud_cover'],20)

    def test_partial_hour_averages_weight_elapsed_time(self):
        w=dict(hours=[dict(time=0,cloud_cover=0),dict(time=3600,cloud_cover=100)])
        self.assertEqual(blocks(w,1800,5400)[0]['cloud_cover'],50)

    def test_next_eight_hours_begin_at_current_hour(self):
        rows=forecast_periods(self.weather(),None,3661)['hours']
        self.assertEqual(len(rows),8)
        self.assertEqual(rows[0]['time'],3600)
        self.assertTrue(all(r['hours']==1 for r in rows))

    def test_stale_weather_cannot_produce_confident_target_advice(self):
        w=self.weather();w['stale']=True
        rows=[dict(time=i*600,altitude=60,sun=-20,moon=-5,moon_distance=70,night=True) for i in range(15)]
        self.assertTrue(observing_plan(rows,w)['best']['uncertain'])
        self.assertFalse(observing_plan(rows,w)['best']['weather_available'])
        self.assertTrue(all(r['stale'] for r in blocks(w,0,3600)))


class DimmingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.device=self.root/'brightness';self.device.write_text('65')
        (self.root/'max_brightness').write_text('100')
        (self.root/'brightness.json').write_text('{"percent":65}')
        self.time=0
        self.controller=DisplayController(self.root,self.device,lambda:self.time)

    def tearDown(self):self.temp.cleanup()

    def tick(self,at):self.time=at;self.controller.tick()

    def test_migrates_without_losing_active_brightness(self):
        self.assertEqual(self.controller.profile,dict(active=65,idle=10,timeout=60,auto_dim=True))
        self.controller.update(dict(timeout=90))
        restored=DisplayController(self.root,self.device,lambda:self.time)
        self.assertEqual(restored.profile,self.controller.profile)
        self.assertEqual(json.loads(self.controller.path.read_text())['percent'],65)

    def test_exact_timeout_down_fade_and_wake_up_fade(self):
        self.tick(59.99);self.assertFalse(self.controller.dimmed)
        self.tick(60);self.assertTrue(self.controller.dimmed)
        self.tick(60.5);self.assertAlmostEqual(self.controller.current,37.5)
        self.tick(61);self.assertEqual(self.device.read_text(),'10')
        self.assertTrue(self.controller.activity()['wake_only'])
        self.tick(61.1);self.assertAlmostEqual(self.controller.current,37.5)
        self.tick(61.21);self.assertEqual(self.device.read_text(),'65')
        self.assertFalse(self.controller.activity()['wake_only'])

    def test_reads_do_not_postpone_idle_or_write_settings(self):
        before=self.controller.path.read_bytes()
        for i in range(63):self.controller.view();self.tick(i)
        self.assertTrue(self.controller.dimmed)
        self.assertEqual(before,self.controller.path.read_bytes())
        self.controller.activity();self.tick(64)
        self.assertEqual(before,self.controller.path.read_bytes())

    def test_restart_starts_active_and_disabled_auto_dim_stays_active(self):
        self.tick(61);self.tick(62)
        restart=DisplayController(self.root,self.device,lambda:self.time)
        self.assertFalse(restart.dimmed);self.assertEqual(restart.current,65)
        self.controller.update(dict(auto_dim=False));self.tick(63)
        self.assertEqual(self.device.read_text(),'65')

    def test_no_device_or_hardware_error_fails_open(self):
        controller=DisplayController(self.root,None,lambda:self.time)
        self.time=3600;controller.tick()
        self.assertFalse(controller.activity()['wake_only'])
        with patch.object(Path,'write_text',side_effect=OSError):self.controller.tick()
        self.assertFalse(self.controller.view()['available'])
        self.assertFalse(self.controller.activity()['wake_only'])

    def test_validation_is_atomic_and_range_bound(self):
        for value in [dict(idle=70),dict(active=0),dict(active=67),dict(timeout=9),dict(timeout=3601),dict(timeout=True),dict(auto_dim=1),dict(extra=2)]:
            before=self.controller.path.read_bytes()
            with self.assertRaises(ValueError):self.controller.update(value)
            self.assertEqual(before,self.controller.path.read_bytes())

    def test_only_loopback_with_token_can_send_activity(self):
        client=app.app.test_client();headers={'X-Astro-Token':app.csrf}
        with patch.object(app,'display',self.controller):
            self.tick(60);self.tick(61)
            for environ in [dict(REMOTE_ADDR='192.168.2.99'),dict(REMOTE_ADDR='192.168.2.99',HTTP_X_FORWARDED_FOR='127.0.0.1')]:
                self.assertEqual(client.post('/api/display/activity',json={},headers=headers,environ_overrides=environ).status_code,403)
            self.assertEqual(client.post('/api/display/activity',json={}).status_code,403)
            self.assertTrue(self.controller.dimmed)
            self.assertTrue(client.post('/api/display/activity',json={},headers=headers).json['wake_only'])

    def test_legacy_api_and_backup_restore_profile(self):
        client=app.app.test_client()
        with patch.object(app,'display',self.controller):
            for value in (55, '55'):
                result=client.post('/api/settings',json=dict(brightness=value),headers={'X-Astro-Token':app.csrf})
                self.assertEqual(result.status_code,200)
        self.assertEqual(self.controller.profile['active'],55)
        state=self.root/'state';store=CaptureStore(state)
        archive=self.root/'backup.zip'
        create_archive(state,store,{'brightness.json':json.loads(self.controller.path.read_text())},archive)
        restore_archive(archive,self.root/'restored')
        self.assertEqual(DisplayController(self.root/'restored').profile,self.controller.profile)


if __name__=='__main__':unittest.main()
