"""Bounded local solver attempts. Never uploads photographs."""
import os
from pathlib import Path
import shutil
import signal
import subprocess

import numpy as np
from astropy.io import fits


def astrometry_paths():
    root = Path(os.environ.get('ASTRO_ASTROMETRY_HOME', Path.home() / '.local/share/astrometry'))
    return shutil.which('solve-field'), root


def astrometry_available():
    binary, root = astrometry_paths()
    return bool(binary and (root / 'astrometry.cfg').is_file() and any(root.glob('index-*.fits')))


def run_attempt(command, folder, name, timeout):
    # A file prevents verbose solver output accumulating in server memory.
    with (folder / (name + '.log')).open('wb') as log:
        try:
            child = subprocess.Popen(command, cwd=folder, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=os.name == 'posix')
            return child.wait(timeout=timeout) == 0
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(child.pid, signal.SIGKILL)
            else:
                child.kill()
            child.wait()
            return False


def matched_stars(path, width, height):
    """Astrometry correspondence coordinates are one-based FITS pixels."""
    with fits.open(path) as hdus:
        table = hdus[1].data
        points = np.column_stack([table[k] for k in ('field_x', 'field_y', 'index_x', 'index_y')])
    good = np.isfinite(points).all(axis=1)
    good &= (points[:, 0] >= 1) & (points[:, 0] <= width) & (points[:, 1] >= 1) & (points[:, 1] <= height)
    points = points[good]
    residual = np.hypot(points[:, 0]-points[:, 2], points[:, 1]-points[:, 3])
    # Require many spatially distributed matches, not merely a plausible scale.
    inliers = points[residual <= 5]
    if len(inliers) < 12 or np.ptp(inliers[:, 0]) < width*.25 or np.ptp(inliers[:, 1]) < height*.25:
        raise ValueError('Too few reliable star matches. Try a less processed photograph.')
    return dict(matched_stars=len(inliers), median_residual_pixels=float(np.median(residual[residual <= 5])),
                stars=[[float(x-1), float(height-y), float(ix-1), float(height-iy)] for x,y,ix,iy in inliers[:150]])


def solve(photo, picture, folder, obj, native_height, astap, database, progress):
    width, height = photo.size
    solution = folder / 'solution.wcs'
    # Use the original-resolution preview, then a differently binned extraction.
    if astap.is_file() and any(database.glob('d50*.1476')):
        for number, (fov, binning, stars) in enumerate(((native_height or 0, 0, 500), (0, 2 if height >= 1920 else 1, 250)), 1):
            progress('solving', stage=f'ASTAP {number}/2')
            prefix = folder / f'astap-{number}'
            candidate = prefix.with_suffix('.wcs')
            candidate.unlink(missing_ok=True)
            command = [str(astap), '-f', str(picture), '-d', str(database), '-D', 'd50',
                       '-ra', str(obj['ra']/15), '-spd', str(obj['dec']+90), '-r', '15',
                       '-z', str(binning), '-s', str(stars), '-fov', str(fov), '-wcs', '-o', str(prefix)]
            if run_attempt(command, folder, f'astap-{number}', 100) and candidate.exists():
                shutil.copyfile(candidate, solution)
                return 'ASTAP local', {}
    if astrometry_available():
        binary, root = astrometry_paths()
        # Explicit bottom-up FITS input makes WCS orientation identical for both solvers.
        source = folder / 'solve-input.fits'
        fits.writeto(source, np.flipud(np.asarray(photo.convert('L'))), overwrite=True)
        for name, position in [('near', ['--ra', str(obj['ra']), '--dec', str(obj['dec']), '--radius', '15']),
                               ('blind', [])]:
            progress('solving', stage='Astrometry.net: nearby field' if position else 'Astrometry.net: whole sky')
            prefix = 'astrometry-' + name
            candidate = folder / (prefix + '.wcs')
            candidate.unlink(missing_ok=True)
            command = [binary, str(source), '--backend-config', str(root/'astrometry.cfg'), '--dir', str(folder),
                       '--out', prefix, '--overwrite', '--no-plots', '--no-verify', '--new-fits', 'none',
                       '--scale-units', 'degwidth', '--scale-low', '.2', '--scale-high', '12',
                       '--downsample', '2' if height >= 1920 else '1', '--cpulimit', '180',
                       '--objs', '300', '--tweak-order', '2', *position]
            if run_attempt(command, folder, prefix, 220) and candidate.exists():
                try:
                    quality = matched_stars(folder/(prefix+'.corr'), width, height)
                except (ValueError, OSError, KeyError):
                    continue
                shutil.copyfile(candidate, solution)
                source.unlink(missing_ok=True)
                return 'Astrometry.net local', quality
        source.unlink(missing_ok=True)
    raise ValueError('No reliable star match. Try the original, less processed photograph or a wider crop.')
