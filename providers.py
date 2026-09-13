"""External data with bounded requests, validation and persistent last-good cache."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

UTC = timezone.utc
WMS = 'https://view.eumetsat.int/geoserver/wms'
LAYER = 'msg_fes:ir108'


def fetch(url, timeout=25, max_bytes=8_000_000):
    with urlopen(Request(url, headers={'User-Agent': 'RaspDisplay/1.0 personal astronomy dashboard'}), timeout=timeout) as response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError('Remote response exceeds the size limit.')
        return body


def get_json(url):
    return json.loads(fetch(url))


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def location_key(config):
    return f"{config['latitude']:.5f},{config['longitude']:.5f}"


def weather(config):
    fields = ['temperature_2m', 'relative_humidity_2m', 'apparent_temperature', 'dew_point_2m',
              'precipitation_probability', 'precipitation', 'cloud_cover', 'cloud_cover_low',
              'cloud_cover_mid', 'cloud_cover_high', 'wind_speed_10m', 'wind_direction_10m', 'wind_gusts_10m']
    params = {'latitude': config['latitude'], 'longitude': config['longitude'],
              'hourly': ','.join(fields), 'current': ','.join(f for f in fields if f != 'precipitation_probability'),
              'timezone': 'UTC', 'timeformat': 'unixtime', 'forecast_days': 3, 'wind_speed_unit': 'kmh'}
    data = get_json('https://api.open-meteo.com/v1/forecast?' + urlencode(params))
    hourly = data['hourly']
    if not hourly['time'] or 'current' not in data:
        raise ValueError('Incomplete weather response')
    rows = [{'time': t, **{key: hourly[key][i] for key in fields}} for i, t in enumerate(hourly['time'])]
    return {'updated_at': datetime.now(UTC).isoformat(), 'location_key': location_key(config),
            'current': data['current'], 'hours': rows, 'source': 'Open-Meteo', 'units': data['hourly_units']}


def geocode(name, language='en'):
    data = get_json('https://geocoding-api.open-meteo.com/v1/search?' + urlencode({'name': name, 'count': 6, 'language': language}))
    return [{'name': x['name'], 'latitude': x['latitude'], 'longitude': x['longitude'],
             'elevation': x.get('elevation', 0), 'timezone': x.get('timezone', 'Europe/Amsterdam'),
             'description': ', '.join(filter(None, [x.get('admin1'), x.get('country')]))} for x in data.get('results', [])]


def satellite(config, cache):
    root = ET.fromstring(fetch(WMS + '?service=WMS&request=GetCapabilities&version=1.3.0'))
    ns = {'w': 'http://www.opengis.net/wms'}
    layer = next(x for x in root.findall('.//w:Layer', ns) if x.findtext('w:Name', namespaces=ns) == LAYER)
    dimension = next(x for x in layer.findall('w:Dimension', ns) if x.get('name') == 'time')
    text = dimension.text.strip()
    latest = text.split('/')[1] if '/' in text else text.split(',')[-1]
    last = datetime.fromisoformat(latest.replace('Z', '+00:00'))
    # A regional map in Mercator: marker is exactly in its geographic centre.
    lon, lat = config['longitude'], max(-80, min(80, config['latitude']))
    x = 6378137 * math.radians(lon)
    y = 6378137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    bbox = ','.join(str(round(v)) for v in [x - 650000, y - 250000, x + 650000, y + 250000])
    images = Path(cache) / 'satellite'
    images.mkdir(exist_ok=True, parents=True)
    frames = []
    for i in range(5, -1, -1):
        dt = last - timedelta(minutes=15 * i)
        stamp = dt.strftime('%Y%m%dT%H%MZ')
        name = f"v2_{location_key(config).replace(',', '_')}_{stamp}.png"
        path = images / name
        if not path.exists():
            params = {'service': 'WMS', 'request': 'GetMap', 'version': '1.1.1',
                      'layers': LAYER + ',backgrounds:ne_10m_coastline,osmgray:ne_10m_admin_0_boundary_lines_land',
                      'styles': ',whitelines,osmgray:all_boundaries_light', 'format': 'image/png', 'srs': 'EPSG:3857', 'bbox': bbox,
                      'width': 780, 'height': 300, 'time': dt.strftime('%Y-%m-%dT%H:%M:%SZ')}
            content = fetch(WMS + '?' + urlencode(params))
            if not content.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('WMS returned no PNG image')
            temp = path.with_suffix('.tmp')
            temp.write_bytes(content)
            temp.replace(path)
        frames.append({'time': dt.isoformat(), 'url': '/satellite/' + name})
    # Bounded cache, retain old frames briefly for clients that are still playing.
    for old in sorted(images.glob('*.png'), key=lambda p: p.stat().st_mtime, reverse=True)[36:]:
        old.unlink(missing_ok=True)
    return {'updated_at': datetime.now(UTC).isoformat(), 'image_time': last.isoformat(),
            'location_key': location_key(config), 'frames': frames, 'layer': LAYER,
            'source': 'EUMETSAT · Meteosat infrarood 10,8 μm · Natural Earth grenzen'}
