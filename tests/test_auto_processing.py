"""AFM-specific synthetic checks: scan drift, particles, terraces and ambiguity."""
import base64
import unittest
import numpy as np
from afm_workbench.science import apply_recipe
from test_processing import park_metadata


class AutoProcessingTests(unittest.TestCase):
    def run_auto(self, data, **parameters):
        return apply_recipe(data, [{'type':'auto_2d', **parameters}], park_metadata())

    def test_one_to_three_planes_preserve_step_heights_and_replay(self):
        y,x=np.mgrid[:96,:192];tilt=12+20*(x+.5)/192-7*(y+.5)/96
        for count in (1,2,3):
            layers=(x//(192//count))*3.2
            raw=tilt+layers;original=raw.copy()
            result,history=self.run_auto(raw)
            self.assertEqual(history[0]['model']['plane_count'],count)
            np.testing.assert_allclose(result,layers-np.median(layers),atol=1e-10)
            np.testing.assert_array_equal(raw,original)
            replay,replay_history=self.run_auto(raw)
            np.testing.assert_array_equal(replay,result);self.assertEqual(history,replay_history)
            model=history[0]['model']
            offsets=np.array(model['line_correction']['offsets'])
            a,b,c=model['coefficients']
            np.testing.assert_allclose(raw-result,a+b*(x+.5)/192+c*(y+.5)/96+offsets[:,None],atol=1e-10)

    def test_drift_noise_and_particles_keep_known_height_and_texture(self):
        y,x=np.mgrid[:128,:192];xx=(x+.5)/192;yy=(y+.5)/128
        rng=np.random.default_rng(17)
        layer=1.2*(x>110)
        particle=2*np.exp(-((xx-.25)**2+(yy-.3)**2)/.0003)
        rough=.015*rng.normal(size=x.shape)
        drift=4*(yy-.5)**2+.025*rng.normal(size=(128,1))
        raw=5+12*xx-8*yy+layer+particle+rough+drift
        result,history=self.run_auto(raw)
        self.assertAlmostEqual(float(result[30:95,140:180].mean()-result[30:95,40:80].mean()),1.2,delta=.025)
        self.assertGreater(float(result[36:41,45:51].max()-np.median(result[30:60,20:75])),1.5)
        model=history[0]['model'];self.assertGreater(model['excluded_pixel_count'],0)
        # No output filtering: on the same scan line, all local texture remains
        # except the analytically known plane slope subtraction.
        np.testing.assert_allclose(np.diff(result,axis=1),np.diff(raw,axis=1)-model['coefficients'][1]/192,atol=1e-12)

    def test_full_width_step_is_preserved_and_flagged(self):
        y,x=np.mgrid[:96,:192];layers=.7*(y>=48)
        raw=3+x/192-y/96+layers
        result,history=self.run_auto(raw)
        self.assertAlmostEqual(float(np.median(result[65:85])-np.median(result[10:30])),.7,places=8)
        self.assertIn(48,history[0]['model']['line_correction']['preserved_boundaries'])

    def test_six_terraces_and_fast_axis_curvature_fail_unchanged(self):
        y,x=np.mgrid[:96,:192];xx=x/192;yy=y/96
        for feature in ((x//32)*2., 8*xx**2):
            raw=5+xx-yy+feature;copy=raw.copy()
            with self.assertRaisesRegex(ValueError,'Manual corrections'):
                self.run_auto(raw)
            np.testing.assert_array_equal(raw,copy)

    def test_nonparallel_terrace_retains_relative_slope(self):
        y,x=np.mgrid[:96,:192];xx=(x+.5)/192;yy=(y+.5)/96
        layer=np.where(x>125,3+.6*yy,0)
        raw=4+3*xx-2*yy+layer
        result,history=self.run_auto(raw,line_correction=False)
        self.assertEqual(history[0]['model']['plane_count'],2)
        # One reference plane is removed everywhere; the second terrace tilt
        # is physical content and must not be flattened independently.
        difference=result[:,160:180].mean(axis=1)-result[:,30:50].mean(axis=1)
        np.testing.assert_allclose(difference,3+.6*yy[:,0],atol=1e-9)

    def test_columns_metadata_equivalence_and_nan_preservation(self):
        y,x=np.mgrid[:96,:192];raw=2+x/192-y/96+2*(x>100)
        raw=raw.astype(float);raw[10,20]=np.nan
        rows,h=self.run_auto(raw)
        cols,g=apply_recipe(raw.T,[{'type':'auto_2d'}],park_metadata(swap=True))
        np.testing.assert_allclose(rows,cols.T,atol=1e-9,equal_nan=True)
        self.assertTrue(np.isnan(rows[10,20]));self.assertEqual(g[0]['model']['line_correction']['axis'],'columns')
        mask=np.frombuffer(base64.b64decode(h[0]['model']['assignment_uint8_base64']),dtype=np.uint8).reshape(raw.shape)
        self.assertEqual(mask[10,20],255)

    def test_axis_and_parameter_validation_and_reference(self):
        y,x=np.mgrid[:32,:48];raw=1+x/48+y/32
        with self.assertRaisesRegex(ValueError,'not established'):
            apply_recipe(raw,[{'type':'auto_2d'}])
        for op in ({'type':'auto_2d','line_correction':'false'},{'type':'plane','line_correction':True}):
            with self.assertRaises(ValueError):apply_recipe(raw,[op])
        roi={'x0':.1,'x1':.8,'y0':.1,'y1':.8}
        result,h=self.run_auto(raw,line_correction=False,roi=roi)
        np.testing.assert_allclose(result,0,atol=1e-10)
        self.assertFalse(h[0]['model']['line_correction']['enabled'])

    def test_disconnected_islands_share_a_plane(self):
        y,x=np.mgrid[:128,:192];raw=2+x/192-y/128
        island=np.zeros(raw.shape,dtype=bool)
        for a,b in [(15,15),(75,20),(20,130),(80,135)]:
            island[a:a+30,b:b+35]=True
        raw=raw+1.5*island
        result,history=self.run_auto(raw)
        self.assertEqual(history[0]['model']['plane_count'],2)
        self.assertAlmostEqual(float(np.median(result[island])-np.median(result[~island])),1.5,places=8)
