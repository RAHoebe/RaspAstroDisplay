"""Local ASTAP plate solving and WCS reprojection of a remote survey cutout.

Only sky coordinates/WCS go to CDS. Original user photographs never leave the Pi.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import urlencode

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from PIL import Image, ImageOps

from providers import fetch, read_json, save_json
from targets import CATALOG, survey_for


def solver_paths():
    home = Path(os.environ.get('ASTRO_SOLVER_HOME', Path.home() / '.local/share/astap'))
    executable = os.environ.get('ASTRO_SOLVER') or str(home / 'astap_cli')
    return Path(executable), home


def valid_solution(header, width, height):
    wcs = WCS(header).celestial
    if not wcs.has_celestial:
        raise ValueError('No celestial coordinates in the solution.')
    matrix = wcs.pixel_scale_matrix
    scale = math.sqrt(abs(float(np.linalg.det(matrix)))) * 3600
    if not np.isfinite(matrix).all() or not .05 < scale < 300:
        raise ValueError('The returned pixel scale is not plausible.')
    pts = wcs.all_pix2world([[width/2, height/2], [0, height/2], [width-1, height/2],
                           [width/2, 0], [width/2, height-1]], 0)
    if not np.isfinite(pts).all():
        raise ValueError('The returned coordinates are invalid.')
    sky = SkyCoord(pts[:, 0], pts[:, 1], unit='deg')
    return wcs, dict(ra=float(pts[0,0]), dec=float(pts[0,1]), pixel_scale=scale,
                     width_degrees=float(sky[1].separation(sky[2]).deg),
                     height_degrees=float(sky[3].separation(sky[4]).deg),
                     rotation=float(math.degrees(math.atan2(matrix[0,1], matrix[1,1]))),
                     mirrored=bool(np.linalg.det(matrix) > 0))


def reference_header(wcs, width, height, size=1400):
    # Oversize a north-up TAN cutout around the solved footprint, including its edges.
    x = np.linspace(0, width-1, 9)
    y = np.linspace(0, height-1, 9)
    pixels = np.vstack([np.column_stack([x, np.zeros(9)]), np.column_stack([x, np.full(9,height-1)]),
                        np.column_stack([np.zeros(9), y]), np.column_stack([np.full(9,width-1), y])])
    world = wcs.all_pix2world(pixels, 0)
    center = wcs.all_pix2world([[width/2, height/2]], 0)[0]
    header = dict(NAXIS=2, NAXIS1=size, NAXIS2=size, CTYPE1='RA---TAN', CTYPE2='DEC--TAN',
                  CRVAL1=float(center[0]), CRVAL2=float(center[1]), CRPIX1=(size+1)/2, CRPIX2=(size+1)/2,
                  CDELT1=-1., CDELT2=1.)
    offsets = WCS(header).all_world2pix(world, 0) - (size-1)/2
    scale = float(np.max(np.abs(offsets))) * 2 / (size-1) * 1.05
    if not np.isfinite(scale) or not 0 < scale * size < 30:
        raise ValueError('The solved field is too large for this comparison.')
    header.update(CDELT1=-scale, CDELT2=scale)
    return header


def reproject_rgb(source, source_wcs, target_wcs, width, height):
    """FITS WCS uses bottom-up y; image arrays/JPEG use top-down y. Bilinear sampling."""
    source = np.asarray(source, dtype=np.uint8)
    output = np.zeros((height, width, 3), dtype=np.uint8)
    valid_pixels = 0
    for row in range(0, height, 96):
        yy, xx = np.mgrid[row:min(height,row+96), :width]
        ra, dec = target_wcs.all_pix2world(xx, height-1-yy, 0)
        sx, sy = source_wcs.all_world2pix(ra, dec, 0)
        sy = source.shape[0]-1-sy
        valid = np.isfinite(sx) & np.isfinite(sy) & (sx >= 0) & (sy >= 0) & (sx < source.shape[1]-1) & (sy < source.shape[0]-1)
        sx, sy = np.where(valid,sx,0), np.where(valid,sy,0)
        ix, iy = sx.astype(int), sy.astype(int)
        dx, dy = (sx-ix)[...,None], (sy-iy)[...,None]
        sample = ((1-dx)*(1-dy)*source[iy,ix] + dx*(1-dy)*source[iy,ix+1] +
                  (1-dx)*dy*source[iy+1,ix] + dx*dy*source[iy+1,ix+1])
        sample[~valid] = 0
        output[row:row+len(yy)] = np.clip(sample,0,255).astype(np.uint8)
        valid_pixels += int(valid.sum())
    if valid_pixels < width*height*.98:
        raise ValueError('The reference does not cover the solved photograph.')
    return Image.fromarray(output)


class ComparisonManager:
    def __init__(self, state, store):
        self.state, self.store = Path(state), store
        self.folder = self.state / 'comparisons'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='plate-solver')
        self.lock = threading.Lock()
        self.active = set()

    def available(self):
        executable, database = solver_paths()
        return executable.is_file() and any(database.glob('d50*.1476'))

    def status(self, ident):
        row = self.store.get(ident, include_trash=True)
        if not row:
            raise KeyError(ident)
        status = read_json(self.folder / ident / 'status.json', dict(status='new'))
        if status.get('status') in ('queued','solving','reference') and ident not in self.active:
            status = dict(status, status='interrupted', error='Comparison interrupted. Please try again.')
        if status.get('sha256') and status['sha256'] != row['sha256']:
            status = dict(status='new')
        return dict(status, available=self.available(), supported=row['object_id'] in CATALOG)

    def start(self, ident):
        row = self.store.get(ident)
        if not row:
            raise KeyError(ident)
        if row['object_id'] not in CATALOG:
            raise ValueError('Comparison needs a deep-sky photograph with recognizable stars.')
        if not self.available():
            raise ValueError('Install the local ASTAP solver and D50 star database first.')
        with self.lock:
            previous = self.status(ident)
            if ident in self.active or previous.get('status') == 'ready':
                return previous
            if len(self.active) >= 3:
                raise ValueError('The comparison queue is full. Please try again later.')
            if shutil.disk_usage(self.folder).free < 2*1024**3 + 100*1024**2:
                raise OSError('Not enough free space for comparison.')
            folder = self.folder / ident
            folder.mkdir(exist_ok=True)
            self.active.add(ident)
            save_json(folder / 'status.json', dict(status='queued', sha256=row['sha256']))
            self.pool.submit(self.work, row, folder)
        return dict(status='queued', available=True, supported=True)

    def work(self, row, folder):
        started = time.monotonic()
        stamp = dict(sha256=row['sha256'], solver='ASTAP local')
        def status(phase, **more):
            save_json(folder / 'status.json', dict(stamp, status=phase, **more))
        try:
            executable, database = solver_paths()
            solution = folder / 'solution.wcs'
            picture = folder / 'own.png'
            if not solution.exists():
                status('solving')
                with Image.open(self.store.root / row['id'] / ('original'+row['extension'])) as original:
                    photo = ImageOps.exif_transpose(original)
                    if photo.mode in ('I','I;16','I;16B'):
                        photo = photo.point(lambda x:x/256).convert('L')
                    photo = photo.convert('RGB')
                    photo.thumbnail((1600,1600), Image.Resampling.LANCZOS)
                    photo.save(picture)
                obj = CATALOG[row['object_id']]
                base = [str(executable), '-f', str(picture), '-d', str(database), '-D', 'd50',
                        '-ra', str(obj['ra']/15), '-spd', str(obj['dec']+90), '-r', '15', '-z', '0',
                        '-wcs', '-o', str(folder / 'solution')]
                # First use the telescope's native height; then search scale for crops/rotation/mosaics.
                for fov in (row['fov_height'] or 0, 0):
                    result = subprocess.run(base+['-fov',str(fov)], cwd=folder, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, timeout=150, check=False)
                    if result.returncode == 0 and solution.exists():
                        break
                    solution.unlink(missing_ok=True)
                if not solution.exists():
                    raise ValueError('No star match found. Use a photograph with more visible stars and less cropping.')
            with Image.open(picture) as photo:
                width, height = photo.size
            try:
                header = fits.Header.fromfile(solution, endcard=True, padding=False)
                wcs, calibration = valid_solution(header, width, height)
            except Exception:
                solution.unlink(missing_ok=True)
                raise
            status('reference', calibration=calibration)
            source_header = reference_header(wcs, width, height)
            survey, label = survey_for(row['object_id'])
            query = urlencode(dict(hips=survey, wcs=json.dumps(source_header), format='jpg'))
            body = fetch('https://alasky.cds.unistra.fr/hips-image-services/hips2fits?' + query,
                         timeout=60, max_bytes=12*1024*1024)
            with Image.open(io.BytesIO(body)) as image:
                if image.size != (1400,1400):
                    raise ValueError('Unexpected reference image dimensions.')
                reference = reproject_rgb(image.convert('RGB'), WCS(source_header), wcs, width, height)
            reference.save(folder / 'reference.pending.jpg', quality=92)
            (folder / 'reference.pending.jpg').replace(folder / 'reference.jpg')
            status('ready', calibration=calibration, survey=label, width=width, height=height,
                   elapsed_seconds=round(time.monotonic()-started,1),
                   completed_at=datetime.now(timezone.utc).isoformat(),
                   own='/comparison-file/'+row['id']+'/own', reference='/comparison-file/'+row['id']+'/reference')
        except subprocess.TimeoutExpired:
            status('failed', error='Local solving timed out. Please try an image with clearer stars.')
        except Exception as exc:
            status('failed', error=str(exc) or 'Comparison failed. Please try again.')
        finally:
            with self.lock:
                self.active.discard(row['id'])
