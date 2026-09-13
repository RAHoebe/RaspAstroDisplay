import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from astropy.wcs import WCS
from PIL import Image

import app
from backup import create_archive, restore_archive, sha256
from captures import CaptureStore
from comparison import reproject_rgb, valid_solution, reference_header, ComparisonManager
from deploy import display, desktop, setup as setup_module
from planning import observing_plan


def photo():
    body=io.BytesIO()
    Image.new('RGB',(200,150),'#495').save(body,'PNG')
    body.seek(0)
    return body


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.store=CaptureStore(self.root/'state')
        self.scope=dict(id='dwarf-2',name='DWARF II',width=3.19,height=1.79)
        self.target=dict(id='m31',name='M31')

    def tearDown(self):
        self.temp.cleanup()

    def test_installer_uses_current_user_and_paths_with_spaces(self):
        root=self.root/'checkout with spaces'
        home=self.root/'different home'
        (root/'deploy').mkdir(parents=True)
        (home/'.config').mkdir(parents=True)
        for name in ('astro-panel.service','astro-kiosk.service'):
            (root/'deploy'/name).write_text((Path(__file__).parents[1]/'deploy'/name).read_text())
        for name in ('kiosk.sh','start-kiosk.sh','install-solver.sh'):
            (root/'deploy'/name).write_text('#!/bin/sh\n')
        units=[]
        def run(*args):
            if args[:2]==('sudo','install'):
                units.append(Path(args[-2]).read_text())
        with patch.object(setup_module,'ROOT',root),patch.object(setup_module,'HOME',home), \
             patch.object(setup_module.desktop,'detect',return_value='wayfire'), \
             patch.object(setup_module.getpass,'getuser',return_value='astronomer'), \
             patch.object(setup_module,'install_theme',return_value='AstroInvisible'), \
             patch.object(setup_module,'run',side_effect=run):
            setup_module.install()
        self.assertEqual(len(units),1)
        self.assertIn('User=astronomer',units[0])
        self.assertIn('WorkingDirectory='+setup_module.quoted(root),units[0])
        self.assertNotIn('@@',units[0])
        kiosk=(home/'.config/systemd/user/astro-kiosk.service').read_text()
        self.assertIn('ExecStart='+setup_module.quoted(root/'deploy/kiosk.sh'),kiosk)
        self.assertIn('AstroInvisible',(home/'.config/wayfire.ini').read_text())

    def test_favorites_are_per_scope_and_survive_restart(self):
        self.store.favorite('m31','dwarf-2',True)
        self.store.favorite('m31','dwarf-2',True)
        fresh=CaptureStore(self.root/'state')
        self.assertEqual(fresh.summary()['favorites'],{'dwarf-2':['m31']})
        fresh.favorite('m31','seestar-s50-pro',True)
        fresh.favorite('m31','dwarf-2',False)
        self.assertEqual(fresh.summary()['favorites'],{'seestar-s50-pro':['m31']})

    def test_zip_restores_original_trash_favorites_and_settings(self):
        capture=self.store.add(photo(),'test.png',self.target,self.scope)
        self.store.favorite('m31','dwarf-2',True)
        self.store.trash(capture['id'],True)
        archive=self.root/'export.zip'
        settings={'config.json':dict(name='Example'), 'preferences.json':dict(language='nl-NL')}
        result=create_archive(self.root/'state',self.store,settings,archive)
        self.assertEqual(result['captures'],1)
        restore_archive(archive,self.root/'restored')
        fresh=CaptureStore(self.root/'restored')
        self.assertTrue(fresh.get(capture['id'],True)['trashed'])
        self.assertEqual(fresh.summary()['favorites'],{'dwarf-2':['m31']})
        self.assertEqual(sha256(fresh.root/capture['id']/'original.png'),capture['sha256'])
        self.assertEqual(json.loads((self.root/'restored/preferences.json').read_text()),dict(language='nl-NL'))
        with self.assertRaises(ValueError):
            restore_archive(archive,self.root/'restored')

    def test_restore_rejects_path_escape_and_corrupt_file(self):
        self.store.add(photo(),'test.png',self.target,self.scope)
        archive=self.root/'good.zip'
        create_archive(self.root/'state',self.store,{},archive)
        for attack in ('escape','checksum'):
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(self.root/(attack+'.zip'),'w') as dest:
                manifest=json.loads(source.read('manifest.json'))
                if attack=='escape':
                    manifest['files']['state/../../outside']=dict(bytes=1,sha256='0'*64)
                    dest.writestr('state/../../outside',b'x')
                else:
                    next(iter(manifest['files'].values()))['sha256']='0'*64
                for name in source.namelist():
                    if name!='manifest.json':
                        dest.writestr(name,source.read(name))
                dest.writestr('manifest.json',json.dumps(manifest))
            with self.assertRaises(ValueError):
                restore_archive(self.root/(attack+'.zip'),self.root/(attack+'-restore'))
            self.assertFalse((self.root/(attack+'-restore')).exists())

    def test_backup_refuses_missing_original(self):
        capture=self.store.add(photo(),'test.png',self.target,self.scope)
        (self.store.root/capture['id']/'original.png').unlink()
        with self.assertRaises(OSError):
            create_archive(self.root/'state',self.store,{},self.root/'bad.zip')
        self.assertFalse((self.root/'bad.zip').exists())

    def test_plan_requires_continuity_darkness_and_altitude(self):
        rows=[dict(time=i*600,altitude=45,sun=-20,moon=-5,moon_distance=60,night=True) for i in range(15)]
        plan=observing_plan(rows)
        self.assertEqual(plan['best']['minutes'],120)
        self.assertFalse(plan['best']['weather_available'])
        self.assertNotIn('cloud',rows[0])
        for i,row in enumerate(rows):
            row['altitude']=20 if i%3==0 else 45
        self.assertIsNone(observing_plan(rows)['best'])
        for row in rows:
            row.update(altitude=80,sun=-5)
        self.assertIsNone(observing_plan(rows)['best'])

    def test_plan_weather_is_stale_or_prefers_clear_window(self):
        rows=[dict(time=i*600,altitude=50,sun=-20,moon=-5,moon_distance=60,night=True) for i in range(25)]
        weather=dict(hours=[dict(time=i*600,cloud_cover=100 if i<12 else 0) for i in range(25)])
        plan=observing_plan(rows,weather)
        self.assertGreaterEqual(plan['best']['start'],12*600)
        self.assertEqual(plan['best']['cloud'],0)
        weather['stale']=True
        self.assertIsNone(observing_plan(rows,weather)['best']['cloud'])

    def test_language_api_validates_and_survives_location_change(self):
        with patch.object(app,'STATE',self.root/'state'), patch.object(app,'preferences',dict(language='en-US')):
            client=app.app.test_client()
            self.assertIn(b'lang="en-US"',client.get('/').data)
            headers={'X-Astro-Token':app.csrf}
            self.assertEqual(client.post('/api/settings',json={'language':'nl-NL'},headers=headers).status_code,200)
            self.assertIn(b'lang="nl-NL"',client.get('/').data)
            self.assertEqual(client.post('/api/settings',json={'language':'xx'},headers=headers).status_code,400)
            self.assertEqual(json.loads((self.root/'state/preferences.json').read_text())['language'],'nl-NL')

    def test_favorite_api_rejects_unknown_scope_and_cross_origin(self):
        with patch.object(app,'STATE',self.root/'state'):
            client=app.app.test_client()
            body=dict(object='m31',scope='dwarf-2',enabled=True)
            self.assertEqual(client.post('/api/favorites',json=body).status_code,403)
            self.assertEqual(client.post('/api/favorites',json=body,headers={'X-Astro-Token':app.csrf,'Origin':'http://evil.example'}).status_code,403)
            headers={'X-Astro-Token':app.csrf}
            self.assertEqual(client.post('/api/favorites',json=body,headers=headers).status_code,200)
            body['scope']='missing'
            self.assertEqual(client.post('/api/favorites',json=body,headers=headers).status_code,400)

    def test_comparison_rejects_moon_and_recovers_interrupted_status(self):
        capture=self.store.add(photo(),'moon.png',dict(id='moon',name='Moon'),self.scope)
        manager=ComparisonManager(self.root/'state',self.store)
        with self.assertRaises(ValueError):
            manager.start(capture['id'])
        folder=manager.folder/capture['id'];folder.mkdir()
        (folder/'status.json').write_text(json.dumps(dict(status='solving',sha256=capture['sha256'])))
        self.assertEqual(manager.status(capture['id'])['status'],'interrupted')
        with self.assertRaises(KeyError):
            manager.status('../outside')
        manager.pool.shutdown(wait=True)


class ProjectionTests(unittest.TestCase):
    def test_reprojection_keeps_orientation_rotation_and_parity(self):
        # Analytic gradient in source raster coordinates tests the full pixel/world mapping.
        header=dict(NAXIS=2,NAXIS1=400,NAXIS2=400,CTYPE1='RA---TAN',CTYPE2='DEC--TAN',
                    CRVAL1=359.9,CRVAL2=60,CRPIX1=200.5,CRPIX2=200.5,CDELT1=-.002,CDELT2=.002)
        source_wcs=WCS(header)
        yy,xx=np.mgrid[:400,:400]
        source=np.stack([xx/2,yy/2,np.full_like(xx,80)],axis=-1).astype(np.uint8)
        for mirrored in (False,True):
            angle=np.radians(37)
            matrix=np.array([[-np.cos(angle),np.sin(angle)],[np.sin(angle),np.cos(angle)]])*.002
            if mirrored:
                matrix[:,0]*=-1
            target_header={k:v for k,v in header.items() if not k.startswith('CDELT')}
            target_header.update(NAXIS1=120,NAXIS2=90,CRPIX1=60.5,CRPIX2=45.5,
                                 CD1_1=matrix[0,0],CD1_2=matrix[0,1],CD2_1=matrix[1,0],CD2_2=matrix[1,1])
            target,calibration=valid_solution(target_header,120,90)
            self.assertEqual(calibration['mirrored'],mirrored)
            result=np.array(reproject_rgb(source,source_wcs,target,120,90))
            for x,y in [(10,10),(100,10),(10,80),(100,80),(60,45)]:
                # Equal TAN centers permit direct linear-matrix composition, independent of reprojection implementation.
                tangent=matrix@np.array([x-59.5,89-y-44.5])
                expected=np.array([(199.5+tangent[0]/-.002)/2,(199.5-tangent[1]/.002)/2,80])
                np.testing.assert_allclose(result[y,x],expected,atol=1.6)
            derived=reference_header(target,120,90)
            points=WCS(derived).all_world2pix(target.all_pix2world([[0,0],[119,89]],0),0)
            self.assertTrue(np.all((points>0)&(points<1400)))

    def test_invalid_scale_is_rejected(self):
        with self.assertRaises(ValueError):
            valid_solution(dict(CTYPE1='RA---TAN',CTYPE2='DEC--TAN',CDELT1=10,CDELT2=10),100,100)


class DesktopTests(unittest.TestCase):
    def test_all_rotations_swap_native_dimensions_correctly(self):
        for profile in ('original','touch2'):
            native=tuple(map(int,display.PROFILES[profile]['native'].split('x')))
            for rotation in ('0','90','180','270'):
                chosen=display.selection(profile,rotation=rotation)
                self.assertEqual((chosen['width'],chosen['height']),native[::-1] if rotation in ('90','270') else native)

    def test_labwc_preserves_other_settings_and_maps_touch(self):
        from xml.etree import ElementTree as ET
        text='<labwc_config><keyboard><keybind key="W-e"/></keyboard><libinput><device category="non-touch"><pointerSpeed>0.5</pointerSpeed></device></libinput></labwc_config>'
        after=desktop.labwc_config(text,'DSI-1','Goodix TouchScreen','90',True)
        root=ET.fromstring(after)
        self.assertIsNotNone(root.find('keyboard/keybind'))
        self.assertEqual(root.find('libinput/device').get('category'),'non-touch')
        self.assertEqual(root.find('touch').get('mapToOutput'),'DSI-1')
        self.assertEqual(root.findall('libinput/device')[1].findtext('calibrationMatrix'),'0 -1 1 1 0 0')
        again=ET.fromstring(desktop.labwc_config(after,'DSI-1','Goodix TouchScreen','270',True))
        self.assertEqual(len(again.findall('touch')),1)
        self.assertEqual(len(again.findall('libinput/device')),2)


if __name__=='__main__':
    unittest.main()
