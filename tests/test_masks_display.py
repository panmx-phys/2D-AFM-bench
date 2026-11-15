"""Synthetic full-resolution selection, persistence and display-only checks."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from afm_workbench.mcp import handle
from afm_workbench.service import Workbench


class MaskDisplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workbench = Workbench(self.root)
        self.workbench._db.execute("INSERT INTO sessions(id,name,source_path,imported_at,synthetic) VALUES('s','test','synthetic://mask-tests','2026-11-10',1)")
        self.data = np.arange(80, dtype=float).reshape(8, 10)
        self.id = self.insert(self.data, 'mask.tiff')
        self.workbench._db.commit()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.workbench.close()
        self.tmp.cleanup()

    def insert(self, data, name):
        return self.workbench._insert_scan('s', name, hashlib.sha256(data.tobytes()).hexdigest(), data,
            {'height':data.shape[0], 'width':data.shape[1], 'height_um':8., 'width_um':10.,
             'channel':'Z Height', 'value_unit':'nm', 'direction':'Forward', 'acquisition':'001'})

    def unpack(self, result):
        return np.unpackbits(np.frombuffer(base64.b64decode(result['data_base64']), dtype=np.uint8),
                             count=result['height']*result['width']).reshape(result['height'], result['width'])

    def rectangle(self):
        return self.workbench.edit_mask(self.id, 'rectangle', roi={'x0':.2,'x1':.6,'y0':.25,'y1':.75})

    def test_rectangle_brush_erase_and_pixel_centre_geometry(self):
        mask = self.rectangle()
        expected = np.zeros((8,10), dtype=np.uint8)
        expected[2:6,2:6] = 1
        np.testing.assert_array_equal(self.unpack(mask), expected)
        self.assertEqual(mask['count'],16)
        stroke = self.workbench.edit_mask(self.id,'brush',points=[[.05,.0625],[.95,.0625]],radius=.5,mode='replace')
        expected[:] = 0
        expected[0,:] = 1
        np.testing.assert_array_equal(self.unpack(stroke),expected)
        erased = self.workbench.edit_mask(self.id,'brush',points=[[.45,.0625]],radius=.5,mode='remove')
        expected[0,4] = 0
        np.testing.assert_array_equal(self.unpack(erased),expected)
        oversized = self.workbench.edit_mask(self.id,'brush',points=[[.5,.5]],radius=512,mode='replace')
        self.assertEqual(oversized['count'],self.data.size)

    def test_mask_persistence_undo_redo_and_branch(self):
        first = self.rectangle()
        second = self.workbench.edit_mask(self.id,'invert')
        self.assertEqual(second['count'],64)
        self.assertEqual(self.workbench.edit_mask(self.id,'undo')['data_base64'],first['data_base64'])
        self.assertEqual(self.workbench.edit_mask(self.id,'redo')['data_base64'],second['data_base64'])
        self.workbench.edit_mask(self.id,'undo')
        self.workbench.edit_mask(self.id,'clear')
        self.workbench.update_mask(self.id,masking='include',visible=False)
        self.workbench.close()
        self.workbench=Workbench(self.root)
        restored=self.workbench.scan(self.id)['mask']
        self.assertFalse(restored['can_redo'])
        self.assertTrue(restored['can_undo'])
        self.assertFalse(restored['visible'])
        self.assertEqual(restored['masking'],'include')
        self.assertEqual(restored['count'],0)
        self.assertEqual(self.workbench.edit_mask(self.id,'undo')['data_base64'],first['data_base64'])
        self.assertEqual(self.workbench._db.execute('SELECT count(*) FROM mask_revisions').fetchone()[0],3)

    def test_saved_recipe_and_measurements_snapshot_mask(self):
        self.rectangle()
        op={'type':'zero_mean','method':'gwyddion','use_saved_mask':True}
        preview=self.workbench.preview(self.id,[op])
        self.assertNotIn('use_saved_mask',preview['operations'][0])
        self.assertEqual(preview['operations'][0]['masking'],'exclude')
        self.assertEqual(op,{'type':'zero_mean','method':'gwyddion','use_saved_mask':True})
        self.workbench.edit_mask(self.id,'invert')
        saved=self.workbench.process(self.id,preview['operations'])
        np.testing.assert_array_equal(preview['data'],saved['data'])
        area=self.workbench.measure_area(self.id,use_saved_mask=True)
        self.assertEqual(area['statistics']['count'],16)
        profile=self.workbench.profile(self.id,[0,.5],[1,.5],samples=10,interpolation='nearest',use_saved_mask=True)
        self.assertEqual(profile['masking'],'exclude')
        self.assertEqual(sum(v is not None for v in profile['values']),4)
        mask_snapshot=area['mask']
        self.workbench.edit_mask(self.id,'clear')
        exported=json.loads(self.workbench.export_scan(self.id)['content'])
        np.testing.assert_array_equal(exported['measurements'][0]['mask'],mask_snapshot)
        np.testing.assert_array_equal(self.workbench.scan(self.id,raw=True)['data'],self.data)
        np.testing.assert_array_equal(self.workbench.scan(self.id)['data'],saved['data'])

    def test_masked_step_native_region_statistics_and_empty_reference(self):
        self.workbench.edit_mask(self.id,'threshold',lower=20,upper=59)
        self.workbench.update_mask(self.id,masking='include')
        a={'x0':0,'y0':0,'x1':.5,'y1':1}
        b={'x0':.5,'y0':0,'x1':1,'y1':1}
        measured=self.workbench.step_height(self.id,a,b,use_saved_mask=True)
        self.assertEqual(measured['region_a']['count'],20)
        self.assertEqual(measured['region_b']['count'],20)
        self.assertEqual(measured['difference'],5.)
        self.workbench.edit_mask(self.id,'clear')
        detail=self.workbench.scan(self.id)
        self.assertIsNone(detail['masked_statistics'])
        self.assertIn('no valid pixel',detail['masked_statistics_error'])
        with self.assertRaisesRegex(ValueError,'no valid pixel'):
            self.workbench.measure_area(self.id,use_saved_mask=True)
        with self.assertRaisesRegex(ValueError,'no valid pixel'):
            self.workbench.preview(self.id,[{'type':'zero_mean','method':'gwyddion','use_saved_mask':True}])
        self.workbench.update_mask(self.id,masking='ignore')
        self.assertEqual(self.workbench.measure_area(self.id,use_saved_mask=True)['statistics']['count'],80)

    def test_threshold_and_range_use_full_resolution_not_display_samples(self):
        data=np.zeros((520,530))
        data[0,0]=100.
        large=self.insert(data,'large.tiff')
        self.workbench._db.commit()
        detail=self.workbench.scan(large)
        self.assertEqual(detail['data_width'],512)
        mask=self.workbench.edit_mask(large,'threshold',lower=50)
        self.assertEqual(mask['count'],1)
        limits=self.workbench.display_range(large)
        self.assertEqual(limits['maximum'],100.)
        self.assertEqual(sum(limits['histogram']['counts']),data.size)
        self.assertEqual(self.workbench.display_range(large,mode='percentile')['data_maximum'],100.)

    def test_manual_range_persistence_exports_thumbnails_and_no_numerical_mutation(self):
        before=self.workbench.scan(self.id)
        normal=self.workbench.thumbnail(self.id)
        settings={'palette':'gray','mode':'manual','clip_percent':0,'minimum':20.,'maximum':40.}
        self.assertEqual(self.workbench.set_display(self.id,settings),settings)
        self.assertNotEqual(self.workbench.thumbnail(self.id),normal)
        self.workbench.close()
        self.workbench=Workbench(self.root)
        after=self.workbench.scan(self.id)
        self.assertEqual(after['display'],settings)
        self.assertEqual(after['data'],before['data'])
        self.assertEqual(after['statistics'],before['statistics'])
        self.assertEqual(after['operations'],[])
        manifest=json.loads(self.workbench.export_scan(self.id)['content'])
        self.assertEqual(manifest['display']['settings'],settings)
        self.assertIn('mask',manifest)
        limits=self.workbench.display_range(self.id,mode='roi',roi={'x0':0,'y0':0,'x1':.2,'y1':.25})
        self.assertEqual((limits['minimum'],limits['maximum']),(0.,11.))
        self.assertEqual(sum(limits['histogram']['counts']),80)

    def test_invalid_settings_and_edits_are_atomic(self):
        first=self.rectangle()
        for payload in ({'action':'brush','points':[[0,0]],'radius':float('nan')},
                        {'action':'brush','points':[[2,0]],'radius':2},
                        {'action':'threshold','lower':10,'upper':0},
                        {'action':'rectangle','roi':{'x0':0,'x1':0,'y0':0,'y1':1}}):
            with self.assertRaises(ValueError):
                self.workbench.edit_mask(self.id,**payload)
            self.assertEqual(self.workbench.scan(self.id)['mask'],first)
        original=self.workbench.scan(self.id)['display']
        for settings in ({'mode':'manual','minimum':2,'maximum':1}, {'clip_percent':float('inf')},
                         {'minimum':float('nan')}, {'palette':'unknown'}, {'mode':'other'}):
            with self.assertRaises(ValueError):
                self.workbench.set_display(self.id,settings)
            self.assertEqual(self.workbench.scan(self.id)['display'],original)
        with self.assertRaises(ValueError):
            self.workbench.measure_area(self.id,mask=[[0]],use_saved_mask=True)

    def test_constants_preview_range_and_mcp_share_service(self):
        constant=self.insert(np.full((3,4),7.),'constant.tiff')
        self.workbench._db.commit()
        limits=self.workbench.display_range(constant)
        self.assertLess(limits['minimum'],7.)
        self.assertGreater(limits['maximum'],7.)
        limits=self.workbench.display_range(self.id,operations=[{'type':'zero_min','method':'gwyddion'}])
        self.assertEqual(limits['minimum'],0.)
        self.assertEqual(self.workbench.scan(self.id)['operations'],[])
        response=handle(self.workbench,{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'edit_mask','arguments':{'id':self.id,'action':'threshold','lower':70}}})
        result=json.loads(response['result']['content'][0]['text'])
        self.assertEqual(result['count'],10)
        self.assertEqual(result,self.workbench.scan(self.id)['mask'])


if __name__=='__main__':
    unittest.main()
