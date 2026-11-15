/* Run on a disposable local workspace. Requires Playwright and installed Python dependencies.
   AFM_PYTHON=.venv/bin/python node scripts/processing-smoke.cjs URL [browser executable]
   Generates only synthetic TIFF fixtures, then imports them through the application API. */
const {chromium}=require(process.env.AFM_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
(async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'afm-terraces-'));
  let browser;
  try{
    execFileSync(process.env.AFM_PYTHON||'python3',['-c',`
import sys
from pathlib import Path
sys.path.insert(0, 'tests')
from test_importers import park_fixture
import numpy as np
y,x=np.mgrid[:60,:90]
for name,z in [('001_three',3+x/90-y/60+(x//30)*5),('002_six',3+x/90-y/60+(x//15)*5)]:
 Path(sys.argv[1],name+'.tiff').write_bytes(park_fixture(z,unit='nm',gain=1,scale=1,offset=0))
`,folder],{cwd:path.resolve(__dirname,'..')});
    browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
    const page=await browser.newPage({viewport:{width:1100,height:800}});
    await page.addInitScript(() => localStorage.setItem('afm-auto-prepare', 'false')); // Exercise explicit corrections; automatic preparation has its own smoke test.
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const tab=async name=>{await page.locator('#inspector-tab-'+name).click();await page.locator('#inspector-panel-'+name).waitFor({state:'visible'});};
    const openDetails=async id=>{const details=page.locator('#'+id);if(!await details.evaluate(el=>el.open))await details.locator('summary').click();};
    await page.goto(process.argv[2]||'http://127.0.0.1:8771');
    await page.waitForSelector('.session-heading,.empty-state');
    const session=await page.evaluate(async folder=>{const session=await api('import_folder',{path:folder});await openSession(session.id);return session;},folder);
    const good=session.scans.find(s=>s.acquisition==='001'),bad=session.scans.find(s=>s.acquisition==='002');
    await page.evaluate(id=>openScan(id),good.id);
    await tab('prepare');
    await page.getByRole('button',{name:'Fit up to 3 terrace planes'}).click();
    await page.getByRole('button',{name:'Keep result',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>state.scan.history.at(-1).model.plane_count),3);
    assert.equal(await page.evaluate(async()=> (await api('scan',{id:state.scan.id})).operations.length),0);
    await page.getByText('3 fitted planes · proposal',{exact:true}).click();
    await page.getByRole('button',{name:'Inspect fitted planes'}).click();
    await page.waitForSelector('#fit-support');
    assert.equal(await page.locator('#fit-plane').evaluate(c=>c.width/c.height),good.width_um/good.height_um);
    fs.mkdirSync('.test-artifacts',{recursive:true});
    await page.screenshot({path:'.test-artifacts/terrace-fit.png'});
    await page.getByRole('button',{name:'Close dialog',exact:true}).click();
    await page.getByRole('button',{name:'Keep result',exact:true}).click();
    await page.waitForFunction(()=>!state.pending&&!state.loading);
    await page.reload();await page.waitForSelector('.scan-card');
    await page.evaluate(id=>openScan(id),good.id);
    assert.equal(await page.evaluate(()=>state.scan.history[0].model.plane_count),3);
    await tab('record');
    await page.getByRole('button',{name:'Undo last correction',exact:true}).click();
    await page.waitForFunction(()=>!state.loading&&state.scan.operations.length===0);
    await tab('prepare');
    await page.locator('#auto-line-correction').uncheck();
    await page.getByRole('button',{name:'Fit up to 3 terrace planes'}).click();
    await page.getByRole('button',{name:'Keep result',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>state.scan.history.at(-1).model.line_correction.enabled),false);
    await page.getByRole('button',{name:'Discard',exact:true}).click();
    await page.locator('#auto-line-correction').check();
    await openDetails('more-corrections');
    await page.getByRole('button',{name:'Align scan lines',exact:true}).click();
    await page.getByRole('button',{name:'Keep result',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>state.scan.history.at(-1).model.axis),'rows');
    await page.getByRole('button',{name:'Discard',exact:true}).click();
    await page.evaluate(id=>openScan(id),bad.id);
    await tab('prepare');
    await page.getByRole('button',{name:'Fit up to 3 terrace planes'}).click();
    await page.locator('[role="alert"]').waitFor();
    assert.match(await page.locator('[role="alert"]').innerText(),/limit of 3|1–3/);
    assert.equal(await page.evaluate(()=>state.pending),null);
    assert.equal(await page.evaluate(async()=> (await api('scan',{id:state.scan.id})).operations.length),0);
    assert(await page.getByRole('button',{name:'Subtract reference plane',exact:true}).isVisible());
    await page.locator('.canvas-toolbar').getByRole('button',{name:'Area',exact:true}).click();
    const box=await page.locator('#draw-overlay').boundingBox();
    await page.mouse.move(box.x+box.width*.02,box.y+box.height*.1);await page.mouse.down();
    await page.mouse.move(box.x+box.width*.12,box.y+box.height*.9,{steps:8});await page.mouse.up();
    await page.waitForFunction(()=>!!state.area&&!state.loading);
    await tab('prepare');
    await page.getByRole('button',{name:'Subtract reference plane',exact:true}).click();
    await page.getByRole('button',{name:'Keep result',exact:true}).waitFor();
    assert(await page.evaluate(()=>!!state.pending.at(-1).roi));
    await page.screenshot({path:'.test-artifacts/manual-level-fallback.png'});
    assert.deepEqual(errors,[]);
    console.log('PASS: capped fit, fit inspection, preview isolation, save/reopen, undo, metadata-directed alignment, failure leaves data unchanged, manual ROI fallback.');
  }finally{if(browser)await browser.close();fs.rmSync(folder,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1);});
