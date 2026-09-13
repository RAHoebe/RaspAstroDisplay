"""Nominal single-frame telephoto fields; angular dimensions are in degrees."""
from copy import deepcopy
import math
import re


def sensor_field(pixels, pitch_um, focal_mm):
    return math.degrees(2 * math.atan(pixels * pitch_um / 1000 / (2 * focal_mm)))


def diagonal_field(diagonal, width, height):
    half = math.tan(math.radians(diagonal / 2)) / math.hypot(width, height)
    return [math.degrees(2 * math.atan(half * side)) for side in (width, height)]


DEFAULT_SCOPES = [
    dict(id='dwarf-2', name='DWARF II', width=sensor_field(3840, 1.45, 100),
         height=sensor_field(2160, 1.45, 100), builtin=True,
         note='Telecamera · berekend uit 3840 × 2160 pixels, 1,45 µm en 100 mm.'),
    dict(id='seestar-s50-pro', name='Seestar S50 Pro',
         **dict(zip(('width', 'height'), diagonal_field(2.8, 2160, 3840))), builtin=True,
         note='Telecamera · afgeleid van 2,8° diagonaal en 2160 × 3840 pixels.'),
]
DEFAULT_EQUIPMENT = dict(selected='dwarf-2', custom=[])


def equipment_view(saved):
    return dict(selected=saved['selected'], scopes=deepcopy(DEFAULT_SCOPES) + deepcopy(saved['custom']))


def validate_equipment(value):
    if not isinstance(value, dict) or not isinstance(value.get('custom'), list) or len(value['custom']) > 12:
        raise ValueError('Ongeldige telescooplijst (maximaal 12 eigen telescopen).')
    ids = {s['id'] for s in DEFAULT_SCOPES}
    custom = []
    for s in value['custom']:
        if not isinstance(s, dict):
            raise ValueError('Ongeldige telescoop.')
        ident, name = str(s.get('id', '')), str(s.get('name', '')).strip()
        width, height = float(s.get('width', 0)), float(s.get('height', 0))
        if (not re.fullmatch(r'custom-[a-z0-9-]{1,40}', ident) or ident in ids or
                not 1 <= len(name) <= 40 or any(ord(c) < 32 for c in name) or
                not all(math.isfinite(x) and .01 <= x <= 20 for x in (width, height))):
            raise ValueError('Vul een naam en beeldveld van 0,01 tot 20 graden in.')
        ids.add(ident)
        custom.append(dict(id=ident, name=name, width=width, height=height, builtin=False,
                           note='Eigen beeldveld · één opname.'))
    if value.get('selected') not in ids:
        raise ValueError('Kies een bestaande telescoop.')
    return dict(selected=value['selected'], custom=custom)
