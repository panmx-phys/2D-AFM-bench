/* Synthetic workflow acceptance. Run on a disposable local workspace.
   AFM_PYTHON=.venv/bin/python AFM_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/characterization-smoke.cjs URL [browser executable] */
const {chromium}=require(process.env.AFM_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {execFileSync}=require('node:child_process');
(async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'afm-characterization-'));
  let browser;
  try{
    execFileSync(process.env.AFM_PYTHON||'python3',['-c',`
import sys
from pathlib import Path
sys.path.insert(0, 'tests')
from test_importers import park_fixture
import numpy as np
y,x=np.mgrid[:96,:192]
for name,z in [('001_three',8+12*x/192-7*y/96+(x//64)*3.2),('002_six',8+12*x/192-7*y/96+(x//32)*4)]:
 Path(sys.argv[1],name+'.tiff').write_bytes(park_fixture(z,unit='nm',gain=1,scale=1,offset=0))
`,folder],{cwd:path.resolve(__dirname,'..')});
    browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
    const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.argv[2]||'http://127.0.0.1:8794');
    await page.waitForSelector('.session-heading,.empty-state');
    const session=await page.evaluate(async folder=>{const s=await api('import_folder',{path:folder});await openSession(s.id);return s;},folder);
    const good=session.scans.find(s=>s.acquisition==='001'),bad=session.scans.find(s=>s.acquisition==='002');
    const idle=()=>page.waitForFunction(()=>!state.loading);
    const click=async selector=>{await page.locator(selector).click();await idle();};
    const draw=async(a,b)=>{
      const r=await page.locator('#draw-overlay').boundingBox();
      await page.mouse.move(r.x+a[0]*r.width,r.y+a[1]*r.height);await page.mouse.down();
      await page.mouse.move(r.x+b[0]*r.width,r.y+b[1]*r.height,{steps:8});await page.mouse.up();
      await page.evaluate(()=>AFMDisplay.pending());
    };
    await page.evaluate(id=>openScan(id),good.id);
    assert.equal(await page.evaluate(()=>state.pending.at(-1).type),'auto_characterize');
    assert.equal(await page.evaluate(()=>state.tool),'contrast');
    const imageBox=await page.locator('#height-canvas').boundingBox(),overlayBox=await page.locator('#draw-overlay').boundingBox();
    assert.deepEqual(overlayBox,imageBox,'drawing coordinates must match the rectangular image exactly');
    await page.waitForFunction(()=>document.querySelectorAll('#draw-overlay circle').length===3);
    const before=await page.evaluate(async()=>api('scan',{id:state.scan.id}));
    assert.equal(before.operations.length,0);
    const numerical=await page.evaluate(()=>state.scan.statistics);
    await draw([.4,.2],[.6,.8]);
    const roi=await page.evaluate(async()=>({actual:AFMDisplay.range(),expected:await api('display_range',{id:state.scan.id,operations:state.pending,mode:'roi',clip_percent:0,roi:state.contrastROI}),saved:(await api('scan',{id:state.scan.id})).display}));
    assert.deepEqual(roi.actual,[roi.expected.minimum,roi.expected.maximum]);
    assert.deepEqual(roi.saved,before.display,'preview contrast must not overwrite saved display');
    assert.deepEqual(await page.evaluate(()=>state.scan.statistics),numerical);
    assert.equal(await page.evaluate(()=>state.area),null,'contrast rectangle must not become a fit or measurement reference');
    await click('[data-action=discard-preview]');
    assert.equal(await page.evaluate(()=>state.pending),null);
    assert.deepEqual(await page.evaluate(()=>AFMDisplay.settings()),before.display);
    // Saved mask is used by the automatic rerun and snapshotted into its recipe.
    await page.evaluate(async()=>{await api('edit_mask',{id:state.scan.id,action:'rectangle',roi:{x0:.4,x1:.6,y0:.3,y1:.5}});await api('update_mask',{id:state.scan.id,masking:'exclude'});state.scan=await api('scan',{id:state.scan.id});renderContent();});
    await click('[data-operation=auto_characterize]');
    assert.equal(await page.evaluate(()=>state.pending.at(-1).masking),'exclude');
    assert(await page.evaluate(()=>!!state.pending.at(-1).mask));
    await page.setViewportSize({width:900,height:650});
    for(const selector of ['.inspector-nav','.preview-decision','#height-canvas']){
      const r=await page.locator(selector).boundingBox();assert(r&&r.x>=0&&r.y>=0&&r.x+r.width<=901&&r.y+r.height<=651,selector+' fits minimum window');
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    fs.mkdirSync('.test-artifacts',{recursive:true});
    await page.screenshot({path:'.test-artifacts/characterization-preview.png'});
    await click('[data-action=apply-preview]');
    const saved=await page.evaluate(()=>state.scan.history);
    await page.reload();await page.waitForSelector('.scan-card');await page.evaluate(id=>openScan(id),good.id);
    assert.equal(await page.evaluate(()=>state.pending),null,'saved processing must not be automatically stacked');
    assert.deepEqual(await page.evaluate(()=>state.scan.history),saved);
    await page.evaluate(id=>openScan(id),bad.id);
    await page.locator('.preparation-error').waitFor();
    assert.match(await page.locator('.preparation-error').innerText(),/No correction was applied/);
    assert.equal(await page.evaluate(()=>state.pending),null);
    assert.equal(await page.evaluate(async()=>(await api('scan',{id:state.scan.id})).operations.length),0);
    await click('.preparation-error [data-tool=level]');
    for(const [x,y] of [[.03,.1],[.13,.15],[.04,.9]]){
      const r=await page.locator('#draw-overlay').boundingBox();await page.mouse.click(r.x+x*r.width,r.y+y*r.height);await idle();
    }
    await page.waitForFunction(()=>state.pending?.at(-1).type==='three_point');
    assert.equal(await page.locator('.preparation-error').count(),0);
    await page.waitForFunction(()=>document.querySelectorAll('#draw-overlay circle').length===3);
    await page.screenshot({path:'.test-artifacts/characterization-manual.png'});
    const manualDisplay=await page.evaluate(async()=>(await api('scan',{id:state.scan.id})).display);
    await page.evaluate(async()=>{const range=AFMDisplay.roi({x0:.01,x1:.1,y0:.1,y1:.8});await actions['discard-preview']();await range;});
    assert.deepEqual(await page.evaluate(()=>AFMDisplay.settings()),manualDisplay,'discard waits for an in-flight contrast request and restores saved settings');
    assert.deepEqual(await page.evaluate(async()=>(await api('scan',{id:state.scan.id})).display),manualDisplay);
    await page.locator('#auto-prepare-on-open').uncheck();
    await click('[data-action=back]');await page.evaluate(id=>openScan(id),bad.id);
    assert.equal(await page.evaluate(()=>state.pending),null);
    assert.equal(await page.locator('.preparation-error').count(),0);
    assert.deepEqual(errors,[]);
    console.log('PASS: automatic open, three visible reference points, full-resolution preview ROI contrast, isolation, mask snapshot, compact layout, save/reopen, failure notice, manual three-point fallback, opt-out.');
  }finally{if(browser)await browser.close();fs.rmSync(folder,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1);});
