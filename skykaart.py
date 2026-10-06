"""On-demand night charts using the appliance's cached Skyfield ephemeris."""
from datetime import datetime, date, time, timedelta, timezone
from functools import lru_cache
from html import escape
import numpy as np
from zoneinfo import ZoneInfo

from skyfield.api import Star
from astropy.coordinates import SkyCoord, get_constellation
import astropy.units as u
from planning import engine, engine_lock, observing_plan
from targets import CATALOG
from skykaart_stars import star_catalog

UTC = timezone.utc


@lru_cache(maxsize=32)
def night_chart(root, ident, evening, latitude, longitude, elevation, zone):
    """Pin the evening date; never advance a saved chart at sunrise."""
    tz = ZoneInfo(zone)
    noon = datetime.combine(date.fromisoformat(evening), time(12), tz)
    end_noon = noon + timedelta(days=1)
    with engine_lock:
        astro = engine(root)
        events = astro.events(noon.astimezone(UTC).isoformat(), end_noon.astimezone(UTC).isoformat(),
                              latitude, longitude, elevation)
        start = datetime.fromisoformat(events['sunset']) if events['sunset'] else noon.astimezone(UTC)
        end = datetime.fromisoformat(events['sunrise']) if events['sunrise'] else end_noon.astimezone(UTC)
        grid_start = (int(start.timestamp())//600+1)*600
        dates = [start] + [datetime.fromtimestamp(stamp, UTC) for stamp in range(grid_start, int(end.timestamp()), 600)] + [end]
        times = astro.ts.from_datetimes(dates)
        _, observer = astro.observer(latitude, longitude, elevation)
        at = observer.at(times)
        body = Star(ra_hours=CATALOG[ident]['ra']/15, dec_degrees=CATALOG[ident]['dec']) if ident in CATALOG else astro.eph[
            {'moon': 'moon', 'venus': 'venus', 'jupiter': 'jupiter barycenter', 'saturn': 'saturn barycenter'}[ident]]
        target = at.observe(body).apparent()
        moon = at.observe(astro.eph['moon']).apparent()
        alt, az, _ = target.altaz()
        moon_alt, moon_az, _ = moon.altaz()
        sun_alt = at.observe(astro.eph['sun']).apparent().altaz()[0].degrees
        separation = target.separation_from(moon).degrees
        # The backdrop is a real sky at the best high, dark reference sample.
        sun_limit = -18 if ident in CATALOG else -12
        rows = [dict(time=d.timestamp(), altitude=float(a), azimuth=float(z), moon=float(m),
                     moon_azimuth=float(mz), sun=float(s), moon_distance=float(sep), night=bool(s < sun_limit))
                for d, a, z, m, mz, s, sep in zip(dates, alt.degrees, az.degrees, moon_alt.degrees, moon_az.degrees, sun_alt, separation)]
        best = observing_plan(rows)['best']
        if best:
            ref = min(range(len(dates)), key=lambda i: abs(rows[i]['time']-(best['start']+best['end'])/2))
        else:
            visible = [i for i,r in enumerate(rows) if r['altitude'] >= 0 and r['sun'] < -12]
            ref = max(visible or range(len(dates)), key=lambda i: alt.degrees[i])
        catalog = star_catalog()
        star = Star(ra_hours=[s['ra']/15 for s in catalog], dec_degrees=[s['dec'] for s in catalog],
                    ra_mas_per_year=np.array([s['pmra'] for s in catalog]), dec_mas_per_year=np.array([s['pmdec'] for s in catalog]),
                    epoch=2448349.0625)
        apparent = observer.at(times[ref]).observe(star).apparent()
        sa, sz, _ = apparent.altaz()
        sr, sd, _ = apparent.radec()
        tr, td, _ = target.radec()
        stars = [dict(hip=s['hip'], magnitude=s['magnitude'], name=s['name'], altitude=float(a),
                      azimuth=float(z), ra=float(r), dec=float(d))
                 for s,a,z,r,d in zip(catalog,sa.degrees,sz.degrees,sr.radians,sd.radians)]
    return dict(samples=rows, events=events, start=start.isoformat(), end=end.isoformat(),
                best=best, sun_limit=sun_limit, stars=stars, reference_time=dates[ref].timestamp(),
                reference_index=ref, ra=float(tr.radians[ref]), dec=float(td.radians[ref]), ident=ident,
                constellation=get_constellation(SkyCoord(ra=tr.radians[ref]*u.rad, dec=td.radians[ref]*u.rad)))


from skykaart_poster import chart_svg

def chart_page(chart, name, config, evening, download_url, ident):
    e = escape
    tz = ZoneInfo(config['timezone'])
    local = lambda value: datetime.fromisoformat(value).astimezone(tz).strftime('%d-%m-%Y %H:%M %Z')
    best = chart['best']
    stamp = lambda value: datetime.fromtimestamp(value, tz).strftime('%H:%M %Z')
    advice = (f'{stamp(best["start"])} – {stamp(best["end"])} (hoogte ≥30°, zon onder {chart["sun_limit"]}°).'
              if best else f'Geen aaneengesloten venster van minstens 30 minuten boven 30° met de zon onder {chart["sun_limit"]}°.')
    dark = ' · '.join(local(d['start'])+' – '+local(d['end']) for d in chart['events']['dark']) or 'Geen astronomische duisternis deze nacht.'
    polar = '<p>Geen zonsondergang of zonsopkomst: de kaart gebruikt lokale middag tot middag.</p>' if not chart['events']['sunset'] or not chart['events']['sunrise'] else ''
    return f'''<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Skykaart — {e(name)} — {evening}</title>
<style>body{{margin:0;background:radial-gradient(ellipse at 20% 0%,#172e47 0%,#080e18 55%);color:#e0eafa;font:16px/1.5 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:36px 24px}}h1{{font-size:clamp(32px,5vw,58px);letter-spacing:-.04em;line-height:1.1;margin:12px 0 20px;max-width:900px}}p{{margin:8px 0 16px}}svg{{display:block;width:100%;height:auto;box-shadow:0 20px 60px #0004;border:1px solid #26384d;border-radius:18px}}a{{color:#86d8ff}}.eyebrow{{font-size:12px;letter-spacing:.22em;color:#86d8ff}}.sub{{color:#a9bcd1;font-size:14px;max-width:750px}}.actions{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}.actions a{{border:1px solid #3a506a;border-radius:30px;padding:10px 18px;text-decoration:none;font-size:13px}}.actions a:last-child{{background:#b2e5fc;color:#0b1220;border-color:#b2e5fc}}.details{{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:24px;margin-top:24px}}.card{{border:1px solid #26384d;background:#0e1929;border-radius:16px;padding:22px;margin-bottom:16px}}.card strong{{color:#86d8ff;font-size:12px;letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:10px}}.reference{{margin:0;overflow:hidden;border-radius:16px;border:1px solid #26384d;background:#0e1929;align-self:start}}.reference img{{width:100%;aspect-ratio:5/3;object-fit:contain;background:#030610}}figcaption{{padding:15px;font-size:10px;color:#86d8ff;letter-spacing:.06em}}figcaption span{{color:#a9bcd1;letter-spacing:0}}.note{{color:#8fa3bc;font-size:12px;max-width:820px}}@media(max-width:700px){{main{{padding:24px 12px}}.details{{grid-template-columns:1fr}}.reference{{max-width:400px}}}}@media print{{body{{background:white;color:black}}.actions{{display:none}}main{{padding:0}}h1{{font-size:28px}}.card{{color:#e0eafa}}}}</style><script src="/static/skykaart.js" defer></script></head><body><main>
<nav class="actions"><a href="/">← RaspAstroDisplay</a><a href="{e(download_url, quote=True)}">Download Skykaart ↓</a></nav>
{chart_svg(chart, name, config['timezone'], config['name'])}
<section class="details" style="display:block"><div style="display:flex;gap:16px;flex-wrap:wrap"><div class="card" style="flex:1;min-width:240px"><strong>Geometrisch waarneemvenster</strong>{e(advice)}</div><div class="card" style="flex:1;min-width:240px"><strong>Astronomisch donker</strong>{e(dark)}{polar}</div></div></section>
<p class="note">{e(config['name'])} · {config['latitude']:.5f}°, {config['longitude']:.5f}° · {e(config['timezone'])}. Lokale tijden; de nacht blijft vastgelegd bij later openen. Sterren getoond op het aangegeven referentietijdstip, gouden pad op de afzonderlijke tijden. Posities zonder atmosferische refractie. Het venster houdt geen rekening met wolken of obstakels. Landschap illustratief. Sterren: ESA Hipparcos via CDS; sterrenbeeldlijnen: Stellarium (CC BY-SA); berekeningen: Skyfield / JPL DE421.</p>
</main></body></html>'''
