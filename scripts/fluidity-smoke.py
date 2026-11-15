"""Profile bounded canvas input bursts in native WebKit/WebView2.

Run against a disposable source or rebuilt application's loopback server:
  .venv/bin/python scripts/fluidity-smoke.py http://127.0.0.1:8784

The fixture has 1024 x 1024 calibrated source pixels and the normal 512 x 512
display. Each phase dispatches 12 DOM input events per frame for 20 frames.
Pointer capture is emulated for synthetic pointers. Timings include instrumented
JavaScript work and observed animation-frame intervals, not physical device
latency or compositor/GPU timings; no hardware-dependent timing threshold is
used. Assertions check final gesture state, scientific stroke coverage, exact
contrast limits, persisted slider endpoints and immutable numerical data.
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
parser.add_argument('--expect-coalesced', action='store_true', help='Require bounded visual work per frame after optimization')
args = parser.parse_args()
outcome = {}
fixture_directory = tempfile.TemporaryDirectory(prefix='afm-fluidity-')
folder = Path(fixture_directory.name) / 'Synthetic fluidity 1024px'
folder.mkdir()
y, x = np.mgrid[:1024, :1024] / 1023
values = 7 + 8*x - 5*y + 3*(x > .5) + np.random.default_rng(6).normal(0, .03, x.shape)
(folder / '001__Z Height_Forward.tiff').write_bytes(park_fixture(
    values, gain=1, scale=1, offset=0, unit='nm', width_um=6, height_um=6))
window = webview.create_window('AFM canvas fluidity verification', args.url, width=1200, height=850)


def wait_for(expression):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if window.evaluate_js(expression):
            return
        time.sleep(.05)
    raise AssertionError(f'Timed out: {expression}')


def check():
    try:
        wait_for('!!document.querySelector(".session-heading,.empty-state") && typeof api === "function"')
        script = r'''
        (async()=>{
          const phases={},checks=[];let current='initialization',retainedCanvas=true;
          window.__fluidityProgress={current,checks,phases};
          const assert=(value,message)=>{if(!value)throw Error(current+': '+message);};
          const close=(a,b,t=1e-7)=>Math.abs(a-b)<t;
          const nativeRAF=window.requestAnimationFrame.bind(window);
          const frame=()=>new Promise(resolve=>nativeRAF(resolve));
          const settle=async()=>{
            await new Promise(resolve=>setTimeout(resolve,0));await AFMDisplay.pending();
            const deadline=performance.now()+20000;
            while(state.loading){assert(performance.now()<deadline,'operation timeout');await new Promise(resolve=>setTimeout(resolve,10));}
            await frame();await frame();
          };
          const select=async tool=>{const previous=document.getElementById('height-canvas');selectTool(tool);await frame();await frame();retainedCanvas&&=previous===document.getElementById('height-canvas');};
          let active=null;
          const originalRect=Element.prototype.getBoundingClientRect;
          Element.prototype.getBoundingClientRect=function(...args){if(active)active.layout_reads++;return originalRect.apply(this,args);};
          const originalStyle=window.getComputedStyle;
          window.getComputedStyle=function(...args){if(active)active.style_reads++;return originalStyle.apply(window,args);};
          const originalPut=CanvasRenderingContext2D.prototype.putImageData;
          CanvasRenderingContext2D.prototype.putImageData=function(...args){if(active)active.pixel_writes++;return originalPut.apply(this,args);};
          window.requestAnimationFrame=callback=>{
            const measured=active,index=active?.frame_index;
            if(measured)measured.scheduled_callbacks++;
            return nativeRAF(timestamp=>{
              const start=performance.now();
              try{return callback(timestamp);}finally{
                if(measured)measured.callback_work[index]=(measured.callback_work[index]||0)+performance.now()-start;
              }
            });
          };
          const observer=new MutationObserver(records=>{
            if(!active)return;
            for(const record of records){
              active.dom_mutations++;
              if(record.type==='childList'&&record.target.id==='draw-overlay')active.overlay_replacements++;
            }
          });
          observer.observe(document.body,{subtree:true,childList:true,attributes:true,characterData:true});
          const summary=values=>{
            const sorted=values.slice().sort((a,b)=>a-b),at=p=>sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||0;
            return {median:+at(.5).toFixed(3),p95:+at(.95).toFixed(3),max:+(sorted.at(-1)||0).toFixed(3)};
          };
          const burst=async(name,emit)=>{
            current=name;window.__fluidityProgress.current=name;
            const measured={frames:20,events:240,layout_reads:0,style_reads:0,pixel_writes:0,dom_mutations:0,overlay_replacements:0,scheduled_callbacks:0,callback_work:[],frame_index:0};
            const dispatch=[],intervals=[];let previous=await frame();active=measured;
            for(let i=0;i<20;i++){
              const timestamp=await frame();intervals.push(timestamp-previous);previous=timestamp;
              measured.frame_index=i;const started=performance.now();
              for(let j=0;j<12;j++)emit(i*12+j,240);
              dispatch.push(performance.now()-started);
            }
            await frame();await frame();await Promise.resolve();active=null;
            const work=dispatch.map((value,i)=>value+(measured.callback_work[i]||0));
            phases[name]={events:measured.events,frames:measured.frames,
              main_thread_work_ms_per_burst:summary(work),dispatch_ms_per_burst:summary(dispatch),frame_interval_ms:summary(intervals),
              total_main_thread_work_ms:+work.reduce((a,b)=>a+b,0).toFixed(3),
              layout_reads:measured.layout_reads,style_reads:measured.style_reads,pixel_writes:measured.pixel_writes,
              dom_mutations:measured.dom_mutations,overlay_replacements:measured.overlay_replacements,scheduled_callbacks:measured.scheduled_callbacks};
          };
          let pointer=500;
          const surface=()=>{
            const el=document.getElementById('draw-overlay');
            if(!el.__fluidityCapture){
              let capture=null;el.setPointerCapture=id=>{capture=id;};el.hasPointerCapture=id=>capture===id;
              el.releasePointerCapture=id=>{if(capture===id)capture=null;};el.__fluidityCapture=true;
            }
            return el;
          };
          const coords=point=>{const r=surface().getBoundingClientRect();return [r.left+point[0]*r.width,r.top+point[1]*r.height];};
          const send=(type,point,id,button=0)=>surface().dispatchEvent(new PointerEvent(type,{clientX:point[0],clientY:point[1],pointerId:id,pointerType:'mouse',isPrimary:true,button,buttons:type==='pointerup'?0:button===1?4:1,bubbles:true,cancelable:true}));
          const interpolate=(start,end,t)=>[start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t];
          const gesture=async(name,start,end,emit=null)=>{
            const id=++pointer;send('pointerdown',start,id);
            await burst(name,(i,count)=>send('pointermove',emit?emit(i,count):interpolate(start,end,(i+1)/count),id));
            // Release deliberately arrives before another visual frame. A
            // scheduled implementation must flush the endpoint before saving.
            send('pointermove',end,id);send('pointerup',end,id);await settle();
          };

          state.autoPrepare=false;
          const session=await api('import_folder',{path:FOLDER});await openSession(session.id);
          await openScan(session.scans[0].id);await settle();
          const id=state.scan.id,pixels=Array.from(flattenData(state.scan)),statistics=JSON.stringify(state.scan.statistics),operations=JSON.stringify(state.scan.operations);
          assert(state.scan.width===1024&&state.scan.data_width===512,'unexpected fixture/display dimensions');
          const originalRGBA=document.getElementById('height-canvas').getContext('2d').getImageData(0,0,512,512).data;

          await select('inspect');
          const hoverStart=coords([.1,.15]),hoverEnd=coords([.87,.79]);
          await burst('inspect',(i,count)=>send('pointermove',interpolate(hoverStart,hoverEnd,(i+1)/count),++pointer));
          const readout=document.getElementById('cursor-value').textContent;
          assert(readout.includes('x '+num(.87*state.scan.width_um))&&readout.includes('y '+num(.79*state.scan.height_um)),'latest inspection sample was dropped');checks.push('latest inspection sample');

          AFMCanvas.fit();AFMCanvas.zoom(1.5);await settle();await select('pan');
          const panStart=coords([.4,.4]),panEnd=[panStart[0]+54,panStart[1]+38],before=AFMCanvas.view();
          await gesture('pan',panStart,panEnd);
          assert(close(AFMCanvas.view().x,before.x+54,1)&&close(AFMCanvas.view().y,before.y+38,1),'final pan endpoint was dropped');checks.push('pan release flush');

          for(const [name,ctrlKey,deltaY,sensitivity] of [['wheel',false,-.5,.002],['pinch',true,-.1,.01]]){
            AFMCanvas.fit();await settle();await select('inspect');
            const target=surface(),anchor=coords([.4,.4]).map(Math.round),initial=target.getBoundingClientRect();
            const normalized=[(anchor[0]-initial.left)/initial.width,(anchor[1]-initial.top)/initial.height];
            await burst(name,()=>target.dispatchEvent(new WheelEvent('wheel',{clientX:anchor[0],clientY:anchor[1],deltaY,ctrlKey,bubbles:true,cancelable:true})));
            await settle();const after=target.getBoundingClientRect();
            assert(close(AFMCanvas.view().scale,Math.exp(-deltaY*sensitivity*240),1e-6),'wheel event deltas were dropped');
            assert(close((anchor[0]-after.left)/after.width,normalized[0],.001)&&close((anchor[1]-after.top)/after.height,normalized[1],.001),'zoom anchor moved');
            checks.push(name+' delta accumulation and anchor');
          }

          AFMCanvas.fit();await settle();state.contrastROI=null;await select('contrast');
          const roiStart=coords([.12,.14]),roiEnd=coords([.62,.66]);
          await gesture('contrast_draft',roiStart,roiEnd);
          assert(['x0','y0','x1','y1'].every((key,i)=>close(state.contrastROI[key],[.12,.14,.62,.66][i])),'final contrast endpoint was dropped');
          const expected=await api('display_range',{id,mode:'roi',roi:state.contrastROI});
          assert(close(AFMDisplay.range()[0],expected.minimum)&&close(AFMDisplay.range()[1],expected.maximum),'contrast differs from full-resolution region');checks.push('contrast release flush and exact limits');

          await select('mask');document.querySelector('[data-mask-shape="brush"]').click();await settle();
          const drawing=surface(),rect=drawing.getBoundingClientRect(),path=[];
          const sample=(i,count)=>{
            const row=Math.floor(i/12),column=i%12,t=row%2?1-column/11:column/11;
            const p=[.15+.7*t,.15+.6*row/19];path.push(p);return [rect.left+p[0]*rect.width,rect.top+p[1]*rect.height];
          };
          const brushStart=[rect.left+.15*rect.width,rect.top+.15*rect.height],brushEnd=[rect.left+.15*rect.width,rect.top+.75*rect.height];
          await gesture('brush_draft',brushStart,brushEnd,sample);
          assert(state.scan.mask.count>0,'brush did not commit');
          const bits=Uint8Array.from(atob(state.scan.mask.data_base64),c=>c.charCodeAt(0));
          const marked=p=>{const x=Math.min(state.scan.width-1,Math.floor(p[0]*state.scan.width)),y=Math.min(state.scan.height-1,Math.floor(p[1]*state.scan.height)),i=y*state.scan.width+x;return !!(bits[Math.floor(i/8)]&(128>>(i%8)));};
          assert(path.every(marked),'coalescing lost scientific brush samples');checks.push('every brush sample retained in full-resolution mask');

          await select('inspect');showInspector('view');await settle();
          document.querySelector('#display-controls [data-display-action="full"]').click();await settle();
          const full=AFMDisplay.range(),slider=document.getElementById('color-lower-slider');
          await burst('contrast_slider',(i,count)=>{slider.value=String(Math.round(100*(i+1)/count));slider.dispatchEvent(new Event('input',{bubbles:true}));});
          slider.dispatchEvent(new Event('change',{bubbles:true}));await settle();
          assert(close(AFMDisplay.range()[0],full[0]+(full[1]-full[0])*.1,1e-6),'latest slider endpoint was dropped');
          assert(close(AFMDisplay.settings().minimum,AFMDisplay.range()[0]),'slider endpoint was not persisted');
          const rgba=document.getElementById('height-canvas').getContext('2d').getImageData(0,0,512,512).data;
          assert(rgba.some((value,i)=>value!==originalRGBA[i]),'live contrast never changed displayed pixels');checks.push('latest slider preview and saved limits');
          const limits=AFMDisplay.range();
          for(const index of [0,65536,131072,262143]){
            const expected=color((flattenData(state.scan)[index]-limits[0])/(limits[1]-limits[0]));
            assert(expected.every((value,c)=>value===rgba[index*4+c]),'displayed pixels lag behind final contrast limits');
          }

          current='pending-frame cancellation';window.__fluidityProgress.current=current;
          await select('contrast');
          const roi=JSON.stringify(state.contrastROI),range=JSON.stringify(AFMDisplay.range());
          const visibleShapes=()=>Array.from(surface().querySelectorAll('rect,line,path,circle,text')).filter(el=>{
            const style=getComputedStyle(el),box=el.getBoundingClientRect();return style.display!=='none'&&style.visibility!=='hidden'&&(box.width||box.height);
          }).map(el=>{const r=el.getBoundingClientRect();return [el.tagName,r.x,r.y,r.width,r.height].map(v=>typeof v==='number'?+v.toFixed(2):v);});
          const beforeShapes=JSON.stringify(visibleShapes()),cancelPointer=++pointer;
          send('pointerdown',coords([.73,.76]),cancelPointer);send('pointermove',coords([.92,.94]),cancelPointer);
          surface().dispatchEvent(new PointerEvent('pointercancel',{pointerId:cancelPointer,bubbles:true}));await settle();
          assert(JSON.stringify(state.contrastROI)===roi&&JSON.stringify(AFMDisplay.range())===range,'cancelled pending frame changed the selection');
          assert(JSON.stringify(visibleShapes())===beforeShapes,'cancelled visual callback restored a stale draft');
          const panBefore=JSON.stringify(AFMCanvas.view()),panPointer=++pointer,start=coords([.35,.35]);
          send('pointerdown',start,panPointer,1);send('pointermove',[start[0]+60,start[1]+45],panPointer,1);
          surface().dispatchEvent(new PointerEvent('pointercancel',{pointerId:panPointer,bubbles:true}));await settle();
          assert(JSON.stringify(AFMCanvas.view())===panBefore,'cancelled pending pan changed viewport');
          const anchor=coords([.5,.5]).map(Math.round);
          surface().dispatchEvent(new WheelEvent('wheel',{clientX:anchor[0],clientY:anchor[1],deltaY:-60,bubbles:true,cancelable:true}));AFMCanvas.fit();await settle();
          assert(close(AFMCanvas.view().scale,1)&&close(AFMCanvas.view().x,0)&&close(AFMCanvas.view().y,0),'pending wheel callback undid Fit');checks.push('cancel and Fit discard pending visual work');

          current='immediate slider release';window.__fluidityProgress.current=current;
          showInspector('view');await settle();const latestSlider=document.getElementById('color-lower-slider'),endpoint=150;
          latestSlider.value=String(endpoint);latestSlider.dispatchEvent(new Event('input',{bubbles:true}));latestSlider.dispatchEvent(new Event('change',{bubbles:true}));await settle();
          assert(close(AFMDisplay.range()[0],full[0]+(full[1]-full[0])*endpoint/1000,1e-6)&&close(AFMDisplay.settings().minimum,AFMDisplay.range()[0]),'release saved a stale slider endpoint');checks.push('slider release before animation frame');

          // Lifecycle/field regressions run after every measured phase, so
          // comparison metrics retain the same input workload as the baseline.
          if(EXPECT_COALESCED){
            current='stationary draft retention';window.__fluidityProgress.current=current;
            const visibleDraft=()=>{
              const draft=surface().querySelector('#drawing-draft');
              if(!draft)return null;
              const box=draft.getBoundingClientRect(),style=getComputedStyle(draft);
              return style.display!=='none'&&style.visibility!=='hidden'&&box.width>0&&box.height>0?draft:null;
            };
            for(const tool of ['contrast','mask']){
              await select(tool);
              if(tool==='mask'){document.querySelector('[data-mask-shape="brush"]').click();await settle();}
              const p=++pointer,start=coords(tool==='contrast'?[.74,.77]:[.2,.25]),end=coords(tool==='contrast'?[.92,.94]:[.4,.6]);
              const savedROI=JSON.stringify(state.contrastROI),savedMask=state.scan.mask.revision;
              send('pointerdown',start,p);send('pointermove',end,p);await frame();await frame();
              const draft=visibleDraft();assert(draft,'missing stationary '+tool+' draft');
              const path=tool==='mask'?draft.querySelector('path')?.getAttribute('d'):null;
              restoreDrawing();await frame();await frame();
              assert(visibleDraft()===draft,'restoring static overlay erased or replaced stationary '+tool+' draft');
              if(tool==='mask')assert(draft.querySelector('path')?.getAttribute('d')===path,'static refresh changed brush geometry');
              surface().dispatchEvent(new PointerEvent('pointercancel',{pointerId:p,bubbles:true}));await settle();
              assert(!surface().querySelector('#drawing-draft'),'cancel retained '+tool+' draft');
              assert(JSON.stringify(state.contrastROI)===savedROI&&state.scan.mask.revision===savedMask,'static refresh/cancel changed scientific selection');
              if(tool==='mask')assert(AFMMask.preview()==='','cancel retained scientific brush stroke');
            }
            checks.push('stationary contrast and brush drafts survive static refresh and cancel cleanly');

            current='hover callback after tool change';window.__fluidityProgress.current=current;
            await select('inspect');
            send('pointermove',coords([.91,.81]),++pointer);
            selectTool('pan');
            const resetCursor=document.getElementById('cursor-value').textContent;
            await frame();await frame();
            assert(state.tool==='pan'&&document.getElementById('cursor-value').textContent===resetCursor,'old hover callback wrote into the next tool');
            assert(!surface().querySelector('#drawing-draft'),'tool change resurrected a draft');
            checks.push('tool change discards pending hover frame');

            current='numeric Set before slider frame';window.__fluidityProgress.current=current;
            showInspector('view');await settle();
            const numericSlider=document.getElementById('color-lower-slider'),untouchedMaximum=AFMDisplay.range()[1],span=full[1]-full[0];
            numericSlider.value='200';numericSlider.dispatchEvent(new Event('input',{bubbles:true}));
            document.querySelector('[data-display-action="manual"]').click();await settle();
            assert(close(AFMDisplay.range()[0],full[0]+span*.2,1e-6),'numeric Set read the stale untouched minimum');
            assert(AFMDisplay.range()[1]===untouchedMaximum,'numeric Set changed untouched maximum precision');
            assert(close(AFMDisplay.settings().minimum,AFMDisplay.range()[0]),'numeric Set did not save latest slider minimum');
            checks.push('numeric Set flushes latest untouched slider endpoint');

            current='numeric edit during slider frame';window.__fluidityProgress.current=current;
            const pendingSlider=document.getElementById('color-lower-slider'),maximumField=document.getElementById('color-max-input'),editedMaximum=full[0]+span*.85;
            pendingSlider.value='250';pendingSlider.dispatchEvent(new Event('input',{bubbles:true}));
            maximumField.value=String(editedMaximum);maximumField.dispatchEvent(new Event('input',{bubbles:true}));
            await frame();await frame();
            assert(maximumField.value===String(editedMaximum)&&maximumField.dataset.edited==='true','pending slider frame overwrote numeric edit');
            document.querySelector('[data-display-action="manual"]').click();await settle();
            assert(close(AFMDisplay.range()[0],full[0]+span*.25,1e-6)&&AFMDisplay.range()[1]===editedMaximum,'numeric Set lost edited or untouched endpoint');
            assert(AFMDisplay.settings().maximum===editedMaximum,'edited maximum was not persisted exactly');
            checks.push('pending slider render preserves edited numeric field');
          }

          assert(JSON.stringify(state.scan.statistics)===statistics&&JSON.stringify(state.scan.operations)===operations,'display/input changed numerical results');
          assert(pixels.every((value,i)=>Object.is(value,flattenData(state.scan)[i])),'display/input changed source pixels');checks.push('immutable numerical values and recipe');
          if(EXPECT_COALESCED){
            assert(phases.contrast_slider.pixel_writes<=22,'slider repaints more than once per frame');
            assert(phases.contrast_draft.overlay_replacements<=42&&phases.brush_draft.overlay_replacements<=42,'draft replaces the overlay for individual input events');
            assert(phases.pan.layout_reads<=50&&phases.wheel.layout_reads<=50&&phases.pinch.layout_reads<=50,'navigation rereads layout for individual input events');
            assert(retainedCanvas,'switching tools replaced the image canvas');checks.push('bounded visual work and retained canvas');
          }
          observer.disconnect();window.__fluidityResult={passed:true,fixture:{source:[1024,1024],display:[512,512]},events_per_frame:12,frames_per_phase:20,retained_canvas_on_tool_switch:retainedCanvas,phases,checks};
        })().catch(error=>window.__fluidityResult={passed:false,error:error.message+'\n'+(error.stack||''),progress:window.__fluidityProgress});
        '''.replace('FOLDER', json.dumps(str(folder))).replace('EXPECT_COALESCED', str(args.expect_coalesced).lower())
        window.evaluate_js(script)
        wait_for('!!window.__fluidityResult')
        outcome.update(window.evaluate_js('window.__fluidityResult'))
    except Exception as exc:
        outcome.update(passed=False, error=str(exc))
    finally:
        window.destroy()


webview.start(check, private_mode=True)
fixture_directory.cleanup()
print(json.dumps(outcome, indent=2))
sys.exit(0 if outcome.get('passed') else 1)
