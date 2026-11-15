"""Exercise canvas interactions in native WebKit/WebView2 using a synthetic session.

Run against a disposable catalog, including the rebuilt --browser runtime:
  .venv/bin/python scripts/canvas-smoke.py http://127.0.0.1:8775

DOM pointer/wheel/key events exercise the production handlers. Pointer capture is
emulated because synthetic pointers are not registered with the OS. This checks
rendering, selection geometry and interaction state, not physical input devices.
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
args = parser.parse_args()
outcome = {}
fixture_directory = tempfile.TemporaryDirectory(prefix='afm-canvas-')
rectangular_folder = Path(fixture_directory.name) / 'Rectangular physical calibration'
rectangular_folder.mkdir()
# A square pixel array with a 2:1 recorded footprint catches aspect-ratio errors.
(rectangular_folder / '001__Z Height_Forward.tiff').write_bytes(park_fixture(
    np.arange(64 * 64).reshape(64, 64) / 100,
    gain=1, scale=1, offset=0, unit='nm', width_um=8, height_um=4))
window = webview.create_window('AFM canvas interaction verification', args.url, width=1200, height=850)


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
        window.evaluate_js(r'''
        (async()=>{
          const checks=[];window.__canvasProgress={checks,current:'initialization'};
          let current='initialization';
          const assert=(v,m)=>{if(!v)throw Error(current+': '+m);};
          const clone=v=>JSON.parse(JSON.stringify(v));
          const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
          const close=(a,b,tolerance=1e-8)=>Math.abs(a-b)<tolerance;
          const sameROI=(a,b)=>a&&b&&['x0','x1','y0','y1'].every(k=>close(a[k],b[k]));
          const frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
          const until=async(predicate)=>{
            const deadline=performance.now()+15000;
            while(!predicate()){assert(performance.now()<deadline,'condition timed out');await new Promise(r=>setTimeout(r,10));}
          };
          const settle=async()=>{
            await new Promise(r=>setTimeout(r,0));
            await AFMDisplay.pending();
            const deadline=performance.now()+15000;
            while(state.loading){assert(performance.now()<deadline,'operation timed out');await new Promise(r=>setTimeout(r,10));}
            await frame();
          };
          const click=async selector=>{const el=document.querySelector(selector);assert(el&&!el.disabled,'missing enabled '+selector);el.click();await settle();};
          const key=(type,value,code=value)=>{
            const el=document.getElementById('height-canvas');el.focus({preventScroll:true});
            el.dispatchEvent(new KeyboardEvent(type,{key:value,code,bubbles:true,cancelable:true}));
          };
          let pointer=20;
          const surface=()=>{
            const el=document.getElementById('draw-overlay');
            if(!el.__syntheticCapture){
              let captured=null;
              el.setPointerCapture=id=>{captured=id;};
              el.hasPointerCapture=id=>captured===id;
              el.releasePointerCapture=id=>{if(captured===id)captured=null;};
              el.__syntheticCapture=true;
            }
            return el;
          };
          const coords=p=>{const b=surface().getBoundingClientRect();return [b.left+p[0]*b.width,b.top+p[1]*b.height];};
          const send=(type,client,id,button=0)=>{
            surface().dispatchEvent(new PointerEvent(type,{clientX:client[0],clientY:client[1],pointerId:id,pointerType:'mouse',isPrimary:true,button,buttons:type==='pointerup'||type==='pointercancel'?0:button===1?4:1,bubbles:true,cancelable:true}));
          };
          const drag=async(a,b,{button=0,cancel=false,wait=true}={})=>{
            const id=++pointer,start=coords(a),end=coords(b);
            send('pointerdown',start,id,button);
            for(let i=1;i<=5;i++)send('pointermove',[start[0]+(end[0]-start[0])*i/5,start[1]+(end[1]-start[1])*i/5],id,button);
            send(cancel?'pointercancel':'pointerup',end,id,button);if(wait)await settle();
          };
          const checkRange=async()=>{
            const expected=await api('display_range',{id:state.scan.id,mode:'roi',roi:state.contrastROI});
            const actual=AFMDisplay.range();
            assert(close(actual[0],expected.minimum)&&close(actual[1],expected.maximum),'limits differ from full-resolution ROI');
          };
          const verifyHiddenGuides=async()=>{
            const snapshot=()=>clone({tool:state.tool,tab:state.inspectorTab,roi:state.contrastROI,range:AFMDisplay.range(),
              mask:state.scan.mask,profile:state.profile,area:state.area,regions:state.regions,points:state.levelPoints,
              operations:state.scan.operations,display:state.scan.display,statistics:state.scan.statistics});
            const before=snapshot(),image=document.getElementById('height-canvas'),pixels=image.toDataURL();
            await click('[data-action="toggle-inspector"]');
            assert(state.inspectorHidden&&document.getElementById('image-inspector').hidden,'controls still shown');
            assert(getComputedStyle(document.getElementById('canvas-tools')).display==='none','canvas toolbar still shown');
            assert(getComputedStyle(document.getElementById('profile-panel')).display==='none','measurement panel still shown');
            assert(getComputedStyle(document.getElementById('mask-canvas')).visibility==='hidden','mask still shown');
            for(const node of document.querySelectorAll('#draw-overlay *'))
              assert(getComputedStyle(node).visibility==='hidden','guide still visible: '+node.tagName);
            // Dragging where an invisible guide used to be must leave analysis untouched.
            await drag([.12,.16],[.42,.56]);
            assert(equal(snapshot(),before),'hidden drag modified analysis or selection');
            await click('[data-canvas-action="zoom-in"]');
            assert(AFMCanvas.view().scale>1,'zoom disabled with controls hidden');
            await drag([.4,.4],[.45,.45],{button:1});
            assert(Math.abs(AFMCanvas.view().x)>1,'pan disabled with controls hidden');
            await click('[data-canvas-action="fit"]');
            assert(state.inspectorHidden&&equal(snapshot(),before),'navigation changed controls or analysis');
            assert(image.toDataURL()===pixels,'hiding changed displayed image pixels');
            await click('[data-action="toggle-inspector"]');
            assert(!state.inspectorHidden&&equal(snapshot(),before),'show did not retain settings and guides');
            assert(getComputedStyle(document.getElementById('mask-canvas')).visibility==='visible','mask visibility not restored');
            for(const node of document.querySelectorAll('#drawing-static > *'))
              assert(getComputedStyle(node).visibility==='visible','guide visibility not restored');
          };
          const visibleROI=()=>Array.from(document.querySelectorAll('#draw-overlay text')).some(el=>el.textContent==='Contrast');
          const step=async(name,fn)=>{current=name;window.__canvasProgress.current=name;await fn();checks.push(name);};

          state.autoPrepare=false;
          const session=await api('demo');await openSession(session.id);
          const id=session.scans.find(s=>s.channel==='Z Height'&&s.direction==='Forward').id;
          await api('process',{id,operations:[]});await api('edit_mask',{id,action:'clear'});
          await api('set_display',{id,settings:{palette:'amber',mode:'full',clip_percent:0}});
          await openScan(id);await frame();
          const statistics=clone(state.scan.statistics),operations=clone(state.scan.operations),pixels=Array.from(flattenData(state.scan));

          await step('hide and restore inspector without changing image state',async()=>{
            await click('#inspector-tab-prepare');
            const toggle=document.querySelector('[data-action="toggle-inspector"]');
            assert(toggle.querySelector('svg')&&toggle.textContent===''&&toggle.parentElement.lastElementChild===toggle,'toggle is not a rightmost icon');
            assert(toggle.getBoundingClientRect().width<=28,'toggle is not compact');
            const stage=document.querySelector('.canvas-stage'),width=stage.getBoundingClientRect().width;
            const snapshot=clone({operations:state.scan.operations,display:state.scan.display,tool:state.tool});
            await click('[data-action="toggle-inspector"]');
            assert(document.getElementById('image-inspector').hidden,'inspector still visible');
            assert(stage.getBoundingClientRect().width>width,'canvas did not gain space');
            assert(document.querySelector('[data-action="toggle-inspector"]').getAttribute('aria-expanded')==='false','toggle accessibility state');
            assert(localStorage.getItem('afm-inspector-hidden')==='true','preference not saved');
            renderContent();await frame();
            assert(document.getElementById('image-inspector').hidden,'rerender lost hidden preference');
            assert(document.querySelector('.canvas-stage')===stage,'canvas replaced');
            await click('[data-action="toggle-inspector"]');
            assert(!document.getElementById('image-inspector').hidden&&state.inspectorTab==='prepare','tab not restored');
            assert(equal(snapshot,{operations:state.scan.operations,display:state.scan.display,tool:state.tool}),'image state changed');
            await click('[data-action="toggle-inspector"]');
            key('keydown','1');await frame();
            assert(!state.inspectorHidden&&state.inspectorTab==='view','tab shortcut did not reveal inspector');
            assert(localStorage.getItem('afm-inspector-hidden')==='false','shown preference not saved');
          });

          await step('discoverable region selection and full-resolution contrast',async()=>{
            await click('[data-display-action="select-roi"]');
            assert(state.tool==='contrast','Select region did not activate contrast');
            await drag([.12,.16],[.42,.56]);
            assert(sameROI(state.contrastROI,{x0:.12,y0:.16,x1:.42,y1:.56}),'wrong drawn ROI');
            assert(visibleROI(),'selected region disappeared');await checkRange();
            assert(equal(state.scan.statistics,statistics)&&equal(state.scan.operations,operations),'display changed numerical result');
          });
          await step('hide contrast outline and handles while retaining contrast',async()=>{
            assert(document.querySelectorAll('.contrast-handle').length===4,'missing contrast handles');
            await verifyHiddenGuides();
            assert(visibleROI(),'contrast guide did not return');
          });
          await step('selection survives tool and inspector changes',async()=>{
            const roi=clone(state.contrastROI);
            await click('[data-tool="profile"]');
            showInspector('prepare');await frame();showInspector('view');await frame();
            assert(sameROI(state.contrastROI,roi)&&visibleROI(),'selection lost after tool/tab changes');
            await click('[data-display-action="select-roi"]');
          });
          await step('clicks and zero-height drags preserve selected region',async()=>{
            const roi=clone(state.contrastROI),range=AFMDisplay.range();
            await drag([.76,.18],[.76,.18]);
            await drag([.72,.18],[.94,.18]);
            assert(sameROI(state.contrastROI,roi),'click or degenerate drag replaced region');
            assert(equal(AFMDisplay.range(),range),'click or degenerate drag changed limits');
          });
          await step('move and resize selected region',async()=>{
            const before=clone(state.contrastROI);
            await drag([.27,.36],[.31,.41]);
            assert(sameROI(state.contrastROI,{x0:before.x0+.04,x1:before.x1+.04,y0:before.y0+.05,y1:before.y1+.05}),'interior drag did not move region');
            await checkRange();
            const moved=clone(state.contrastROI);
            await drag([moved.x1,moved.y1],[moved.x1+.08,moved.y1+.06]);
            assert(sameROI(state.contrastROI,{...moved,x1:moved.x1+.08,y1:moved.y1+.06}),'corner drag did not resize region');
            await checkRange();
          });
          await step('Escape and pointer cancellation restore previous selection',async()=>{
            const roi=clone(state.contrastROI),range=AFMDisplay.range();
            const p=++pointer;send('pointerdown',coords([.72,.18]),p);send('pointermove',coords([.94,.42]),p);
            key('keydown','Escape','Escape');send('pointerup',coords([.94,.42]),p);await settle();
            assert(state.view==='detail'&&state.tool==='contrast','Escape left tool while cancelling a drag');
            assert(sameROI(state.contrastROI,roi)&&equal(AFMDisplay.range(),range),'Escape did not restore previous selection');
            await drag([.73,.72],[.94,.94],{cancel:true});
            assert(sameROI(state.contrastROI,roi)&&equal(AFMDisplay.range(),range),'pointercancel committed a selection');
            const lost=++pointer;send('pointerdown',coords([.73,.72]),lost);send('pointermove',coords([.94,.94]),lost);
            send('lostpointercapture',coords([.94,.94]),lost);send('pointerup',coords([.94,.94]),lost);await settle();
            assert(sameROI(state.contrastROI,roi)&&equal(AFMDisplay.range(),range),'lostpointercapture committed a selection');
            const q=++pointer;send('pointerdown',coords([.73,.72]),q);send('pointermove',coords([.94,.94]),q);
            window.dispatchEvent(new Event('blur'));send('pointerup',coords([.94,.94]),q);await settle();
            assert(sameROI(state.contrastROI,roi),'window blur committed a selection');
          });
          await step('correction and undo preserve contrast outline',async()=>{
            const roi=clone(state.contrastROI);
            await runOperation('plane');await frame();
            assert(sameROI(state.contrastROI,roi)&&visibleROI(),'applying correction removed region');
            await actions.undo();await frame();
            assert(sameROI(state.contrastROI,roi)&&visibleROI(),'undo removed region');
            assert(equal(state.scan.statistics,statistics),'undo did not restore original numerical result');
          });
          await step('rapid consecutive drags keep the latest region and limits',async()=>{
            const realFetch=window.fetch,requested=[];
            let release,intercepted=false;
            const gate=new Promise(r=>release=r);
            window.fetch=async(url,options)=>{
              const body=options?.body&&JSON.parse(options.body);
              if(String(url).endsWith('/api/display_range')&&body?.mode==='roi'){
                requested.push(clone(body.roi));
                if(!intercepted){intercepted=true;await gate;}
              }
              return realFetch(url,options);
            };
            try{
              await drag([.65,.68],[.9,.9],{wait:false});await until(()=>intercepted);
              assert(document.querySelector('#display-controls').getAttribute('aria-busy')==='true','first request was not held in flight');
              await drag([.60,.08],[.89,.30],{wait:false});
              release();await settle();
              assert(requested.length===2,'a completed drag was dropped: '+JSON.stringify(requested));
              assert(sameROI(state.contrastROI,{x0:.60,y0:.08,x1:.89,y1:.30}),'latest region was lost');
              await checkRange();
            }finally{release();window.fetch=realFetch;}
            await drag([.12,.16],[.42,.56]);
          });
          await step('failed contrast request restores prior outline and limits',async()=>{
            const roi=clone(state.contrastROI),range=AFMDisplay.range(),realFetch=window.fetch;
            let failed=false;
            window.fetch=async(url,options)=>{
              const body=options?.body&&JSON.parse(options.body);
              if(!failed&&String(url).endsWith('/api/display_range')&&body?.mode==='roi'){
                failed=true;
                return new Response(JSON.stringify({error:'Synthetic ROI failure'}),{status:500,headers:{'Content-Type':'application/json'}});
              }
              return realFetch(url,options);
            };
            try{
              await drag([.67,.71],[.91,.93]);
              assert(failed,'request failure was not exercised');
              assert(sameROI(state.contrastROI,roi)&&visibleROI(),'failed request lost prior outline');
              assert(equal(AFMDisplay.range(),range),'failed request changed limits');
              assert(document.getElementById('toast').textContent.includes('Synthetic ROI failure'),'failure was not surfaced');
            }finally{window.fetch=realFetch;}
          });
          await step('pointer-centered wheel zoom and visible navigation controls',async()=>{
            const roi=clone(state.contrastROI),location=coords([.35,.4]),before=surface().getBoundingClientRect();
            const wheel=new WheelEvent('wheel',{clientX:location[0],clientY:location[1],deltaY:-180,bubbles:true,cancelable:true});
            // WebKit rounds synthetic WheelEvent coordinates to CSS pixels.
            const anchor=[wheel.clientX,wheel.clientY],expected=[(anchor[0]-before.left)/before.width,(anchor[1]-before.top)/before.height];
            surface().dispatchEvent(wheel);await frame();
            assert(AFMCanvas.view().scale>1,'wheel did not zoom');
            const b=surface().getBoundingClientRect();
            const anchored=[(anchor[0]-b.left)/b.width,(anchor[1]-b.top)/b.height];
            assert(close(anchored[0],expected[0],1e-5)&&close(anchored[1],expected[1],1e-5),'wheel zoom moved pointer anchor: '+JSON.stringify({anchored,expected,anchor,view:AFMCanvas.view(),bounds:{x:b.x,y:b.y,width:b.width,height:b.height}}));
            assert(sameROI(state.contrastROI,roi)&&visibleROI(),'zoom lost selection');
            const scale=AFMCanvas.view().scale;await click('[data-canvas-action="zoom-in"]');
            assert(AFMCanvas.view().scale>scale,'zoom-in control did not zoom');
            await click('[data-canvas-action="zoom-out"]');
            assert(AFMCanvas.view().scale<scale*1.8,'zoom-out control did not zoom out');
          });
          await step('Space and middle-button pan preserve active tool and region',async()=>{
            const roi=clone(state.contrastROI),tool=state.tool,start=clone(AFMCanvas.view());
            key('keydown',' ','Space');await drag([.3,.3],[.38,.36]);key('keyup',' ','Space');await frame();
            const after=AFMCanvas.view();
            assert(Math.hypot(after.x-start.x,after.y-start.y)>5,'Space-drag did not pan');
            assert(state.tool===tool&&sameROI(state.contrastROI,roi),'temporary pan changed active tool or region');
            await drag([.35,.35],[.30,.30],{button:1});
            const middle=AFMCanvas.view();
            assert(Math.hypot(middle.x-after.x,middle.y-after.y)>5,'middle-drag did not pan');
            assert(state.tool===tool&&sameROI(state.contrastROI,roi),'middle pan changed tool or region');
            await click('[data-canvas-action="fit"]');
            assert(close(AFMCanvas.view().scale,1)&&close(AFMCanvas.view().x,0)&&close(AFMCanvas.view().y,0),'Fit did not reset viewport');
          });
          await step('drawing while zoomed uses image coordinates',async()=>{
            await click('[data-canvas-action="zoom-in"]');
            await drag([.65,.22],[.84,.49]);
            assert(sameROI(state.contrastROI,{x0:.65,y0:.22,x1:.84,y1:.49}),'zoomed drawing used viewport coordinates');
            await checkRange();
            key('keydown','f','KeyF');key('keyup','f','KeyF');await frame();
            assert(close(AFMCanvas.view().scale,1),'F did not fit image');
          });
          await step('clear outline preserves display limits and original pixels',async()=>{
            const range=AFMDisplay.range();await click('[data-display-action="clear-roi"]');
            assert(!state.contrastROI&&!visibleROI(),'Clear did not remove outline');
            assert(equal(AFMDisplay.range(),range),'Clear changed display limits');
            await rawMode(true);await frame();
            assert(pixels.every((v,i)=>Object.is(v,flattenData(state.scan)[i])),'canvas interactions changed original pixels');
            await rawMode(false);await frame();
          });
          await step('H hand tool pans Original without drawing or changing pixels',async()=>{
            await rawMode(true);await frame();
            key('keydown','h','KeyH');key('keyup','h','KeyH');await frame();
            assert(state.tool==='pan'&&state.raw,'H did not activate Pan on Original');
            const before=clone(AFMCanvas.view());await drag([.3,.3],[.4,.4]);
            assert(Math.hypot(AFMCanvas.view().x-before.x,AFMCanvas.view().y-before.y)>5,'Hand tool did not pan Original');
            assert(!state.contrastROI&&pixels.every((v,i)=>Object.is(v,flattenData(state.scan)[i])),'Original pan changed selection or pixels');
            await click('[data-canvas-action="fit"]');await rawMode(false);await frame();
          });
          await step('profile, area, step and mask pointer routes preserve data',async()=>{
            const temporaryPan=async(property)=>{
              const selection=clone(state[property]),tool=state.tool;
              key('keydown',' ','Space');await drag([.3,.3],[.35,.35]);key('keyup',' ','Space');await frame();
              assert(state.tool===tool&&equal(state[property],selection),'temporary pan changed '+property);
              await click('[data-canvas-action="fit"]');
            };
            await click('[data-tool="profile"]');await drag([.05,.4],[.95,.4]);
            assert(state.profile?.values.length>10&&sameROI({x0:state.profile.selection.start[0],y0:state.profile.selection.start[1],x1:state.profile.selection.end[0],y1:state.profile.selection.end[1]},{x0:.05,y0:.4,x1:.95,y1:.4}),'profile gesture did not produce the selected line');
            await temporaryPan('profile');
            await verifyHiddenGuides();
            await click('[data-tool="area"]');await drag([.1,.1],[.4,.4]);
            assert(state.area?.statistics.count>0&&Number.isFinite(state.area.statistics.mean)&&sameROI(state.area.roi,{x0:.1,y0:.1,x1:.4,y1:.4}),'area gesture did not produce region statistics');
            await temporaryPan('area');
            await verifyHiddenGuides();
            await click('[data-tool="step"]');await drag([.05,.1],[.25,.4]);await drag([.65,.1],[.85,.4]);
            assert(state.regions.length===2&&Number.isFinite(state.step?.difference)&&state.step.region_a.count>0&&state.step.region_b.count>0,'two step gestures did not produce region difference');
            await verifyHiddenGuides();
            await click('[data-tool="mask"]');await click('[data-mask-shape="rectangle"]');await click('[data-mask-edit="add"]');
            const setMaskUse=async value=>{const el=document.getElementById('mask-use');el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));await settle();};
            await setMaskUse('exclude');await drag([.2,.2],[.55,.55]);
            const mask=clone(state.scan.mask),total=state.scan.width*state.scan.height;
            assert(mask.count>0&&mask.count<total&&state.scan.masked_statistics.count===total-mask.count,'rectangle mask gesture did not exclude marked pixels');
            await verifyHiddenGuides();
            // Current-view PNG follows temporary visibility without saving it to the mask.
            const exportedPixel=async()=>{
              const originalDownload=download;let encoded;
              try{download=async(name,content)=>{encoded=content;};await exportFigure();}
              finally{download=originalDownload;}
              const png=new Image();png.src='data:image/png;base64,'+encoded;await png.decode();
              const canvas=document.createElement('canvas');canvas.width=png.width;canvas.height=png.height;
              const ctx=canvas.getContext('2d');ctx.drawImage(png,0,0);
              const ratio=state.scan.width_um/state.scan.height_um,w=ratio>=1?940:940*ratio,h=ratio>=1?940/ratio:940;
              return Array.from(ctx.getImageData(Math.floor(80+(940-w)/2+w*.35),Math.floor(95+h*.35),1,1).data);
            };
            const visiblePixel=await exportedPixel(),savedVisibility=state.scan.mask.visible;
            await click('[data-action="toggle-inspector"]');
            const hiddenPixel=await exportedPixel();
            assert(!equal(visiblePixel,hiddenPixel),'exported mask overlay did not hide');
            assert(state.scan.mask.visible===savedVisibility,'temporary visibility changed saved mask preference');
            await click('[data-action="toggle-inspector"]');
            assert(equal(await exportedPixel(),visiblePixel),'exported mask overlay did not restore');
            await click('[data-tool="profile"]');await drag([.05,.4],[.95,.4]);
            assert(state.profile?.masking==='exclude'&&state.profile.values.some(v=>v===null)&&state.profile.values.some(v=>v!==null),'masked profile pointer route did not retain excluded gaps');
            await click('[data-tool="area"]');await drag([.05,.05],[.95,.95]);
            assert(state.area?.masking==='exclude'&&state.area.statistics.count>0&&state.area.statistics.count<total*.81,'area pointer route did not intersect the exclusion mask');
            showInspector('prepare');await frame();await setMaskUse('include');
            assert(state.scan.masked_statistics.count===mask.count,'include mode did not select marked pixels');
            await click('[data-tool="area"]');await drag([.05,.05],[.95,.95]);
            assert(state.area?.masking==='include'&&state.area.statistics.count===mask.count,'area pointer route did not use inclusion mask');
            const raw=await api('scan',{id,raw:true});
            assert(pixels.every((v,i)=>Object.is(v,flattenData(raw)[i]))&&equal(state.scan.operations,operations),'measurement or mask pointer gesture changed original pixels or recipe');
            showInspector('prepare');await frame();await click('[data-mask-action="clear"]');await setMaskUse('exclude');
          });
          await step('leveling points hide and tool shortcuts restore controls',async()=>{
            selectTool('level');await frame();
            await drag([.1,.1],[.1,.1]);
            await drag([.8,.1],[.8,.1]);
            assert(state.levelPoints.length===2,'level reference points missing');
            await verifyHiddenGuides();
            await click('[data-action="toggle-inspector"]');
            key('keydown','m');await frame();
            assert(!state.inspectorHidden&&state.tool==='mask','drawing shortcut did not restore controls');
          });
          await step('recorded physical aspect aligns image, mask and region overlay',async()=>{
            const rectangle=await api('import_folder',{path:RECTANGULAR_FOLDER});
            await openSession(rectangle.id);await openScan(rectangle.scans[0].id);await frame();
            assert(state.scan.width===state.scan.height&&state.scan.width_um/state.scan.height_um===2,'rectangular calibration fixture is invalid');
            const image=document.getElementById('height-canvas').getBoundingClientRect(),drawing=surface().getBoundingClientRect(),mask=document.getElementById('mask-canvas').getBoundingClientRect();
            assert(close(image.width/image.height,2,.005),'image does not use recorded physical aspect: '+JSON.stringify({width:image.width,height:image.height}));
            assert(close(image.width,drawing.width,.05)&&close(image.height,drawing.height,.05)&&close(image.left,drawing.left,.05)&&close(image.top,drawing.top,.05),'image and drawing overlay disagree');
            assert(close(image.width,mask.width,.05)&&close(image.height,mask.height,.05),'image and mask overlay disagree');
            await click('[data-display-action="select-roi"]');await drag([.15,.2],[.45,.7]);
            assert(sameROI(state.contrastROI,{x0:.15,y0:.2,x1:.45,y1:.7}),'rectangular selection used incorrect coordinates');await checkRange();
            const roi=clone(state.contrastROI);await click('[data-canvas-action="zoom-in"]');
            const zoomed=surface().getBoundingClientRect();
            assert(close(zoomed.width/zoomed.height,2,.005)&&sameROI(state.contrastROI,roi),'zoom changed physical aspect or region');
            await click('[data-canvas-action="fit"]');
          });
          window.__canvasResult={passed:true,checks};
        })().catch(error=>window.__canvasResult={passed:false,...window.__canvasProgress,error:String(error.message||error)+'\n'+String(error.stack||'')});
        '''.replace('RECTANGULAR_FOLDER', json.dumps(str(rectangular_folder))))
        wait_for('!!window.__canvasResult')
        outcome.update(window.evaluate_js('window.__canvasResult'))
        if outcome.get('passed'):
            window.resize(900, 650)
            time.sleep(.25)
            window.evaluate_js('AFMCanvas.refresh()')
            assert window.evaluate_js('document.documentElement.scrollWidth<=innerWidth'), '900 × 650 page overflows horizontally'
            assert window.evaluate_js('document.querySelector("[data-canvas-action=fit]").getBoundingClientRect().right<=innerWidth'), 'Fit control is outside compact window'
            outcome['checks'].append('900 × 650 layout without horizontal page overflow')
            window.evaluate_js('setInspectorHidden(true)')
            time.sleep(.1)
            assert window.evaluate_js('document.querySelector("[data-action=toggle-inspector]").getBoundingClientRect().right<=innerWidth'), 'Toggle is outside compact window'
            current_id = window.evaluate_js('state.scan.id')
            window.evaluate_js('location.reload()')
            wait_for('!!document.querySelector(".session-heading,.empty-state") && typeof api === "function"')
            assert window.evaluate_js('state.inspectorHidden'), 'Reload lost controls preference'
            window.evaluate_js(f'openScan({json.dumps(current_id)})')
            wait_for('!!document.getElementById("image-inspector") && !state.loading')
            assert window.evaluate_js('document.getElementById("image-inspector").hidden && getComputedStyle(document.getElementById("canvas-tools")).display==="none"'), 'Reopened scan did not hide controls'
            window.evaluate_js('setInspectorHidden(false)')
            outcome['checks'].append('900 × 650 toggle access and hidden preference after page reload')

    except Exception as exc:
        outcome.update(passed=False, error=str(exc))
        try:
            outcome['progress'] = window.evaluate_js('window.__canvasProgress || null')
        except Exception:
            pass
    finally:
        window.destroy()


webview.start(check, private_mode=True)
fixture_directory.cleanup()
print(json.dumps(outcome, indent=2))
sys.exit(0 if outcome.get('passed') else 1)
