"""Bundled bright Hipparcos stars and Stellarium western constellation lines."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'catalog' / 'skykaart'
NAMES = {24608:'Capella',21421:'Aldebaran',27989:'Betelgeuse',24436:'Rigel',37826:'Pollux',36850:'Castor',26451:'Zeta Tauri',32349:'Sirius',37279:'Procyon',91262:'Vega',102098:'Deneb',97649:'Altair',11767:'Polaris',69673:'Arcturus',65474:'Spica',80763:'Antares',49669:'Regulus',113963:'Markab',677:'Alpheratz',15863:'Mirfak',9884:'Hamal',25336:'Bellatrix',26727:'Alnitak',26311:'Alnilam',25930:'Mintaka',54061:'Dubhe',59774:'Megrez',62956:'Alioth',67301:'Alkaid',71683:'Alpha Centauri',30438:'Canopus',7588:'Achernar',60718:'Acrux',68702:'Hadar',22449:'Elnath',25428:'Alhena',109268:'Alnair',86228:'Sargas'}


@lru_cache(maxsize=1)
def star_catalog():
    rows = []
    for line in (ROOT / 'hipparcos.tsv').read_text(encoding='utf-8').splitlines():
        fields = line.split('\t')
        if len(fields) != 6 or not fields[0].strip().isdigit():
            continue
        try:
            hip, ra, dec, mag = int(fields[0]), float(fields[1]), float(fields[2]), float(fields[3])
            rows.append(dict(hip=hip, ra=ra, dec=dec, magnitude=mag,
                             pmra=float(fields[4].strip() or 0), pmdec=float(fields[5].strip() or 0), name=NAMES.get(hip,'')))
        except ValueError:
            continue
    if len(rows) < 1000:
        raise ValueError('Incomplete bright star catalog')
    return rows


@lru_cache(maxsize=1)
def constellations():
    return json.loads((ROOT / 'western.json').read_text(encoding='utf-8'))['constellations']
