"""Shared catalog loading and tolerant designation search (application code: MIT)."""
import json
import re
import unicodedata
from pathlib import Path


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value)).casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    for pattern, replacement in [(r'\blynds\s*(?:dark\s*nebula\s*)?', 'ldn'),
                                 (r'\bbarnard\s*', 'b'), (r'\bcaldwell\s*', 'c'),
                                 (r'\bmessier\s*', 'm'), (r'\bsharpless\s*(?:2\s*[- ]\s*)?', 'sh2')]:
        value = re.sub(pattern, replacement, value)
    value = re.sub(r'[^a-z0-9]', '', value)
    return re.sub(r'^(sh2|ldn|lbn|rcw|vdb|ngc|ic|m|c|b)0+(\d)', r'\1\2', value)


def load_catalog(root=None):
    root = root or Path(__file__).parent / 'catalog'
    base = json.loads((root / 'deepsky.json').read_text(encoding='utf-8'))
    supplement = json.loads((root / 'supplement.json').read_text(encoding='utf-8'))
    for ident, patch in supplement.items():
        if ident in base:
            obj = base[ident]
            obj['aliases'] += ' ' + patch.get('aliases', '')
            obj['designations'] = patch.get('designations', [])
            for key in ('opacity', 'area_sq_deg', 'dark_nebula'):
                if key in patch:
                    obj[key] = patch[key]
            if patch.get('dark_nebula'):
                obj['magnitude'] = None
            obj['catalog_source'] = 'OpenNGC + Stellarium/CDS'
        else:
            base[ident] = patch.copy()
    for ident, obj in base.items():
        obj['designations'] = list(dict.fromkeys([ident, *obj.get('designations', [])]))
        obj.setdefault('catalog_source', 'OpenNGC')
    return base


def match_rank(query, ident, obj):
    """Exact identifiers first, then names/partial text; None means no match."""
    query = normalize(query)
    if not query:
        return None
    if query in {normalize(x) for x in [ident, *obj.get('designations', [])]}:
        return 0
    return 1 if query in normalize(ident + ' ' + obj['name'] + ' ' + obj.get('aliases', '')) else None
