"""Rebuild the bundled OpenNGC selection; network is needed only for this tool."""
from collections import Counter
import csv
import io
import json
from pathlib import Path
import re
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
TYPES = {
    'G': ('galaxy', 'Sterrenstelsel'), 'GPair': ('galaxy', 'Stelselduo'),
    'GTrpl': ('galaxy', 'Stelseltrio'), 'GGroup': ('galaxy', 'Stelselgroep'),
    'OCl': ('cluster', 'Open sterrenhoop'), 'GCl': ('cluster', 'Bolhoop'),
    '*Ass': ('cluster', 'Sterassociatie'),
    'Cl+N': ('nebula', 'Sterrenhoop met nevel'), 'PN': ('nebula', 'Planetaire nevel'),
    'HII': ('nebula', 'Emissienevel'), 'EmN': ('nebula', 'Emissienevel'),
    'DrkN': ('nebula', 'Donkere nevel'), 'Neb': ('nebula', 'Nevel'),
    'RfN': ('nebula', 'Reflectienevel'), 'SNR': ('nebula', 'Supernovarest'),
}
DUTCH = {'m31':'Andromeda', 'm42':'Orionnevel', 'm45':'Plejaden', 'm13':'Hercules',
         'm57':'Ringnevel', 'm27':'Halternevel', 'm1':'Krabnevel', 'm8':'Lagunenevel',
         'm16':'Adelaarsnevel', 'm17':'Omeganevel', 'm20':'Trifidnevel',
         'ngc7000':'Noord-Amerikanevel', 'ic5070':'Pelikaannevel', 'ngc1499':'Californiënevel',
         'ngc6960':'Sluiernevel west', 'ngc6992':'Sluiernevel oost', 'ngc6888':'Sikkelnevel',
         'ic1805':'Hartnevel', 'ic1848':'Zielnevel', 'b33':'Paardenkopnevel',
         'ngc281':'Pacmannevel', 'ngc7635':'Bubbelnevel', 'ngc2237':'Rosettenevel'}


def coord(value):
    sign=-1 if value.startswith('-') else 1
    a,b,c=map(float,value.lstrip('+-').split(':'))
    return sign*(a+b/60+c/3600)


def compact(value):
    return re.sub(r'([A-Za-z]+)0+(\d)', r'\1\2', value).lower()


def main():
    commit=json.load(urlopen('https://api.github.com/repos/mattiaverga/OpenNGC/commits/master',timeout=20))['sha']
    rows=[]
    for filename in ('NGC.csv','addendum.csv'):
        url=f'https://raw.githubusercontent.com/mattiaverga/OpenNGC/{commit}/database_files/{filename}'
        rows.extend(csv.DictReader(io.StringIO(urlopen(url,timeout=30).read().decode()),delimiter=';'))
    result={}
    for r in rows:
        if r['Type'] not in TYPES or not r['RA'] or not r['Dec']:
            continue
        ident='m'+str(int(r['M'])) if r['M'].isdigit() else compact(r['Name'])
        if ident in result:
            ident=compact(r['Name'])
        code=ident.upper() if ident.startswith(('m','ngc','ic')) else r['Name']
        label=DUTCH.get(ident) or r['Common names'].split(',')[0].strip()
        major=float(r['MajAx']) if r['MajAx'] else None
        minor=float(r['MinAx']) if r['MinAx'] else major
        if major is not None and major<=0:major=minor=None
        category,kind=TYPES[r['Type']]
        result[ident]=dict(name=code+(' · '+label if label else ''),kind=kind,category=category,
            ra=round(coord(r['RA'])*15,8),dec=round(coord(r['Dec']),8),major=major,minor=minor,
            pa=float(r['PosAng']) if r['PosAng'] else None,
            magnitude=float(r['V-Mag']) if r['V-Mag'] else None,
            aliases=' '.join([code,r['Name'],r['Common names'],r['Identifiers']]))
    dest=ROOT/'catalog';dest.mkdir(exist_ok=True)
    (dest/'deepsky.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (dest/'source.json').write_text(json.dumps(dict(project='OpenNGC',author='Mattia Verga',
        commit=commit,license='CC-BY-SA-4.0',url='https://github.com/mattiaverga/OpenNGC',
        objects=len(result),categories=dict(Counter(v['category'] for v in result.values()))),indent=2),encoding='utf-8')
    print((dest/'source.json').read_text())


if __name__=='__main__':main()
