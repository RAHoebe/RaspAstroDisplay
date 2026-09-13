import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
import app
from captures import CaptureStore, DuplicateCapture
from equipment import DEFAULT_SCOPES
from ranking import recommendation


def photograph(fmt='PNG', size=(400, 300), color='navy', **args):
    out=io.BytesIO();Image.new('RGB',size,color).save(out,format=fmt,**args);return out.getvalue()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name);self.store=CaptureStore(self.root)
        self.target=dict(id='m31',name='M31 · Andromeda');self.scope=DEFAULT_SCOPES[0]

    def add(self,body=None,filename='photo.png',scope=None):
        return self.store.add(io.BytesIO(body or photograph()),filename,self.target,scope or self.scope,'2026-09-13','Testopname')

    def test_original_previews_counters_and_restart(self):
        body=photograph();c=self.add(body)
        self.assertEqual((self.store.root/c['id']/'original.png').read_bytes(),body)
        for variant in ['thumb','preview']:
            with Image.open(self.store.root/c['id']/(variant+'.jpg')) as im:
                im.verify()
        second=self.add(scope=DEFAULT_SCOPES[1])
        store=CaptureStore(self.root)
        self.assertEqual(store.summary()['counts']['m31'],{'dwarf-2':1,'seestar-s50-pro':1})
        self.assertEqual(store.listing(scope_id=second['scope_id'])['total'],1)
        self.assertEqual(store.listing(query='Andromeda')['total'],2)
        self.assertEqual(store.get(c['id'])['observed_on'],'2026-09-13')

    def test_duplicates_and_recoverable_removal(self):
        c=self.add()
        with self.assertRaises(DuplicateCapture):self.add()
        self.store.trash(c['id'],True)
        self.assertEqual(self.store.summary()['counts'],{})
        self.assertTrue((self.store.root/c['id']/'original.png').exists())
        self.assertEqual(self.store.listing(trash=True)['total'],1)
        self.store.trash(c['id'],False)
        self.assertEqual(self.store.summary()['counts']['m31']['dwarf-2'],1)

    def test_exif_orientation_and_invalid_images_do_not_count(self):
        exif=Image.Exif();exif[274]=6
        c=self.add(photograph('JPEG',(400,200),exif=exif),filename='rotated.jpg')
        self.assertEqual((c['width'],c['height']),(200,400))
        for body,name in [(b'not a photo','fake.jpg'),(photograph(),'wrong.jpg'),(photograph('WEBP'),'x.webp'),(photograph('GIF'),'x.png')]:
            with self.assertRaises((ValueError,OSError)):self.add(body,name)
        with patch('captures.MAX_PIXELS',1):
            with self.assertRaises(ValueError):self.add(photograph(color='red'))
        self.assertEqual(self.store.listing()['total'],1)
        self.assertFalse(list(self.store.root.glob('.pending-*')))

    def test_disk_reserve_and_bad_dates(self):
        with patch('captures.shutil.disk_usage') as usage:
            usage.return_value.free=1024
            with self.assertRaises(OSError):self.add()
        with self.assertRaises(ValueError):self.store.add(io.BytesIO(photograph()),'x.png',self.target,self.scope,'not a date')
        self.assertEqual(self.store.listing()['total'],0)

    def test_upload_api_guards_limits_and_historical_telescope(self):
        client=app.app.test_client();headers={'X-Astro-Token':app.csrf}
        def upload(body=None,name='x.png',**extra):
            return client.post('/api/captures',data=dict(object='m31',scope='dwarf-2',file=(io.BytesIO(body or photograph()),name)),**extra)
        with patch.object(app,'STATE',self.root):
            self.assertEqual(upload().status_code,403)
            self.assertEqual(upload(headers={**headers,'Origin':'https://evil.example'}).status_code,403)
            # A realistic >64k image exercises multipart parser limits.
            noise=io.BytesIO();Image.effect_noise((500,500),100).convert('RGB').save(noise,'PNG')
            self.assertGreater(len(noise.getvalue()),65536)
            response=upload(noise.getvalue(),headers=headers)
            self.assertEqual(response.status_code,201,response.data)
            c=response.json['capture']
            self.assertEqual(client.get('/api/captures/summary').json['counts']['m31']['dwarf-2'],1)
            with client.get('/capture-file/'+c['id']+'/original') as original:
                self.assertEqual(original.data,noise.getvalue())
            self.assertEqual(upload(noise.getvalue(),headers=headers).status_code,409)
            self.assertEqual(upload(photograph('WEBP'),'x.webp',headers=headers).status_code,400)
            self.assertEqual(client.get('/capture-file/bad/original').status_code,404)
            self.assertEqual(client.post('/api/captures/'+c['id']+'/trash',json={'trashed':True},headers=headers).status_code,200)
            self.assertEqual(client.get('/api/captures').json['total'],0)
            self.assertEqual(client.get('/api/captures?trash=1').json['total'],1)
        historic=dict(self.scope,id='custom-old',name='Oude telescoop')
        self.add(scope=historic)
        self.assertEqual(self.store.listing(scope_id='custom-old')['total'],1)


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.target=dict(category='nebula',kind='Emissienevel',major=30,minor=20,magnitude=7,altitude=60,best_altitude=70,night_minutes_30=180)
        self.scope=DEFAULT_SCOPES[1]
    def score(self,**changes):return recommendation(dict(self.target,**changes),self.scope)['score']
    def test_usable_target_beats_tiny_low_or_very_faint_target(self):
        good=self.score()
        for changes in [dict(major=.3,minor=.3,magnitude=5),dict(best_altitude=18,night_minutes_30=0),dict(magnitude=15),dict(major=500,minor=300)]:
            self.assertGreater(good,self.score(**changes),changes)
    def test_missing_values_explicit_and_scope_changes_ranking(self):
        unknown=recommendation(dict(self.target,magnitude=None),self.scope)
        self.assertIn('helderheid onbekend',unknown['reasons']);self.assertTrue(unknown['limited'])
        self.assertGreater(unknown['score'],0)
        self.assertNotEqual(self.score(),recommendation(self.target,DEFAULT_SCOPES[0])['score'])
    def test_now_uses_current_altitude_and_no_night_is_not_good(self):
        target=dict(self.target,altitude=-10)
        self.assertLess(recommendation(target,self.scope,'now')['score'],recommendation(target,self.scope,'night')['score'])
        self.assertLess(self.score(best_altitude=None,night_minutes_30=0),self.score())


if __name__=='__main__':unittest.main()
