"""Complete UTC forecast intervals; unknown hours are never clear weather."""
from datetime import datetime
import math


FIELDS = ('cloud_cover', 'cloud_cover_low', 'cloud_cover_mid', 'cloud_cover_high',
          'temperature_2m', 'precipitation_probability', 'wind_speed_10m')


def blocks(weather, start, end, hourly=False):
    if end <= start:
        return []
    hours = {h['time']: h for h in (weather or {}).get('hours', [])}
    count = math.ceil((end-start)/3600)
    width = 1 if hourly else max(1, math.ceil(count/8))
    result = []
    edge = start
    while edge < end:
        stop = min(end, edge+width*3600)
        samples = []
        for t in range(math.floor(edge/3600)*3600, math.ceil(stop/3600)*3600, 3600):
            weight = min(stop,t+3600)-max(edge,t)
            samples.append((hours.get(t, {}), weight))
        row = dict(time=edge, end=stop, hours=(stop-edge)/3600)
        for key in FIELDS:
            valid = all(type(h.get(key)) in (int, float) and math.isfinite(h[key]) for h, _ in samples)
            row[key] = round(sum(h[key]*w for h,w in samples)/(stop-edge), 1) if valid else None
        row['stale'] = bool((weather or {}).get('stale'))
        result.append(row)
        edge = stop
    return result


def forecast_periods(weather, astronomy, now):
    start = math.floor(now/3600)*3600
    result = dict(hours=blocks(weather, start, start+8*3600, hourly=True), night=[])
    if astronomy and astronomy.get('night_start') and astronomy.get('night_end'):
        a, b = (datetime.fromisoformat(astronomy[k]).timestamp() for k in ('night_start','night_end'))
        result['night'] = blocks(weather, a, b)
    return result
