"""Catalog sizes and calibrated TAN cutouts. See SOURCES.md for provenance."""
import hashlib
import json
import math
from pathlib import Path
import threading
from urllib.parse import urlencode

from providers import fetch
from catalog_search import load_catalog

# OpenNGC major axes in arcminutes. Missing minor axes use the catalog diameter.
# M45 is Mel022 in the OpenNGC addendum (150 arcmin catalog diameter).
CATALOG = load_catalog()
IDS = ['moon', 'venus', 'jupiter', 'saturn', *CATALOG]
RADII = dict(moon=1737.4, venus=6051.8, mars=3396.19, jupiter=71492., saturn=60268.)
WIDTH, HEIGHT = 900, 540
image_lock = threading.Lock()
SURVEYS = {'m57': ('CDS/P/PanSTARRS/DR1/color', 'Pan-STARRS DR1')}


def survey_for(ident):
    return SURVEYS.get(ident, ('CDS/P/DSS2/color', 'DSS2'))


def angular_diameter(radius, distance):
    return math.degrees(2 * math.asin(radius / distance))


def metadata(ident, distance_km):
    if ident in CATALOG:
        obj = CATALOG[ident]
        return dict(id=ident, **obj, size_note='Catalogusmaat ≈ · zwakke uitlopers kunnen verder reiken'
                    if obj['major'] else 'Afmeting onbekend · geen groottepercentage beschikbaar')
    diameter = angular_diameter(RADII[ident], distance_km) * 60
    return dict(id=ident, major=diameter, minor=diameter, pa=None,
                size_note='Actuele schijfdiameter' + (' · zonder ringen' if ident == 'saturn' else ''))


def plane_span(angle):
    return math.degrees(2 * math.tan(math.radians(angle / 2)))


def view_geometry(target, scope, zoom, angle):
    """Use the same projected degrees/pixel for the WCS and the ROI corners."""
    if zoom not in ('target', 'fov') or angle not in range(0, 180, 15):
        raise ValueError('Ongeldige weergave.')
    rw, rh = plane_span(scope['width']), plane_span(scope['height'])
    a = math.radians(angle)
    # Positive position angle turns the frame's vertical axis towards east (left).
    corners = [(x*math.cos(a)+y*math.sin(a), -x*math.sin(a)+y*math.cos(a))
               for x, y in [(-rw/2,-rh/2),(rw/2,-rh/2),(rw/2,rh/2),(-rw/2,rh/2)]]
    if zoom == 'fov':
        scale = max((max(x for x,y in corners)-min(x for x,y in corners))/WIDTH,
                    (max(y for x,y in corners)-min(y for x,y in corners))/HEIGHT) * 1.15
    else:
        # Unknown catalog size: use a labelled 30 arcminute context, never invent a size.
        major = plane_span((target['major'] or 30)/60) * (2.5 if target['id'] == 'saturn' else 1)
        minor = plane_span((target['minor'] or target['major'] or 30)/60)
        if target.get('pa') is not None:
            pa = math.radians(target['pa'])
            bx = math.hypot(major*math.sin(pa), minor*math.cos(pa))
            by = math.hypot(major*math.cos(pa), minor*math.sin(pa))
        else:
            bx = by = major  # Unknown position angle: include the whole diameter.
        scale = max(bx/WIDTH, by/HEIGHT) * 1.15
    # Stable cache keys, while retaining subarcsecond scale for small targets.
    scale = round(scale, 12)
    points = [[WIDTH/2+x/scale, HEIGHT/2+y/scale] for x,y in corners]
    return dict(width=WIDTH, height=HEIGHT, scale=scale, roi=points,
                field_width=math.degrees(2*math.atan(math.radians(scale*WIDTH/2))),
                target_pixels=plane_span(target['major']/60)/scale if target['major'] else None,
                size_unknown=not target['major'],
                roi_outside=any(x<0 or y<0 or x>WIDTH or y>HEIGHT for x,y in points))


def cutout_path(cache, ident, scale):
    """Fetch only fixed catalog coordinates from CDS; persist bounded local cache."""
    obj = CATALOG[ident]
    wcs = dict(NAXIS=2, NAXIS1=WIDTH, NAXIS2=HEIGHT,
               CTYPE1='RA---TAN', CTYPE2='DEC--TAN', CRVAL1=obj['ra'], CRVAL2=obj['dec'],
               CRPIX1=(WIDTH+1)/2, CRPIX2=(HEIGHT+1)/2, CDELT1=-scale, CDELT2=scale)
    params = dict(hips=survey_for(ident)[0], wcs=json.dumps(wcs, separators=(',', ':')), format='jpg')
    query = urlencode(params)
    folder = Path(cache) / 'targets'
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (ident + '-' + hashlib.sha256(query.encode()).hexdigest()[:20] + '.jpg')
    if dest.exists():
        return dest
    # Only one upstream request; other requests return a retryable response.
    if not image_lock.acquire(blocking=False):
        raise BlockingIOError('Beeldbron is bezig. Probeer opnieuw.')
    try:
        if dest.exists():
            return dest
        body = fetch('https://alasky.cds.unistra.fr/hips-image-services/hips2fits?' + query, timeout=25)
        if not body.startswith(b'\xff\xd8') or len(body) < 1000:
            raise ValueError('Geen geldig hemelbeeld ontvangen.')
        temp = dest.with_suffix('.tmp')
        temp.write_bytes(body)
        temp.replace(dest)
        for old in sorted(folder.glob('*.jpg'), key=lambda p:p.stat().st_mtime, reverse=True)[120:]:
            old.unlink(missing_ok=True)
        return dest
    finally:
        image_lock.release()
