"""Small per-object altitude tracks and transparent observing-window estimates."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import threading

import numpy as np
from skyfield.api import Star

from astro import Astronomy, first_night_mask
from targets import CATALOG

engine_lock = threading.Lock()


@lru_cache(maxsize=2)
def engine(root):
    return Astronomy(root)


@lru_cache(maxsize=32)
def track(root, ident, latitude, longitude, elevation, bucket):
    with engine_lock:
        astro = engine(root)
        start = datetime.fromtimestamp(bucket * 300, timezone.utc)
        dates = [start + timedelta(minutes=10 * i) for i in range(145)]
        times = astro.ts.from_datetimes(dates)
        _, observer = astro.observer(latitude, longitude, elevation)
        at = observer.at(times)
        if ident in CATALOG:
            obj = CATALOG[ident]
            body = Star(ra_hours=obj['ra'] / 15, dec_degrees=obj['dec'])
        else:
            body = astro.eph[dict(moon='moon', venus='venus', jupiter='jupiter barycenter', saturn='saturn barycenter')[ident]]
        alt = at.observe(body).apparent().altaz()[0].degrees
        sun = at.observe(astro.eph['sun']).apparent().altaz()[0].degrees
        moon = at.observe(astro.eph['moon']).apparent().altaz()[0].degrees
        moon_distance = at.observe(body).apparent().separation_from(at.observe(astro.eph['moon']).apparent()).degrees
    eligible = first_night_mask(sun)
    return [dict(time=d.timestamp(), altitude=round(float(a), 2), sun=round(float(s), 2),
                 moon=round(float(m), 2), moon_distance=round(float(md), 1), night=bool(e))
            for d, a, s, m, md, e in zip(dates, alt, sun, moon, moon_distance, eligible)]


def observing_plan(samples, weather=None, illumination=0):
    """Prefer up to two uninterrupted hours, at least 30 minutes, >=30° and Sun<-12°.

    Cloud forecasts rank eligible windows but never invent missing coverage.
    The original samples are immutable cached data; enrich a copy for the response.
    """
    rows = [dict(s) for s in samples]
    hours = weather.get('hours', []) if weather and not weather.get('stale') else []
    for row in rows:
        nearest = min(hours, key=lambda h: abs(h['time'] - row['time']), default=None)
        row['cloud'] = nearest.get('cloud_cover') if nearest and abs(nearest['time'] - row['time']) <= 1800 else None
    good = [r['night'] and r['altitude'] >= 30 and r['sun'] < -12 for r in rows]
    candidates = []
    for start in range(len(rows) - 3):
        for length in range(3, 13):
            end = start + length
            if end >= len(rows) or not all(good[start:end + 1]):
                break
            chosen = rows[start:end + 1]
            clouds = [r['cloud'] for r in chosen]
            known = all(c is not None for c in clouds)
            cloud = float(np.mean(clouds)) if known else None
            height = float(np.mean([r['altitude'] for r in chosen]))
            moon_penalty = float(np.mean([max(0, r['moon']) / 90 * illumination / 100 *
                                          max(0, 1 - r['moon_distance'] / 120) for r in chosen]))
            # Missing coverage is neutral, never treated as a clear forecast.
            score = height / 90 * 40 + length / 12 * 25 - moon_penalty * 15 - (cloud if known else 50) * .4
            candidates.append((score, start, end, cloud, known))
    if not candidates:
        return dict(samples=rows, best=None, minimum_altitude=30, sun_limit=-12)
    _, start, end, cloud, known = max(candidates, key=lambda c: c[0])
    return dict(samples=rows, minimum_altitude=30, sun_limit=-12,
                best=dict(start=rows[start]['time'], end=rows[end]['time'], minutes=(end-start)*10,
                          cloud=round(cloud) if cloud is not None else None, weather_available=known,
                          max_altitude=round(max(r['altitude'] for r in rows[start:end+1])),
                          uncertain=not known or cloud > 60))
