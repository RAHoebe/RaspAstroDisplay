import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app
from catalog_search import normalize, match_rank
from targets import CATALOG, metadata, view_geometry
from ranking import recommendation
from equipment import DEFAULT_SCOPES


class ExtendedCatalogTests(unittest.TestCase):
    def test_existing_ids_and_coordinates_preserved(self):
        original=json.loads((Path(__file__).resolve().parents[1]/'catalog/deepsky.json').read_text(encoding='utf-8'))
        for ident, old in original.items():
            self.assertIn(ident,CATALOG)
            for key in ('name','ra','dec','major','minor'):
                self.assertEqual(CATALOG[ident][key],old[key],(ident,key))

    def test_all_messier_caldwell_and_requested_catalog_families(self):
        codes={normalize(d) for obj in CATALOG.values() for d in obj['designations']}
        self.assertTrue({f'm{i}' for i in range(1,111)}<=codes)
        self.assertTrue({f'c{i}' for i in range(1,110)}<=codes)
        for prefix in ['ldn','lbn','b','sh2','vdb','rcw']:
            self.assertGreater(sum(c.startswith(prefix) for c in codes),100,prefix)
        self.assertGreater(len(CATALOG),15000)

    def test_ldn935_is_distinct_and_not_fake_brightness_or_size(self):
        obj=CATALOG['ldn935']
        self.assertEqual(obj['opacity'],4)
        self.assertEqual(obj['area_sq_deg'],2.25)
        self.assertIsNone(obj['magnitude'])
        self.assertIsNone(obj['major'])
        self.assertIsNone(match_rank('LDN 935','ngc7000',CATALOG['ngc7000']))
        self.assertTrue(314<obj['ra']<315 and 43<obj['dec']<45)
        geometry=view_geometry(metadata('ldn935',1),DEFAULT_SCOPES[0],'target',0)
        self.assertTrue(geometry['size_unknown'])
        self.assertIsNone(geometry['target_pixels'])

    def test_coordinates_finite_and_unmeasured_values_remain_unknown(self):
        for ident,obj in CATALOG.items():
            self.assertTrue(0<=obj['ra']<360 and -90<=obj['dec']<=90,ident)
            if obj.get('dark_nebula'): self.assertIsNone(obj['magnitude'],ident)
            if obj['major'] is not None: self.assertGreater(obj['major'],0,ident)

    def test_search_spelling_variants_and_exact_first(self):
        client=app.app.test_client()
        for query, ident in [('LDN 935','ldn935'),('ldn-0935','ldn935'),('Lynds 935','ldn935'),
                            ('Gulf of Mexico','ldn935'),('Barnard 33','b33'),('Caldwell 20','ngc7000'),
                            ('Sh2-155','c9'),('Sharpless 155','c9'),('Messier 1','m1')]:
            rows=client.get('/api/objects',query_string={'q':query}).json['items']
            self.assertTrue(rows,query)
            self.assertEqual(rows[0]['id'],ident,query)
        self.assertEqual(client.get('/api/objects?q=').json['items'],[])

    def test_global_lookup_and_upload_do_not_require_visibility(self):
        client=app.app.test_client()
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'STATE',Path(folder)), patch.dict(app.data,{'astronomy':None}):
            self.assertEqual(client.get('/api/objects?q=LDN935').json['items'][0]['id'],'ldn935')
            image=io.BytesIO();Image.new('RGB',(80,80),'navy').save(image,'PNG');image.seek(0)
            response=client.post('/api/captures',headers={'X-Astro-Token':app.csrf},data={
                'object':'ldn935','scope':'dwarf-2','file':(image,'ldn935.png')})
            self.assertEqual(response.status_code,201,response.data)
            self.assertEqual(client.get('/api/captures/summary').json['counts']['ldn935']['dwarf-2'],1)

    def test_dark_nebula_opacity_never_becomes_magnitude_score(self):
        obj=dict(CATALOG['ldn935'],best_altitude=65,night_minutes_30=180)
        a=recommendation(obj,DEFAULT_SCOPES[0])
        b=recommendation(dict(obj,magnitude=4,opacity=6),DEFAULT_SCOPES[0])
        self.assertEqual(a['score'],b['score'])
        self.assertIn('donkere nevel · contrast bepalend',a['reasons'])


if __name__=='__main__': unittest.main()
