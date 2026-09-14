from copy import deepcopy
from functools import lru_cache
from datetime import datetime, timezone
import json
import gzip
import logging
import math
import os
import socket
import re
import subprocess
import ipaddress
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, jsonify, request, send_from_directory, send_file, abort, Response
from waitress import serve
from astro import Astronomy
from providers import weather, satellite, geocode, save_json, read_json, location_key
from equipment import DEFAULT_EQUIPMENT, equipment_view, validate_equipment
from targets import CATALOG, IDS, view_geometry, cutout_path, survey_for
from captures import CaptureStore, DuplicateCapture, MAX_BYTES
from ranking import recommendation
from backup import BackupManager
from comparison import ComparisonManager
from planning import track, observing_plan
from display_control import DisplayController, validate as validate_display
from forecast import forecast_periods

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get('ASTRO_STATE', ROOT / '.runtime'))
STATE.mkdir(parents=True, exist_ok=True)
UTC = timezone.utc
DEFAULT = json.loads((ROOT / 'config.example.json').read_text())
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 8192
log = logging.getLogger('astro')
lock = threading.RLock()
config = read_json(STATE / 'config.json', DEFAULT)
preferences = read_json(STATE / 'preferences.json', {'language': 'en-US'})
try:
    equipment = validate_equipment(read_json(STATE / 'equipment.json', DEFAULT_EQUIPMENT))
except (ValueError, TypeError):
    equipment = deepcopy(DEFAULT_EQUIPMENT)
data = {k: read_json(STATE / f'{k}.json') for k in ('weather', 'astronomy', 'satellite')}
errors = {}
csrf = secrets.token_urlsafe(24)


@lru_cache(maxsize=1)
def local_hosts():
    hostname = socket.gethostname().lower()
    allowed = {'localhost', '127.0.0.1', '::1', hostname, hostname + '.local', hostname + '.home'}
    try:
        allowed.update(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass
    try:
        if os.name == 'posix':
            for value in subprocess.check_output(['hostname', '-I'], text=True, timeout=3).split():
                allowed.add(str(ipaddress.ip_address(value)))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    allowed.update(x.strip().lower() for x in os.environ.get('ASTRO_HOSTS', '').split(',') if x.strip())
    return allowed


def snapshot():
    with lock:
        # The full catalog is downloaded only while Targets is open.
        result = {k: deepcopy({field:v for field,v in value.items() if field != 'targets'})
                  if k == 'astronomy' and value else deepcopy(value) for k,value in data.items()}
        result.update(config=deepcopy(config), equipment=equipment_view(equipment),
                      errors=deepcopy(errors), server_time=datetime.now(UTC).isoformat())
    for key in ('weather', 'satellite', 'astronomy'):
        value = result[key]
        if value and value.get('location_key') != location_key(result['config']):
            result[key] = None
    for key, limit in [('weather', 3600), ('satellite', 5400), ('astronomy', 180)]:
        value = result[key]
        if value:
            stamp = value.get('image_time') if key == 'satellite' else value['updated_at']
            age = (datetime.now(UTC) - datetime.fromisoformat(stamp)).total_seconds()
            value['age_seconds'] = round(age)
            value['stale'] = age > limit or age < -300
    result['forecast'] = forecast_periods(result['weather'], result['astronomy'], time.time())
    result['display'] = display.view()
    result['local_display'] = local_display_request()
    return result


def worker(kind, interval, provider):
    last_key, due, failures = None, 0, 0
    while True:
        with lock:
            current = deepcopy(config)
        key = location_key(current)
        if key != last_key or time.monotonic() >= due:
            try:
                value = provider(current)
                value['location_key'] = key
                with lock:
                    if location_key(config) == key:
                        # Positions are recalculated locally at boot; avoid writing
                        # the large catalog to the microSD every minute.
                        cached = {k:v for k,v in value.items() if k != 'targets'} if kind == 'astronomy' else value
                        save_json(STATE / f'{kind}.json', cached)
                        data[kind] = value
                        errors.pop(kind, None)
                due = time.monotonic() + interval
                failures = 0
            except Exception as exc:
                log.warning('%s refresh failed: %s', kind, exc)
                with lock:
                    errors[kind] = 'Bron tijdelijk niet bereikbaar' if kind != 'astronomy' else 'Astronomische berekening tijdelijk niet beschikbaar'
                # Recover quickly when boot races Wi-Fi; back off during a longer outage.
                due = time.monotonic() + min(60, 5 * 2 ** min(failures, 4))
                failures += 1
            last_key = key
        time.sleep(2)


def start_workers():
    engine = None
    def compute(c):
        nonlocal engine
        if engine is None:
            engine = Astronomy(STATE)
        return engine.calculate(c)
    for kind, interval, provider in [('astronomy', 60, compute), ('weather', 900, weather),
                                     ('satellite', 900, lambda c: satellite(c, STATE))]:
        threading.Thread(target=worker, args=(kind, interval, provider), daemon=True, name=kind).start()


@app.before_request
def guard():
    # Local appliance: no cross-origin API writes and no DNS rebinding to arbitrary hosts.
    host = urlsplit('http://' + request.host).hostname
    if host not in local_hosts():
        abort(400)
    if request.method == 'POST':
        upload = request.endpoint == 'capture_upload'
        if upload:
            request.max_content_length = MAX_BYTES + 128 * 1024
            request.max_form_parts = 8
            request.max_form_memory_size = 256 * 1024
        if (not upload and not request.is_json) or request.headers.get('X-Astro-Token') != csrf:
            abort(403)
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            abort(403)


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    if request.path.startswith('/api/') or request.path == '/':
        response.headers['Cache-Control'] = 'no-store'
    if request.path == '/api/targets':
        response.vary.add('Accept-Encoding')
        if 'gzip' in request.headers.get('Accept-Encoding', '') and response.status_code == 200:
            response.set_data(gzip.compress(response.get_data(), compresslevel=3))
            response.headers['Content-Encoding'] = 'gzip'
    return response


@app.get('/')
def home():
    html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
    html = html.replace('{{APP_VERSION}}', (ROOT / 'VERSION').read_text(encoding='utf-8').strip())
    language = preferences.get('language', 'en-US')
    html = html.replace('<html lang="nl">', '<html lang="' + language + ('" class="kiosk">' if request.args.get('kiosk') == '1' else '">'))
    return Response(html, mimetype='text/html')


@app.get('/api/status')
def status():
    return jsonify(snapshot())


@app.get('/api/health')
def health():
    return jsonify(ok=True)


def brightness_device():
    return next(Path('/sys/class/backlight').glob('*/brightness'), None)


display = DisplayController(STATE, brightness_device())


def local_display_request():
    # Never trust forwarded IPs or a remote browser's ?kiosk=1 flag.
    from flask import has_request_context
    return has_request_context() and request.remote_addr in ('127.0.0.1', '::1')


@app.get('/api/display')
def display_status():
    return jsonify(display=display.view(), local_display=local_display_request(),
                   token=csrf if local_display_request() else None)


@app.post('/api/display/activity')
def display_activity():
    if not local_display_request():
        abort(403)
    return jsonify(display.activity())


@app.get('/api/settings')
def settings():
    return jsonify(config=config, preferences=preferences, equipment=equipment_view(equipment), token=csrf,
                   brightness=display.profile['active'], brightness_available=display.available,
                   display=display.view(), local_display=local_display_request())


@app.post('/api/equipment')
def update_equipment():
    global equipment
    try:
        value = validate_equipment(request.get_json())
        with lock:
            save_json(STATE / 'equipment.json', value)
            equipment = value
        return jsonify(equipment=equipment_view(value))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc) or 'Controleer de telescoopinstellingen.'), 400
    except OSError:
        return jsonify(error='Telescoop kon niet worden opgeslagen.'), 503


def target_view_data(ident):
    with lock:
        current = data.get('astronomy') or {}
        target = deepcopy(next((t for t in current.get('targets', []) if t.get('id') == ident), None))
        scopes = equipment_view(equipment)
    if not target:
        abort(404)
    scope = next((s for s in scopes['scopes'] if s['id'] == request.args.get('scope', scopes['selected'])), None)
    if not scope:
        abort(400)
    try:
        zoom = request.args.get('zoom', 'fov')
        angle = int(request.args.get('angle', '0'))
        geometry = view_geometry(target, scope, zoom, angle)
    except (ValueError, TypeError):
        abort(400)
    return target, scope, geometry, zoom, angle


@app.get('/api/targets/<ident>/view')
def target_view(ident):
    target, scope, geometry, zoom, angle = target_view_data(ident)
    args = urlencode(dict(scope=scope['id'], zoom=zoom, angle=angle))
    return jsonify(target=target, scope=scope, geometry=geometry,
                   recommendation=recommendation(target, scope, request.args.get('window', 'night')),
                   image=None if ident == 'moon' else ('/target-image/' + ident + '?' + args) if ident in CATALOG else '/static/planets/' + ident + '.jpg',
                   survey=ident in CATALOG, survey_name=survey_for(ident)[1] if ident in CATALOG else None,
                   astronomy_time=(data.get('astronomy') or {}).get('updated_at'))


@app.get('/api/targets')
def target_list():
    with lock:
        current = data.get('astronomy') or {}
        if not current.get('targets') or current.get('location_key') != location_key(config):
            return jsonify(error='Waarneemdoelen worden berekend.'), 503
        # Workers replace complete snapshots, so this immutable reference is safe after unlocking.
        scopes = equipment_view(equipment)
    scope_id = request.args.get('scope')
    window = request.args.get('window', 'night')
    if window not in ('night', 'now', 'day'):
        abort(400)
    scope = next((s for s in scopes['scopes'] if s['id'] == (scope_id or scopes['selected'])), None)
    if scope is None:
        abort(400)
    rows = current['targets']
    if scope_id:
        rows = [dict(t, recommendation=recommendation(t, scope, window)) for t in rows]
    return jsonify(updated_at=current['updated_at'], location_key=current['location_key'],
                   scope_id=scope['id'], window=window, targets=rows)


@lru_cache(maxsize=4)
def capture_store(root):
    return CaptureStore(root)


def object_info(ident):
    if ident not in IDS:
        return None
    return dict(id=ident, name=CATALOG[ident]['name'] if ident in CATALOG else
                {'moon':'Maan', 'venus':'Venus', 'jupiter':'Jupiter', 'saturn':'Saturnus'}[ident])


@app.get('/api/objects')
def objects_lookup():
    query = request.args.get('q', '').replace(' ', '').casefold()[:100]
    rows = []
    for ident in IDS:
        obj = object_info(ident)
        haystack = (ident + obj['name'] + CATALOG.get(ident, {}).get('aliases', '')).replace(' ', '').casefold()
        if query and query in haystack:
            rows.append(obj)
        if len(rows) == 25:
            break
    return jsonify(items=rows)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error='De upload is te groot. Maximaal 25 MB per JPG- of PNG-foto.'), 413


@app.get('/api/captures/summary')
def capture_summary():
    return jsonify(capture_store(STATE).summary())


@app.post('/api/favorites')
def favorite_update():
    body = request.get_json()
    if not isinstance(body, dict) or type(body.get('enabled')) is not bool or body.get('object') not in IDS:
        abort(400)
    with lock:
        valid = any(s['id'] == body.get('scope') for s in equipment_view(equipment)['scopes'])
    if not valid:
        abort(400)
    capture_store(STATE).favorite(body['object'], body['scope'], body['enabled'])
    return jsonify(ok=True)


@app.get('/api/targets/<ident>/plan')
def target_plan(ident):
    if ident not in IDS:
        abort(404)
    current = snapshot()
    c = current['config']
    samples = track(str(STATE), ident, c['latitude'], c['longitude'], c['elevation'], int(time.time() // 300), c['timezone'],
                    (current.get('astronomy') or {}).get('night_start'), (current.get('astronomy') or {}).get('night_end'))
    illumination = (current.get('astronomy') or {}).get('moon', {}).get('illumination', 0)
    result = observing_plan(samples, current.get('weather'), illumination, now=time.time())
    result['night_start'] = (current.get('astronomy') or {}).get('night_start')
    result['night_end'] = (current.get('astronomy') or {}).get('night_end')
    return jsonify(result)


@lru_cache(maxsize=4)
def comparisons(state_path):
    return ComparisonManager(state_path, capture_store(state_path))


@app.route('/api/captures/<ident>/comparison', methods=['GET', 'POST'])
def capture_comparison(ident):
    try:
        manager = comparisons(STATE)
        return jsonify(manager.start(ident) if request.method == 'POST' else manager.status(ident))
    except KeyError:
        abort(404)
    except (ValueError, OSError) as exc:
        return jsonify(error=str(exc)), 400


@app.get('/comparison-file/<ident>/<variant>')
def comparison_file(ident, variant):
    if not capture_store(STATE).get(ident, include_trash=True) or variant not in ('own', 'reference'):
        abort(404)
    if comparisons(STATE).status(ident).get('status') != 'ready':
        abort(404)
    return send_file(STATE / 'comparisons' / ident / ('own.png' if variant == 'own' else 'reference.jpg'), max_age=86400)


@lru_cache(maxsize=4)
def backups(state_path):
    return BackupManager(state_path, capture_store(state_path))


@app.route('/api/backup', methods=['GET', 'POST'])
def backup_export():
    manager = backups(STATE)
    if request.method == 'GET':
        return jsonify(manager.status())
    with lock:
        settings_copy = {'config.json': deepcopy(config), 'equipment.json': deepcopy(equipment),
                         'preferences.json': deepcopy(preferences),
                         'brightness.json': read_json(STATE / 'brightness.json', {})}
    return jsonify(manager.start(settings_copy)), 202


@app.get('/backup-file/<ident>')
def backup_file(ident):
    if not re.fullmatch('[a-f0-9]{32}', ident):
        abort(404)
    file = STATE / 'exports' / (ident + '.zip')
    if not file.is_file():
        abort(404)
    return send_file(file, as_attachment=True, download_name='astro-backup-' + ident[:8] + '.zip', max_age=0)


@app.get('/api/captures')
def capture_list():
    try:
        page = int(request.args.get('page', 0))
    except ValueError:
        abort(400)
    return jsonify(capture_store(STATE).listing(request.args.get('object', ''), request.args.get('scope', ''),
                   request.args.get('q', '')[:100], page, request.args.get('trash') == '1'))


@app.post('/api/captures')
def capture_upload():
    target = object_info(request.form.get('object', ''))
    with lock:
        scopes = equipment_view(equipment)['scopes']
    scope = next((s for s in scopes if s['id'] == request.form.get('scope')), None)
    files = request.files.getlist('file')
    if not target or not scope or len(files) != 1:
        return jsonify(error='Kies een bestaand object, een telescoop en één foto per uploadverzoek.'), 400
    try:
        row = capture_store(STATE).add(files[0].stream, files[0].filename, target, scope,
                                      request.form.get('observed_on', ''), request.form.get('note', ''))
        return jsonify(capture=row), 201
    except DuplicateCapture as exc:
        return jsonify(error=str(exc)), 409
    except (ValueError, OSError) as exc:
        return jsonify(error=str(exc) or 'Foto kon niet worden opgeslagen.'), 400


@app.post('/api/captures/<ident>/trash')
def capture_trash(ident):
    body = request.get_json()
    if not isinstance(body, dict) or not isinstance(body.get('trashed'), bool):
        abort(400)
    try:
        capture_store(STATE).trash(ident, body['trashed'])
        return jsonify(ok=True)
    except KeyError:
        abort(404)
    except DuplicateCapture as exc:
        return jsonify(error=str(exc)), 409


@app.get('/capture-file/<ident>/<variant>')
def capture_file(ident, variant):
    store = capture_store(STATE)
    row = store.get(ident, include_trash=True)
    if not row or variant not in ('original', 'preview', 'thumb'):
        abort(404)
    ext = row['extension'] if variant == 'original' else '.jpg'
    return send_file(store.root / ident / (variant + ext),
                     mimetype='image/png' if ext == '.png' else 'image/jpeg', max_age=86400,
                     as_attachment=variant == 'original', download_name=row['filename'] if variant == 'original' else None)


@app.get('/target-image/<ident>')
def target_image(ident):
    if ident not in CATALOG:
        abort(404)
    target, scope, geometry, zoom, angle = target_view_data(ident)
    try:
        return send_file(cutout_path(STATE, ident, geometry['scale']), mimetype='image/jpeg', max_age=86400)
    except Exception as exc:
        log.warning('Target image %s unavailable: %s', ident, exc)
        return jsonify(error='Hemelbeeld tijdelijk niet beschikbaar. Het kader blijft op schaal.'), 503


@app.get('/api/locations')
def locations():
    query = request.args.get('q', '').strip()
    if not 2 <= len(query) <= 80:
        return jsonify(error='Vul een plaatsnaam in.'), 400
    try:
        return jsonify(results=geocode(query, 'nl' if request.args.get('lang') == 'nl-NL' else 'en'))
    except Exception:
        return jsonify(error='Plaatsen zoeken lukt nu niet. Probeer het later opnieuw.'), 503


@app.post('/api/settings')
def update_settings():
    global config, preferences
    body = request.get_json()
    try:
        if not isinstance(body, dict):
            raise ValueError()
        new_display = body.get('display', {})
        if 'brightness' in body:
            legacy_brightness = int(body['brightness'])
            new_display = dict(new_display, active=legacy_brightness)
            if 'idle' not in new_display:
                new_display['idle'] = min(display.profile['idle'], legacy_brightness)
        validate_display(new_display, display.profile, legacy='brightness' in body and 'display' not in body)
        if 'language' in body:
            if body['language'] not in ('en-US', 'nl-NL'):
                raise ValueError()
            new_preferences = dict(preferences, language=body['language'])
        if 'location' in body:
            c = body['location']
            name = str(c['name']).strip()
            lat, lon = float(c['latitude']), float(c['longitude'])
            elevation = float(c.get('elevation', 0))
            zone = str(c['timezone'])
            ZoneInfo(zone)
            if not name or len(name) > 80 or not all(math.isfinite(x) for x in (lat, lon, elevation)) or not -90 <= lat <= 90 or not -180 <= lon <= 180 or not -500 <= elevation <= 9000:
                raise ValueError()
            new_config = dict(name=name, latitude=lat, longitude=lon, elevation=elevation, timezone=zone)
        with lock:
            if 'display' in body or 'brightness' in body:
                display.update(new_display, legacy='brightness' in body and 'display' not in body)
            if 'location' in body:
                save_json(STATE / 'config.json', new_config)
                config = new_config
            if 'language' in body:
                save_json(STATE / 'preferences.json', new_preferences)
                preferences = new_preferences
    except (KeyError, ValueError, TypeError, ZoneInfoNotFoundError):
        return jsonify(error='Controleer de ingevoerde instellingen.'), 400
    except OSError:
        return jsonify(error='Instelling kon niet worden opgeslagen.'), 503
    return jsonify(ok=True)


@app.get('/satellite/<name>')
def image(name):
    return send_from_directory(STATE / 'satellite', name, max_age=3600)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    display.start()
    start_workers()
    serve(app, host=os.environ.get('ASTRO_BIND', '0.0.0.0'), port=int(os.environ.get('ASTRO_PORT', '8080')), threads=6,
          max_request_body_size=MAX_BYTES + 128 * 1024)
