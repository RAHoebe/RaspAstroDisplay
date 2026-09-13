"""Location-aware astronomy. UTC internally, local calendar boundaries externally."""
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, Star, wgs84
from targets import CATALOG, metadata

UTC = timezone.utc


def night_bounds(now, zone):
    local = now.astimezone(ZoneInfo(zone))
    day = local.date() - timedelta(days=local.hour < 12)
    start = datetime.combine(day, time(12), local.tzinfo)
    end = datetime.combine(day + timedelta(days=1), time(12), local.tzinfo)
    return start.astimezone(UTC), end.astimezone(UTC)


def iso(value):
    return value.isoformat() if value else None


def direction(degrees):
    return ['N', 'NNO', 'NO', 'ONO', 'O', 'OZO', 'ZO', 'ZZO',
            'Z', 'ZZW', 'ZW', 'WZW', 'W', 'WNW', 'NW', 'NNW'][int((degrees + 11.25) / 22.5) % 16]


def first_night_mask(solar_altitudes):
    """Remaining current night, or the first upcoming night in the next 24 hours."""
    dark = np.asarray(solar_altitudes) < -6
    result = np.zeros_like(dark)
    found = np.flatnonzero(dark)
    if len(found):
        start = found[0]
        ends = np.flatnonzero(~dark[start:])
        end = start + ends[0] if len(ends) else len(dark)
        result[start:end] = True
    return result


def observing_minutes(altitudes, eligible):
    """Longest uninterrupted span above 30 degrees between ten-minute samples."""
    good = (np.atleast_2d(altitudes) >= 30) & eligible
    run = np.zeros(good.shape[0], dtype=int)
    longest = run.copy()
    for column in good.T:
        run = (run + 1) * column
        np.maximum(longest, run, out=longest)
    return np.maximum(0, longest - 1) * 10


def fixed_altitude_grid(ra_hours, dec_degrees, sidereal_hours, latitude, longitude):
    """Apparent equatorial coordinates and local apparent sidereal time, no refraction.

    Small catalog batches avoid a large stars × time × coordinate allocation on the Pi.
    Apparent RA/Dec at the current epoch vary negligibly over the next 24 hours.
    """
    dec = np.radians(np.asarray(dec_degrees))[:, None]
    hour_angle = np.radians((np.asarray(sidereal_hours)[None, :] - np.asarray(ra_hours)[:, None])*15 + longitude)
    lat = np.radians(latitude)
    sine = np.sin(lat)*np.sin(dec) + np.cos(lat)*np.cos(dec)*np.cos(hour_angle)
    return np.degrees(np.arcsin(np.clip(sine, -1, 1)))


class Astronomy:
    def __init__(self, cache):
        self.load = Loader(str(Path(cache) / 'ephemeris'))
        self.ts = self.load.timescale(builtin=True)
        self.eph = self.load('de421.bsp')  # 1899–2053; cached for offline use.
        self.catalog = [
            ('moon', 'Maan', 'Maan', self.eph['moon']),
            ('venus', 'Venus', 'Planeet', self.eph['venus']),
            ('jupiter', 'Jupiter', 'Planeet', self.eph['jupiter barycenter']),
            ('saturn', 'Saturnus', 'Planeet', self.eph['saturn barycenter']),
        ]
        self.fixed_ids = list(CATALOG)
        self.fixed = Star(ra_hours=np.array([CATALOG[i]['ra']/15 for i in self.fixed_ids]),
                          dec_degrees=np.array([CATALOG[i]['dec'] for i in self.fixed_ids]))

    def observer(self, lat, lon, elevation):
        site = wgs84.latlon(lat, lon, elevation_m=elevation)
        return site, self.eph['earth'] + site

    @lru_cache(maxsize=12)
    def events(self, start_iso, end_iso, lat, lon, elevation):
        start, end = datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso)
        site, observer = self.observer(lat, lon, elevation)
        t0, t1 = self.ts.from_datetime(start), self.ts.from_datetime(end)
        f = almanac.dark_twilight_day(self.eph, site)
        times, values = almanac.find_discrete(t0, t1, f)
        state, edge = int(f(t0)), start
        dark = []
        for t, new_state in zip(times, values):
            dt = t.utc_datetime()
            if state == 0:
                dark.append({'start': iso(edge), 'end': iso(dt)})
            state, edge = int(new_state), dt
        if state == 0:
            dark.append({'start': iso(edge), 'end': iso(end)})
        result = {'dark': dark, 'night_start': iso(start), 'night_end': iso(end)}
        for key, func in [('sunrise', almanac.find_risings), ('sunset', almanac.find_settings)]:
            tt, valid = func(observer, self.eph['sun'], t0, t1)
            result[key] = next((iso(t.utc_datetime()) for t, ok in zip(tt, valid) if ok), None)
        phase_t, phase_y = almanac.find_discrete(t0, self.ts.from_datetime(end + timedelta(days=32)), almanac.moon_phases(self.eph))
        result['phases'] = [{'time': iso(t.utc_datetime()), 'phase': int(y)} for t, y in zip(phase_t, phase_y)]
        # Retain several days so the next events can be selected each minute.
        for key, func in [('moonrises', almanac.find_risings), ('moonsets', almanac.find_settings)]:
            tt, valid = func(observer, self.eph['moon'], t0, self.ts.from_datetime(end + timedelta(days=2)))
            result[key] = [iso(t.utc_datetime()) for t, ok in zip(tt, valid) if ok]
        return result

    def calculate(self, config, now=None):
        now = now or datetime.now(UTC)
        lat, lon, elevation = (config[k] for k in ('latitude', 'longitude', 'elevation'))
        site, observer = self.observer(lat, lon, elevation)
        t = self.ts.from_datetime(now)
        at = observer.at(t)
        moon = at.observe(self.eph['moon']).apparent()
        ma, mz, md = moon.altaz()
        sun_alt = float(at.observe(self.eph['sun']).apparent().altaz()[0].degrees)
        phase = float(almanac.moon_phase(self.eph, t).degrees)
        illumination = float(almanac.fraction_illuminated(self.eph, 'moon', t)) * 100
        phase_name = ['Nieuwe maan', 'Wassende sikkel', 'Eerste kwartier', 'Wassende maan',
                      'Volle maan', 'Afnemende maan', 'Laatste kwartier', 'Afnemende sikkel'][int((phase + 22.5) / 45) % 8]
        start, end = night_bounds(now, config['timezone'])
        events = self.events(iso(start), iso(end), lat, lon, elevation)
        dates = [now + timedelta(minutes=10 * i) for i in range(145)]
        grid = self.ts.from_datetimes(dates)
        grid_observer = observer.at(grid)
        solar_alts = grid_observer.observe(self.eph['sun']).apparent().altaz()[0].degrees
        eligible = first_night_mask(solar_alts)
        targets = []
        def timing(altitudes, minutes=None):
            index = int(np.argmax(np.where(eligible, altitudes, -999)))
            best = float(altitudes[index]) if np.any(eligible) else None
            if minutes is None:
                minutes = observing_minutes(altitudes, eligible)[0]
            return dict(night_minutes_30=int(minutes), best_time=iso(dates[index]) if best is not None and best > 0 else None,
                        best_altitude=round(best, 2) if best is not None else None,
                        day_max_altitude=round(float(np.max(altitudes)), 2))

        sun = at.observe(self.eph['sun']).apparent()
        for ident, name, kind, body in self.catalog:
            current = at.observe(body).apparent()
            alt, az, _ = current.altaz()
            altitudes = grid_observer.observe(body).apparent().altaz()[0].degrees
            targets.append({**metadata(ident, float(current.distance().km)),
                            'name': name, 'kind': kind, 'category': 'moon' if ident == 'moon' else 'planet',
                            'altitude': round(float(alt.degrees), 2),
                            'azimuth': round(float(az.degrees)), 'direction': direction(float(az.degrees)),
                            'moon_distance': round(float(current.separation_from(moon).degrees)),
                            'sun_distance': round(float(current.separation_from(sun).degrees), 1),
                            **timing(altitudes),
                            **({'phase_angle':phase, 'illumination':round(illumination,1)} if ident == 'moon' else {})})

        fixed = at.observe(self.fixed).apparent()
        fa, fz, _ = fixed.altaz()
        ra, dec, _ = fixed.radec(epoch=t)
        # separation_from broadcasts the Moon against the catalog without computing 12k ephemerides.
        fm = fixed.separation_from(moon).degrees
        for offset in range(0, len(self.fixed_ids), 256):
            alts = fixed_altitude_grid(ra.hours[offset:offset+256], dec.degrees[offset:offset+256],
                                       grid.gast, lat, lon)
            durations = observing_minutes(alts, eligible)
            for j, altitudes in enumerate(alts):
                i = offset+j
                ident = self.fixed_ids[i]
                targets.append({**metadata(ident, 1), 'altitude':round(float(fa.degrees[i]), 2),
                    'azimuth':round(float(fz.degrees[i])), 'direction':direction(float(fz.degrees[i])),
                    'moon_distance':round(float(fm[i])), **timing(altitudes, durations[j])})
        targets.sort(key=lambda x: (-x['altitude'], x['name']))
        # Hour samples share timestamps with Unix-time weather API; no DST ambiguity.
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hours = [hour_start + timedelta(hours=i) for i in range(25)]
        hour_t = self.ts.from_datetimes(hours)
        hour_at = observer.at(hour_t)
        sun_hours = hour_at.observe(self.eph['sun']).apparent().altaz()[0].degrees
        moon_hours = hour_at.observe(self.eph['moon']).apparent().altaz()[0].degrees
        next_event = lambda key: next((v for v in events[key] if datetime.fromisoformat(v) >= now), None)
        return {'updated_at': iso(now), **events, 'sun_altitude': round(sun_alt, 1),
                'sky': 'Astronomisch donker' if sun_alt < -18 else 'Schemering' if sun_alt < -0.833 else 'Overdag',
                'moon': {'phase_angle': phase, 'phase_name': phase_name, 'illumination': round(illumination, 1),
                         'altitude': round(float(ma.degrees), 1), 'azimuth': round(float(mz.degrees)),
                         'direction': direction(float(mz.degrees)), 'distance_km': round(float(md.km)),
                         'rise': next_event('moonrises'), 'set': next_event('moonsets'),
                         'next_new': next((p['time'] for p in events['phases'] if p['phase'] == 0 and datetime.fromisoformat(p['time']) >= now), None),
                         'next_full': next((p['time'] for p in events['phases'] if p['phase'] == 2 and datetime.fromisoformat(p['time']) >= now), None)},
                'targets': targets, 'catalog_count':len(CATALOG),
                'target_night_start':iso(dates[int(np.flatnonzero(eligible)[0])]) if np.any(eligible) else None,
                'target_night_end':iso(dates[int(np.flatnonzero(eligible)[-1])]) if np.any(eligible) else None,
                'hours': [{'time': int(dt.timestamp()), 'sun_altitude': round(float(sa), 1), 'moon_altitude': round(float(ma), 1)}
                          for dt, sa, ma in zip(hours, sun_hours, moon_hours)]}
