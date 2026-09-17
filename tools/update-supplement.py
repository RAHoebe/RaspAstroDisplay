"""Reproduce the supplemental catalog from bundled, attributed source extracts.

No live telescope catalogs or proprietary app databases are copied. The original
OpenNGC JSON is never rewritten, so existing captures retain their object IDs.
Run with the project environment (Astropy converts CDS FK4/B1950 to ICRS).
"""
import json
import re
from pathlib import Path
import sys
from astropy.coordinates import SkyCoord, FK4
from astropy.time import Time
import astropy.units as u

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from catalog_search import normalize

FIELDS = [('NGC',16),('IC',17),('M',18),('C',19),('B',20),('Sh2-',21),('VdB',22),('RCW',23),('LDN',24),('LBN',25)]
TYPES = {'DN':('nebula','Donkere nevel'),'MoC':('nebula','Donkere nevel'),
         'HII':('nebula','Emissienevel'),'RN':('nebula','Reflectienevel'),
         'PN':('nebula','Planetaire nevel'),'PN?':('nebula','Planetaire nevel'),
         'C+N':('nebula','Sterrenhoop met nevel'),'SNR':('nebula','Supernovarest'),
         'OC':('cluster','Open sterrenhoop'),'GC':('cluster','Bolhoop'),
         'CL':('cluster','Sterassociatie'),'*':('cluster','Ster'),
         '**':('cluster','Dubbelster'),'Gx':('galaxy','Sterrenstelsel'),
         'AGx':('galaxy','Sterrenstelsel'),'IG':('galaxy','Sterrenstelsel'),
         'G':('galaxy','Sterrenstelsel'),'GiG':('galaxy','Sterrenstelsel')}


def build():
    src = ROOT/'catalog'/'sources'
    base = json.loads((ROOT/'catalog/deepsky.json').read_text(encoding='utf-8'))
    known = {normalize(k):k for k in base}
    # Only explicit identifiers are used for merging, never proximity in the sky.
    for ident, obj in base.items():
        for match in re.finditer(r'\b(?:NGC|IC|M|B)\s*0*\d+[A-Za-z]?\b', obj['aliases']):
            known.setdefault(normalize(match.group()), ident)
    names = {}
    for line in (src/'stellarium-names.dat').read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip(): continue
        match = re.search(r'_\("(.*?)"\)', line[20:])
        if match: names.setdefault(normalize(line[:20]), []).append(match[1])
    result = {}
    for line in (src/'stellarium-selected.tsv').read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'): continue
        row = line.split('\t')
        designations = [prefix+str(int(row[i])) for prefix,i in FIELDS if row[i].strip() not in ('','0')]
        keys = [normalize(d) for d in designations]
        existing = {known[k] for k in keys if k in known}
        # Conflicting parent/component identifications must not combine captures.
        if len(existing)>1:
            explicit = [known[k] for k in keys if k in known and known[k] in base]
            ident = explicit[0] if explicit else sorted(existing)[0]
        elif existing: ident = next(iter(existing))
        else:
            preferred = next((d for p in ['LDN','B','Sh2-','LBN','VdB','RCW','M','C'] for d in designations if d.startswith(p)), designations[0])
            ident = normalize(preferred)
        common = list(dict.fromkeys(n for key in keys for n in names.get(key, [])))
        dark = row[5] in ('DN','MoC')
        category, kind = TYPES.get(row[5], ('nebula','Nevel'))
        major, minor = float(row[7]), float(row[8])
        # LDN sizes in Stellarium can be area-derived radii. Do not label them axes.
        unknown_extent = bool(row[24].strip() not in ('','0'))
        major = major if major>0 and not unknown_extent else None
        minor = (minor if minor>0 else major) if major else None
        magnitude = float(row[4])
        obj = dict(name=designations[keys.index(ident)] if ident in keys else designations[0],
                   kind=kind, category=category, ra=float(row[1]), dec=float(row[2]),
                   major=major, minor=minor, pa=None, magnitude=magnitude if magnitude<90 and not dark else None,
                   dark_nebula=dark, designations=designations,
                   aliases=' '.join(designations+common), catalog_source='Stellarium DSO 3.23')
        if common: obj['name'] += ' · '+common[0]
        if ident in result:
            old=result[ident]
            old['aliases'] += ' '+obj['aliases']
            old['designations']=list(dict.fromkeys(old['designations']+designations))
        else: result[ident]=obj
        for key in keys: known.setdefault(key, ident)

    # The original CDS release supplies actual opacity and area, plus entries
    # omitted from Stellarium. Four clouds have no original LDN number.
    for line in (src/'ldn').read_text().splitlines():
        number=line[:4].strip(); seq=int(line[50:54])
        code='LDN'+number if number else 'LDN-seq'+str(seq)
        ident=known.get(normalize(code),normalize(code))
        area=float(line[36:43]); opacity=int(line[44:45]) or None
        if ident not in result:
            ra=15*(int(line[5:7])+float(line[8:12])/60)
            dec=(int(line[16:18])+int(line[19:21])/60)*(-1 if line[15]=='-' else 1)
            coord=SkyCoord(ra*u.deg,dec*u.deg,frame=FK4(equinox=Time('B1950'))).icrs
            result[ident]=dict(name=code,kind='Donkere nevel',category='nebula',ra=coord.ra.deg,dec=coord.dec.deg,
                               major=None,minor=None,pa=None,magnitude=None,aliases=code,designations=[code],
                               catalog_source='Lynds 1962 / CDS VII/7A')
        result[ident].update(opacity=opacity,area_sq_deg=area,dark_nebula=True,magnitude=None)
        if result[ident]['catalog_source'].startswith('Stellarium'):
            result[ident]['catalog_source']='Stellarium DSO 3.23 + CDS VII/7A'
    (ROOT/'catalog/supplement.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    stats=dict(objects_added=len(set(result)-set(base)),existing_objects_enriched=len(set(result)&set(base)),
               designations={p:len({d for v in result.values() for d in v['designations'] if re.fullmatch(re.escape(p)+r'\d+',d)}) for p,_ in FIELDS},
               input_catalog='Stellarium DSO 3.23 standard + CDS VII/7A',
               stellarium_commit='04329a443d6827c2829bf45874f87243226673c2')
    (ROOT/'catalog/supplement-source.json').write_text(json.dumps(stats,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(stats,indent=2))


if __name__=='__main__': build()
