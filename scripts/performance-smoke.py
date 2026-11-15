"""Measure rendered processing latency in native WebKit/WebView2 with synthetic data.

Run against a disposable catalog, including a packaged --browser runtime:
  .venv/bin/python scripts/performance-smoke.py http://127.0.0.1:8775
Pass --expect-compact to require the optimized lossless desktop transport.
The timings include HTTP, decoding, rendering and two animation frames, but not
the importer. They are measurements on this machine, not CI timing thresholds.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
import webview

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from test_importers import park_fixture


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('url')
parser.add_argument('--expect-compact', action='store_true')
args = parser.parse_args()
outcome = {}


def wait_for(window, expression):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if window.evaluate_js(expression):
            return
        time.sleep(.05)
    raise AssertionError(f'Timed out: {expression}')


with tempfile.TemporaryDirectory(prefix='afm-performance-') as root:
    folder = Path(root) / 'Synthetic 512px performance'
    folder.mkdir()
    y, x = np.mgrid[:512, :512] / 511
    values = 8 + 12*x - 7*y + 3.2*(x > .5) + np.random.default_rng(1).normal(0, .04, x.shape)
    (folder / '001__Z Height_Forward.tiff').write_bytes(park_fixture(values, gain=1, scale=1, offset=0, unit='nm'))
    window = webview.create_window('AFM processing performance verification', args.url, width=1200, height=850)

    def check():
        try:
            wait_for(window, '!!document.querySelector(".session-heading,.empty-state") && typeof api === "function"')
            script = r'''
            (async()=>{
              const assert=(v,m)=>{if(!v)throw Error(m);},times={};
              const frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
              const timed=async(name,fn)=>{const t=performance.now();await fn();await frame();times[name]=+(performance.now()-t).toFixed(1);};
              state.autoPrepare=false;
              const session=await api('import_folder',{path:FOLDER});
              await openSession(session.id);
              const id=session.scans[0].id;
              await timed('open_image_ms',()=>openScan(id));
              if(COMPACT)assert(state.scan.data instanceof Float64Array,'Desktop did not decode float64 pixels');
              const original=Array.from(flattenData(state.scan));
              await timed('cold_auto_level_ms',()=>runOperation('auto_characterize'));
              assert(state.scan.operations.length===1&&!state.pending,'Auto level did not save directly');
              assert(document.getElementById('height-canvas').width===512,'Wrong canvas dimensions');
              const saved=state.scan.history;
              await timed('append_plane_ms',()=>runOperation('plane'));
              assert(state.scan.operations.length===2,'Plane not saved');
              await timed('undo_ms',()=>actions.undo());
              assert(JSON.stringify(state.scan.history)===JSON.stringify(saved),'Undo changed recipe history');
              await timed('repeat_auto_level_ms',()=>runOperation('auto_characterize'));
              await actions.undo();
              state.lineDir='rows';
              await timed('replace_line_method_ms',()=>applyLine('median'));
              assert(state.scan.operations.some(o=>o.type==='align_rows'&&o.method==='median'),'Line method not saved');
              await actions.undo();
              await timed('roi_contrast_ms',()=>AFMDisplay.roi({x0:.1,x1:.4,y0:.2,y1:.8}));
              const expected=await api('display_range',{id,mode:'roi',roi:{x0:.1,x1:.4,y0:.2,y1:.8}});
              assert(JSON.stringify(AFMDisplay.range())===JSON.stringify([expected.minimum,expected.maximum]),'ROI contrast changed');
              await timed('profile_ms',()=>measureProfile([.1,.5],[.9,.5]));
              assert(state.profile.values.length>10,'Missing full-resolution profile');
              await timed('original_toggle_ms',()=>rawMode(true));
              const rawData=flattenData(state.scan);
              assert(original.every((v,i)=>Object.is(v,rawData[i])),'Original pixels changed');
              await rawMode(false);
              if(COMPACT){
                // Pixel interpolation agrees with the existing color function,
                // including invalid samples and all supported palettes.
                const canvas=document.createElement('canvas'),data=[NaN,null,-1,0,.001,.22,.5,.76,1,2];
                for(const palette of Object.keys(palettes)){
                  paintPixels(canvas,{data,width:data.length,height:1},0,1,palette);
                  const pixels=canvas.getContext('2d').getImageData(0,0,data.length,1).data;
                  data.forEach((v,i)=>{
                    const expected=v===null||!Number.isFinite(v)?[168,177,158]:color(v,palette);
                    assert(expected.every((c,j)=>c===pixels[i*4+j])&&pixels[i*4+3]===255,'Canvas colors changed');
                  });
                }
              }
              // Cache invalidation and mask snapshots are also exercised through
              // the real desktop transport, rather than only Python calls.
              await api('edit_mask',{id,action:'rectangle',roi:{x0:.1,x1:.2,y0:.1,y1:.4}});
              state.scan=await api('scan',{id});
              await timed('masked_plane_ms',()=>runOperation('plane'));
              assert(state.scan.operations.at(-1).mask,'Saved mask was not snapshotted');
              const masked=state.scan.statistics;
              await api('edit_mask',{id,action:'clear'});
              const reopened=await api('scan',{id});
              assert(JSON.stringify(reopened.statistics)===JSON.stringify(masked),'Mask edit changed saved correction');
              await actions.undo();
              const operations=JSON.stringify(state.scan.operations);
              try{await api('process',{id,operations:[...state.scan.operations,{type:'three_point',points:[[0,0],[0,0],[0,0]]}]});throw Error('Bad fit accepted');}
              catch(error){assert(!error.message.includes('Bad fit accepted'),'Bad fit accepted');}
              assert(JSON.stringify((await api('scan',{id})).operations)===operations,'Failed fit changed saved recipe');
              const t=performance.now();await fetch(thumb(state.scan)).then(r=>r.blob());times.thumbnail_first_ms=+(performance.now()-t).toFixed(1);
              const u=performance.now();await fetch(thumb(state.scan)).then(r=>r.blob());times.thumbnail_repeat_ms=+(performance.now()-u).toFixed(1);
              window.__performanceResult={passed:true,times,checks:['direct corrections','undo','line replacement','ROI contrast','profile','immutable original','mask snapshots','rejected fit','thumbnail repeat','canvas rendering']};
            })().catch(error=>window.__performanceResult={passed:false,error:error.stack||error.message});
            '''.replace('FOLDER', json.dumps(str(folder))).replace('COMPACT', str(args.expect_compact).lower())
            window.evaluate_js(script)
            wait_for(window, '!!window.__performanceResult')
            outcome.update(window.evaluate_js('window.__performanceResult'))
        except Exception as exc:
            outcome.update(passed=False, error=str(exc))
        finally:
            window.destroy()

    webview.start(check, private_mode=True)

print(json.dumps(outcome, indent=2))
sys.exit(0 if outcome.get('passed') else 1)
