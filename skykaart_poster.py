"""Accurate, reproducible poster artwork; landscape is purely decorative."""
import base64
from datetime import datetime
from functools import lru_cache
from html import escape
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from astro import direction
from targets import CATALOG, survey_for
from skykaart_stars import constellations


@lru_cache(maxsize=1)
def background():
    data = (Path(__file__).resolve().parent / 'static' / 'skykaart-landscape.png').read_bytes()
    return 'data:image/png;base64,'+base64.b64encode(data).decode('ascii')


def chart_svg(chart, name, zone, location='', reference=None):
    e = escape
    tz = ZoneInfo(zone)
    stamp = lambda t: datetime.fromtimestamp(t, tz).strftime('%H:%M')
    rows = chart['samples']
    start, end = rows[0]['time'], rows[-1]['time']
    day1 = datetime.fromtimestamp(start,tz).strftime('%d %B %Y')
    day2 = datetime.fromtimestamp(end,tz).strftime('%d %B %Y')
    # Choose a continuous horizon window containing the visible part of the path.
    visible = [r for r in rows if r['altitude'] >= 0 and r['sun'] < -6]
    unwrapped = []
    for row in visible:
        angle = row['azimuth']
        if unwrapped:
            angle = unwrapped[-1]+(angle-unwrapped[-1]+180)%360-180
        unwrapped.append(angle)
    center = (min(unwrapped)+max(unwrapped))/2 if unwrapped else rows[chart['reference_index']]['azimuth']
    span = min(360,max(180,(max(unwrapped)-min(unwrapped)+40) if unwrapped else 180))
    def xy(alt, az):
        delta = (az-center+180)%360-180
        return 495+delta/span*910, 725-alt/90*540
    def on_map(alt, az):
        x,y=xy(alt,az)
        return alt>=0 and 44<x<946 and 174<y<725
    stars = chart['stars']
    byhip = {s['hip']:s for s in stars}
    ref = chart['reference_index']
    target = rows[ref]
    markers=[r for r in rows if r['sun'] < -12 and on_map(r['altitude'],r['azimuth']) and datetime.fromtimestamp(r['time'],tz).minute==0 and datetime.fromtimestamp(r['time'],tz).hour%2==1]
    if len(markers)>5:markers=markers[::math.ceil(len(markers)/5)]
    if not markers and visible:markers=[visible[len(visible)//2]]
    occupied=[]
    for row in markers:
        x,y=xy(row['altitude'],row['azimuth']);tx=x+16 if x<790 else x-110
        occupied.append((tx-3,y-22,tx+135,y+19))
    if on_map(target['moon'],target['moon_azimuth']):
        x,y=xy(target['moon'],target['moon_azimuth']);occupied.append((x+10,y-13,x+65,y+12))
    tx,ty=xy(target['altitude'],target['azimuth'])
    target_label_x=tx+24 if tx<650 else tx-290
    if on_map(target['altitude'],target['azimuth']):
        occupied.append((target_label_x,ty+22,target_label_x+270,ty+46))
    def label(x,y,text,size,color,anchor='start'):
        width=len(text)*size*.54
        left=x-width/2 if anchor=='middle' else x
        box=(left,y-size,left+width,y+4)
        if box[0]<45 or box[2]>945 or box[1]<180 or box[3]>720:return ''
        if any(not(box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3]) for b in occupied):return ''
        occupied.append(box)
        return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{e(text)}</text>'
    out = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1400 1050" role="img" aria-labelledby="title desc">',
           f'<title id="title">Skykaart — {e(name)} — {e(day1)} / {e(day2)}</title>',
           '<desc id="desc">Nachtelijke horizonkaart met berekende sterren en sterrenbeelden, doelpad, ingezoomde omgeving en observatiegegevens. Het landschap is illustratief.</desc>',
           '<defs><filter id="glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="3"/></filter><linearGradient id="footer" x2="0" y2="1"><stop stop-color="#030d19" stop-opacity=".4"/><stop offset="1" stop-color="#020913"/></linearGradient><clipPath id="map"><rect x="40" y="175" width="910" height="550"/></clipPath><clipPath id="zoom"><rect x="1000" y="205" width="340" height="360"/></clipPath></defs>',
           '<rect width="1400" height="1050" fill="#030a14"/>',
           f'<image x="0" y="0" width="1400" height="900" preserveAspectRatio="none" href="{background()}"/>',
           '<rect x="0" y="0" width="1400" height="155" fill="#020913" opacity=".35"/>',
           '<g font-family="Segoe UI,DejaVu Sans,sans-serif" fill="#e8f3ff">',
           '<text x="42" y="36" font-size="12" letter-spacing="3" fill="#97b8d5">RASP ASTRO DISPLAY  /  SKYKAART</text>',
           f'<text x="40" y="99" font-size="{min(55,850/max(1,len(name)) * 1.8):.1f}" font-weight="700">{e(name[:65])}</text>',
           '<text x="995" y="95" font-size="39" fill="#ffe390" font-weight="600">deze nacht</text>',
           f'<text x="42" y="137" font-size="24" fill="#d3e6ff">{e(location[:45])} · {datetime.fromtimestamp(start,tz):%d-%m-%Y} / {datetime.fromtimestamp(end,tz):%d-%m-%Y}</text>',
           f'<text x="44" y="165" font-size="12" fill="#8faac8">Sterrenhemel om {stamp(chart["reference_time"])} {e(datetime.fromtimestamp(chart["reference_time"],tz).tzname())} · horizonpanorama {span:.0f}°</text>',
           '<g clip-path="url(#map)">']
    # Real background stars and their native constellation stick figures.
    for constellation in constellations():
        for line in constellation['lines']:
            for a,b in zip(line,line[1:]):
                if not isinstance(a,int) or not isinstance(b,int) or a not in byhip or b not in byhip:
                    continue
                s,t=byhip[a],byhip[b]
                if on_map(s['altitude'],s['azimuth']) and on_map(t['altitude'],t['azimuth']):
                    x,y=xy(s['altitude'],s['azimuth']);xx,yy=xy(t['altitude'],t['azimuth'])
                    if abs(x-xx)<300:
                        out.append(f'<path d="M{x:.1f} {y:.1f}L{xx:.1f} {yy:.1f}" stroke="#8bb2ed" stroke-width="1" opacity=".65"/>')
        nodes={hip for line in constellation['lines'] for hip in line if isinstance(hip,int)}
        points=[xy(byhip[h]['altitude'],byhip[h]['azimuth']) for h in nodes if h in byhip and on_map(byhip[h]['altitude'],byhip[h]['azimuth'])]
        if len(points)>=3:
            x=sum(p[0] for p in points)/len(points);y=sum(p[1] for p in points)/len(points)
            if max(p[0] for p in points)-min(p[0] for p in points)<500:
                out.append(label(x,y-17,constellation['common_name'].get('native',constellation['iau']),19,'#a6c5fb','middle'))
    for star in sorted(stars,key=lambda s:s['magnitude']):
        if not on_map(star['altitude'],star['azimuth']):
            continue
        x,y=xy(star['altitude'],star['azimuth'])
        radius=max(.45,3.5-star['magnitude']*.47)
        if star['magnitude']<2:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius*2:.1f}" fill="#b5d7ff" opacity=".6" filter="url(#glow)"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="#dcecff" opacity="{max(.35,1-star["magnitude"]*.075):.2f}"/>')
        if star['name'] and star['magnitude']<2.4:
            out.append(label(x+9,y+5,star['name'],12,'#d1dff2'))
    # Break paths whenever they go below the horizon or around the panorama seam.
    path=[];last=None
    for row in rows:
        if row['sun'] < -6 and on_map(row['altitude'],row['azimuth']):
            x,y=xy(row['altitude'],row['azimuth'])
            path.append(('L' if last is not None and abs(last-x)<450 else 'M')+f'{x:.1f} {y:.1f}')
            last=x
        else:
            last=None
    out.append(f'<path d="{" ".join(path)}" stroke="#ffe08b" stroke-width="2.2" fill="none" stroke-dasharray="9 7"/>')
    for row in markers:
        x,y=xy(row['altitude'],row['azimuth'])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="#ffd96e" opacity=".7" filter="url(#glow)"/><circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="#ffdd78" stroke="#fff4c9" stroke-width="2"/>')
        tx=x+16 if x<790 else x-110
        out.append(f'<text x="{tx:.1f}" y="{y-5:.1f}" font-size="15" font-weight="600" fill="#ffe390">{stamp(row["time"])}</text><text x="{tx:.1f}" y="{y+13:.1f}" font-size="13">{row["altitude"]:.0f}° hoog · {direction(row["azimuth"])}</text>')
    if on_map(target['altitude'],target['azimuth']):
        x,y=xy(target['altitude'],target['azimuth'])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" stroke="#ffe390" fill="none"/><path d="M{x-25:.1f} {y:.1f}h50M{x:.1f} {y-25:.1f}v50" stroke="#ffe390"/>')
        out.append(f'<text x="{target_label_x:.1f}" y="{y+42:.1f}" font-size="20" fill="#ffe390" font-weight="600">{e(name[:27])}</text>')
    if on_map(target['moon'],target['moon_azimuth']):
        x,y=xy(target['moon'],target['moon_azimuth'])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#d9e3f1"/><text x="{x+14:.1f}" y="{y+5:.1f}" font-size="13">Maan</text>')
    out.append('</g>')
    if chart['ident'] in CATALOG:
        meta=CATALOG[chart['ident']]
        out.append('<rect x="43" y="184" width="214" height="73" fill="#020913" opacity=".65"/>')
        out.append(f'<text x="52" y="204" font-size="13">{e(str(meta.get("kind","")))}</text>')
        if meta.get('magnitude') is not None:
            out.append(f'<text x="52" y="225" font-size="12" fill="#bdd0e9">Magnitude: {meta["magnitude"]:.1f}</text>')
        if meta.get('major'):
            out.append(f'<text x="52" y="246" font-size="12" fill="#bdd0e9">Afmeting ≈ {meta["major"]:.1f}′ × {(meta.get("minor") or meta["major"]):.1f}′</text>')
    # Horizon directions correspond to the same azimuth projection as the stars.
    out.append('<path d="M40 745H950" stroke="#a1b8d2" opacity=".6"/>')
    for az,label in [(0,'N'),(45,'NO'),(90,'O'),(135,'ZO'),(180,'Z'),(225,'ZW'),(270,'W'),(315,'NW')]:
        x,_=xy(0,az)
        if 40<x<950:
            out.append(f'<path d="M{x:.1f} 739v16" stroke="#b9cce0"/><text x="{x:.1f}" y="779" text-anchor="middle" font-size="20" font-weight="600">{label}</text>')
    if not visible:
        message='Dit doel blijft deze nacht onder de horizon.' if all(r['altitude']<0 for r in rows) else 'Geen donkere hemel met dit doel boven de horizon.'
        out.append(f'<text x="80" y="650" font-size="21" fill="#ffe390">{message}</text>')
    # True tangent-plane close-up, north up and east left.
    out += ['<rect x="982" y="169" width="378" height="468" fill="#020a16" fill-opacity=".76" stroke="#7899ca" stroke-width="1.5"/>',
            f'<text x="1002" y="199" font-size="20" font-weight="600">Rond {e(chart["constellation"])}</text>',
            '<g clip-path="url(#zoom)">']
    ra,dec=chart['ra'],chart['dec']
    def tangent(s):
        delta=s['ra']-ra
        denominator=math.sin(dec)*math.sin(s['dec'])+math.cos(dec)*math.cos(s['dec'])*math.cos(delta)
        if denominator<=0:return None
        u=math.cos(s['dec'])*math.sin(delta)/denominator
        v=(math.cos(dec)*math.sin(s['dec'])-math.sin(dec)*math.cos(s['dec'])*math.cos(delta))/denominator
        return 1170-math.degrees(u)*12,382-math.degrees(v)*12
    def inside(p):return p is not None and 1000<p[0]<1340 and 210<p[1]<565
    for constellation in constellations():
        for line in constellation['lines']:
            for a,b in zip(line,line[1:]):
                if not isinstance(a,int) or not isinstance(b,int) or a not in byhip or b not in byhip:continue
                p,q=tangent(byhip[a]),tangent(byhip[b])
                if p is not None and q is not None and (inside(p) or inside(q)):
                    out.append(f'<path d="M{p[0]:.1f} {p[1]:.1f}L{q[0]:.1f} {q[1]:.1f}" stroke="#779fd7" stroke-width="1"/>')
    for star in stars:
        p=tangent(star)
        if not inside(p):continue
        x,y=p;radius=max(.7,3.6-star['magnitude']*.42)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="#dcecff"/>')
        if star['name']:
            out.append(f'<text x="{x+8:.1f}" y="{y+4:.1f}" font-size="11">{e(star["name"])}</text>')
    out += ['<circle cx="1170" cy="382" r="12" stroke="#ffe390" fill="none"/><path d="M1148 382h44M1170 360v44" stroke="#ffe390"/>',
            f'<text x="1188" y="373" fill="#ffe390" font-size="17">{e(chart["ident"].upper())}</text></g>',
            '<text x="1005" y="611" font-size="12" fill="#aabedb">N ↑ · O ←</text><path d="M1260 592h24m-24-5v10m24-10v10" stroke="#d4e6ff"/><text x="1272" y="615" text-anchor="middle" font-size="12">2°</text>']
    ident=chart['ident']
    if ident in CATALOG and reference is not False:
        url=reference or f'/skykaart/{ident}/reference'
        out += ['<rect x="1155" y="452" width="185" height="139" fill="#030a15" stroke="#7899ca"/>',
                '<text x="1170" y="516" font-size="11" fill="#aabedb">Hemelbeeld laden…</text>',
                f'<image id="skykaart-survey" x="1157" y="454" width="181" height="118" preserveAspectRatio="xMidYMid meet" href="{e(url,quote=True)}"/>',
                f'<text x="1247" y="586" text-anchor="middle" font-size="10">{e(survey_for(ident)[1])} / CDS</text>']
    # Footer panels mirror the visual structure of the supplied reference.
    out += ['<rect x="0" y="815" width="1400" height="235" fill="url(#footer)"/>',
            '<path d="M42 823H1358M655 850v158M1000 850v158" stroke="#526d91" stroke-width="1"/>',
            '<text x="44" y="858" font-size="21" font-weight="600">Voor jouw observatienacht</text>']
    best=chart['best']
    advice=f'{stamp(best["start"])} – {stamp(best["end"])} {e(datetime.fromtimestamp(best["start"],tz).tzname())}' if best else 'Geen venster ≥30 min boven 30°'
    dark=' / '.join(stamp(datetime.fromisoformat(d['start']).timestamp())+'–'+stamp(datetime.fromisoformat(d['end']).timestamp()) for d in chart['events']['dark']) or 'Geen astronomische duisternis'
    out += [f'<text x="44" y="896" font-size="16"><tspan fill="#ffe390">◷</tspan>  Geometrisch beste tijd: {advice}</text>',
            f'<text x="44" y="928" font-size="16">☾  Astronomisch donker: {e(dark)}</text>',
            f'<text x="44" y="960" font-size="16">⌖  Zoekobject: {e(ident.upper())}</text>',
            f'<text x="44" y="992" font-size="12" fill="#8faac8">Hoogte ≥30° · zon onder {chart["sun_limit"]}° · controleer wolken en obstakels</text>',
            '<text x="680" y="858" font-size="21" font-weight="600">Hoogte door de nacht</text>']
    gx=lambda t:690+(t-start)/(end-start)*280
    gy=lambda a:977-max(-20,min(90,a))/110*100
    for level in (0,30,60):
        out.append(f'<path d="M690 {gy(level):.1f}H970" stroke="#50657f" stroke-dasharray="3 4"/><text x="684" y="{gy(level)+4:.1f}" font-size="10" text-anchor="end">{level}°</text>')
    for key,color in [('altitude','#ffe390'),('moon','#acc4e2')]:
        path=' '.join(('M' if i==0 else 'L')+f'{gx(r["time"]):.1f} {gy(r[key]):.1f}' for i,r in enumerate(rows))
        out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>')
    out += [f'<text x="690" y="1000" font-size="11">{stamp(start)}</text><text x="970" y="1000" text-anchor="end" font-size="11">{stamp(end)}</text>',
            '<text x="1025" y="858" font-size="21" font-weight="600">Beste resultaten</text>',
            '<text x="1025" y="896" font-size="16">• Kies een donkere locatie</text><text x="1025" y="928" font-size="16">• Laat het doel hoger komen</text><text x="1025" y="960" font-size="16">• Gebruik stacking</text>',
            '<text x="42" y="1030" font-size="10" letter-spacing="1.5" fill="#7f9cbd">HIPPARCOS / STELLARIUM / JPL DE421 · BEREKENDE POSITIES · LANDSCHAP ILLUSTRATIEF</text>',
            '<text x="1350" y="1030" text-anchor="end" font-size="11" fill="#ffe390">Heldere hemel!</text></g></svg>']
    return ''.join(out)
