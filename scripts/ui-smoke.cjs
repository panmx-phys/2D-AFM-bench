/* Run against a dedicated synthetic workspace, never against an active lab catalog.
   npm install --no-save playwright
   node scripts/ui-smoke.cjs http://127.0.0.1:8765 [browser-executable]
   Uses AFM_PLAYWRIGHT_MODULE when an existing installation is available. */
const { chromium } = require(process.env.AFM_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const output = path.resolve('.test-artifacts');
fs.mkdirSync(output, {recursive:true});
(async () => {
  const browser = await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
  const page = await browser.newPage({viewport:{width:1440,height:1040},deviceScaleFactor:1});
  await page.addInitScript(() => localStorage.setItem('afm-auto-prepare', 'false')); // Exercise explicit corrections; automatic preparation has its own smoke test.
  const errors=[];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => {if(msg.type()==='error') errors.push(msg.text());});
  const call = (method,payload={}) => page.evaluate(async({method,payload})=>{
    const r = await fetch('/api/'+method,{method:'POST',headers:{'Content-Type':'application/json','X-AFM-Token':document.querySelector('meta[name="afm-token"]').content},body:JSON.stringify(payload)});
    const result=await r.json();if(!r.ok) throw new Error(JSON.stringify(result));return result;
  },{method,payload});
  await page.goto(base);
  await page.waitForSelector('.session-heading,.empty-state');
  let boot = await call('bootstrap');
  if(!boot.sessions.length){await page.locator('[data-action="demo"]').click();await page.waitForSelector('.scan-card');}
  boot=await call('bootstrap');
  assert(boot.sessions.length>=1,'session exists');
  const session=await call('session',{id:boot.active_session_id||boot.sessions[0].id});
  assert(session.synthetic,'UI mutation test must run on a synthetic workspace');
  const forwardHeights=session.scans.filter(s=>s.channel==='Z Height'&&s.direction==='Forward');
  assert.equal(await page.locator('#channel-filter').inputValue(),'overview','session opens in height overview');
  assert.equal(await page.locator('.primary-scan .scan-card').count(),forwardHeights.length,'one primary height per acquisition');
  const primaryIds=await page.locator('.primary-scan .scan-card').evaluateAll(cards=>cards.map(c=>c.dataset.scanCard).sort());
  assert.deepEqual(primaryIds,forwardHeights.map(s=>s.id).sort(),'forward Z height is the default image');
  await checkGroupingFixtures(page,session.scans[0]);
  await page.waitForFunction(()=>[...document.querySelectorAll('.card-image-button img')].filter(i=>i.getBoundingClientRect().top<innerHeight).every(i=>i.complete&&i.naturalWidth>0));
  await page.screenshot({path:path.join(output,'contact-sheet.png'),fullPage:false});
  const backwardScan=session.scans.find(s=>s.direction==='Backward');
  await page.locator('#global-search').fill(backwardScan.filename);
  await page.waitForFunction(id=>{
    const cards=document.querySelectorAll('.scan-card');
    return cards.length===1&&cards[0].dataset.scanCard===id;
  },backwardScan.id);
  assert.equal(await page.locator('#channel-filter').inputValue(),'overview','search can reach backward images from the default mode');
  await page.locator('#global-search').fill('');
  await page.waitForSelector('.acquisition-card');
  try{
    await call('update_scan',{id:backwardScan.id,starred:true});
    await page.reload();
    await page.waitForSelector('.acquisition-card');
    await page.locator('[data-action="starred-filter"]').click();
    const starredIds=await page.locator('.scan-card').evaluateAll(cards=>cards.map(c=>c.dataset.scanCard).sort());
    const currentSession=await call('session',{id:session.id});
    assert.deepEqual(starredIds,currentSession.scans.filter(s=>s.starred).map(s=>s.id).sort(),'starred filter shows exact images, including backward signals');
    assert(starredIds.includes(backwardScan.id),'starred backward image remains visible');
  }finally{
    await call('update_scan',{id:backwardScan.id,starred:backwardScan.starred});
    await page.reload();
    await page.waitForSelector('.acquisition-card');
  }
  const signal=page.locator('.related-signal').first();
  const signalId=await signal.getAttribute('data-id');
  const signalScan=session.scans.find(s=>s.id===signalId);
  assert.equal(signalScan.direction,'Forward','auxiliary signal matches height direction');
  await signal.click();
  await page.waitForSelector('#height-canvas');
  assert.equal(await page.locator('#related-scan').inputValue(),signalId,'auxiliary signal opens directly');
  const correspondingHeight=forwardHeights.find(s=>s.acquisition===signalScan.acquisition);
  assert.equal(await page.locator('.channel-strip').count(),0,'detail channel ribbon is removed');
  await page.locator('#related-scan').selectOption(correspondingHeight.id);
  await page.waitForFunction(id=>document.getElementById('related-scan')?.value===id,correspondingHeight.id);
  await page.keyboard.press('Escape');
  await page.waitForSelector('.acquisition-card');
  await page.getByRole('button',{name:'Sample map',exact:true}).click();
  await page.waitForSelector('.map-hit');
  assert(await page.locator('.map-location').count()>=2,'map has multiple acquisition locations');
  await page.screenshot({path:path.join(output,'sample-map.png')});
  await page.locator('.map-location').first().click();
  await page.getByRole('button',{name:/Open channels/}).click();
  assert(await page.locator('.modal .map-location').count()>=1,'map reveals channels');
  await page.getByRole('button',{name:'Close dialog',exact:true}).click();
  await page.getByRole('button',{name:/Contact sheet/}).click();
  await page.locator('#channel-filter').selectOption('all');
  const allIds=await page.locator('.scan-card').evaluateAll(cards=>cards.map(c=>c.dataset.scanCard).sort());
  assert.deepEqual(allIds,session.scans.map(s=>s.id).sort(),'all folder images remain accessible together');
  await page.locator('#direction-filter').selectOption('Backward');
  const backwards=session.scans.filter(s=>s.direction==='Backward').length;
  assert.equal(await page.locator('.scan-card').count(),backwards);
  await page.locator('#direction-filter').selectOption('all');
  await page.locator('.card-select').nth(0).check({force:true});
  await page.locator('.card-select').nth(1).check({force:true});
  await page.getByRole('button',{name:'Compare images',exact:true}).click();
  await page.waitForSelector('.compare-image');
  assert.equal(await page.locator('.compare-image').count(),2);
  await page.screenshot({path:path.join(output,'compare.png')});
  await page.keyboard.press('Escape');
  await page.waitForSelector('.scan-card');
  const id=await page.locator('.card-image-button').first().getAttribute('data-id');
  const before=await call('scan',{id});
  await page.locator('.card-image-button').first().click();
  await page.waitForSelector('#height-canvas');
  await page.locator('[data-display-action=auto]').first().click();
  await page.evaluate(()=>AFMDisplay.pending());
  const afterContrast=await call('scan',{id});
  assert.deepEqual(afterContrast.statistics,before.statistics,'contrast must not change numerical data');
  await page.locator('#inspector-tab-prepare').click();
  await page.locator('[data-operation=plane]').click();
  await page.getByRole('button',{name:'Keep result',exact:true}).waitFor();
  const duringPreview=await call('scan',{id});
  assert.deepEqual(duringPreview.operations,before.operations,'preview must not mutate recipe');
  const pendingBefore=await page.evaluate(()=>JSON.stringify(state.pending));
  await page.locator('#related-scan').dispatchEvent('change');
  await page.waitForFunction(()=>!state.loading);
  assert.equal(await page.evaluate(()=>JSON.stringify(state.pending)),pendingBefore,'clicking active channel preserves unsaved preview');
  assert(await page.getByRole('button',{name:'Keep result',exact:true}).isVisible(),'unsaved preview controls remain available');
  await page.getByRole('button',{name:'Keep result',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('[data-action="apply-preview"]'));
  const applied=await call('scan',{id});
  assert.equal(applied.operations.length,before.operations.length+1,'saved correction');
  await page.getByRole('button',{name:'Profile',exact:true}).click();
  const box=await page.locator('#draw-overlay').boundingBox();
  await page.mouse.move(box.x+box.width*.2,box.y+box.height*.3);
  await page.mouse.down();
  await page.mouse.move(box.x+box.width*.8,box.y+box.height*.7,{steps:10});
  await page.mouse.up();
  await page.waitForSelector('#profile-panel svg path');
  const profileBefore=await page.locator('#profile-panel svg path').getAttribute('d');
  await page.locator('#related-scan').dispatchEvent('change');
  await page.waitForFunction(()=>!state.loading);
  assert.equal(await page.locator('#profile-panel svg path').getAttribute('d'),profileBefore,'clicking active channel preserves the measured profile');
  await page.screenshot({path:path.join(output,'analysis.png')});
  await page.locator('#inspector-tab-record').click();
  await page.getByRole('button',{name:'Undo last correction',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.loading-overlay'));
  const undone=await call('scan',{id});
  assert.deepEqual(undone.statistics,before.statistics,'undo replays original data');
  await page.getByRole('button',{name:'Export',exact:true}).click();
  const downloaded=page.waitForEvent('download');
  await page.getByRole('button',{name:/Calibrated data · CSV/}).click();
  const download=await downloaded;
  await download.saveAs(path.join(output,'smoke-export.csv'));
  assert(fs.statSync(path.join(output,'smoke-export.csv')).size>100,'full data exported');
  await page.locator('[data-action=back]').click();
  await page.waitForSelector('.scan-card');
  await page.locator('[data-action="notes"]').click();
  await page.locator('#session-notes').fill('Synthetic UI smoke test — persisted notes.');
  await page.getByRole('button',{name:'Save notes',exact:true}).click();
  await page.reload();
  await page.waitForSelector('.scan-card');
  const reopened=await call('session',{id:session.id});
  assert.equal(reopened.notes,'Synthetic UI smoke test — persisted notes.');
  await page.setViewportSize({width:1000,height:760});
  await page.screenshot({path:path.join(output,'compact-window.png')});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'no horizontal page overflow');
  // Use a fresh viewport so headless compositor resize artifacts do not obscure layout QA.
  const minimumPage=await browser.newPage({viewport:{width:900,height:650},deviceScaleFactor:1});
  await minimumPage.addInitScript(() => localStorage.setItem('afm-auto-prepare', 'false')); // Exercise explicit corrections; automatic preparation has its own smoke test.
  minimumPage.on('pageerror',e=>errors.push(e.message));
  minimumPage.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text());});
  await minimumPage.goto(base);
  await minimumPage.waitForSelector('.acquisition-card');
  await minimumPage.waitForFunction(()=>[...document.querySelectorAll('.card-image-button img')].filter(i=>i.getBoundingClientRect().top<innerHeight).every(i=>i.complete&&i.naturalWidth>0));
  await minimumPage.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await minimumPage.screenshot({path:path.join(output,'minimum-window.png')});
  assert.equal(await minimumPage.locator('.app-shell').count(),1,'one application shell is rendered');
  assert.equal(await minimumPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'no horizontal overflow at minimum native window width');
  await minimumPage.locator('.primary-scan .card-image-button').first().click();
  await minimumPage.waitForSelector('#height-canvas');
  await minimumPage.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await minimumPage.screenshot({path:path.join(output,'minimum-detail.png')});
  assert.equal(await minimumPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'detail has no horizontal overflow at minimum native window width');
  const minimumCanvas=await minimumPage.locator('#height-canvas').boundingBox();
  assert(minimumCanvas&&minimumCanvas.x>=0&&minimumCanvas.y>=0&&minimumCanvas.x+minimumCanvas.width<=900&&minimumCanvas.y+minimumCanvas.height<=650,'whole height canvas fits inside the minimum Inspect viewport');
  assert(Math.abs(minimumCanvas.width/minimumCanvas.height-before.width_um/before.height_um)<.01,'minimum canvas preserves the physical aspect ratio');
  const minimumInspector=await minimumPage.locator('.inspector').boundingBox();
  assert(minimumInspector.y+minimumInspector.height<=650,'inspector is constrained to the visible viewport');
  await minimumPage.locator('#inspector-tab-prepare').click();
  const correction=minimumPage.locator('[data-operation=plane]');
  await correction.scrollIntoViewIfNeeded();
  const correctionBox=await correction.boundingBox();
  assert(correctionBox&&correctionBox.y>=0&&correctionBox.y+correctionBox.height<=650,'correction controls can be scrolled into the minimum viewport');
  assert.equal(await minimumPage.locator('.app-shell').evaluate(el=>el.scrollTop),0,'inspector scrolling does not move the application shell');
  assert.deepEqual(errors,[],'no browser console errors');
  console.log(JSON.stringify({passed:true,images:session.scans.length,checks:['forward height default','exact height priority','matching error direction','missing height fallback','acquisition footprint grouping','backward filename search','exact starred images','all-channel access','related-channel navigation','metadata map','direction filter','comparison','contrast invariance','preview isolation','active channel preserves preview','correction apply','full-resolution profile','active channel preserves profile','undo','CSV export','notes persistence','compact window','minimum native window'],screenshots:output},null,2));
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});

// Render synthetic metadata into an inert template: no files, catalog writes or image requests.
async function checkGroupingFixtures(page,baseScan){
  const groups=await page.evaluate(base=>{
    const make=(id,acquisition,channel,direction,x=0)=>({...base,id,acquisition,channel,direction,
      filename:`${acquisition}_${channel}_${direction}.tiff`,
      position:{x_um:x,y_um:0,reference:'center',rotation_deg:0,calibrated:true}});
    const fixtures=[
      make('generic-height','001','Height','Forward'),
      make('height','001','Z Height','Forward'),
      make('error','001','Height Error','Forward'),
      make('back-error','001','Height Error','Backward'),
      make('fallback','002','Z Height','Backward'),
      make('unmatched-error','002','Height Error','Forward'),
      make('other-position','001','Z Height','Forward',100),
      make('other-position-error','001','Height Error','Forward',100),
      make('phase-only','003','NCM Phase','Forward'),
      make('height-only','004','Z Height','Forward'),
      make('back-error-only','004','Height Error','Backward')
    ];
    const saved={session:state.session,channel:state.channel,direction:state.direction};
    try{
      state.session={...state.session,scans:fixtures};state.channel='overview';state.direction='all';
      const template=document.createElement('template');
      template.innerHTML=renderGrid(fixtures);
      return [...template.content.querySelectorAll('.acquisition-card')].map(card=>({
        primary:card.querySelector('.primary-scan .scan-card')?.dataset.scanCard,
        text:card.textContent,
        related:[...card.querySelectorAll('.related-signal')].map(el=>el.dataset.id),
        accessible:[...card.querySelectorAll('[data-action="open"]')].map(el=>el.dataset.id)
      }));
    }finally{Object.assign(state,saved);}
  },baseScan);
  assert.equal(groups.length,5,'distinct physical footprints do not merge under a reused acquisition number');
  const first=groups.find(g=>g.primary==='height');
  assert(first,'exact Z Height is preferred over generic Height and Height Error');
  assert(first.related.includes('error'),'forward height includes corresponding forward error');
  assert(!first.related.includes('back-error'),'backward error is not presented as a matching forward signal');
  assert(first.accessible.includes('back-error'),'other directions remain accessible');
  assert(first.accessible.includes('generic-height'),'additional height channels remain accessible');
  const fallback=groups.find(g=>g.primary==='fallback');
  assert(fallback,'missing forward height falls back to an available height');
  assert.match(fallback.text,/Backward/,'fallback direction is explicit');
  assert(!fallback.related.includes('unmatched-error'),'fallback height only pairs with its own direction');
  const other=groups.find(g=>g.primary==='other-position');
  assert(other.related.includes('other-position-error'),'error remains paired with its physical footprint');
  assert(!other.related.includes('error'),'signals from another position do not leak into the group');
  assert(groups.some(g=>g.primary==='phase-only'),'acquisitions without a height channel remain visible');
  assert(!groups.find(g=>g.primary==='height-only').related.includes('back-error-only'),'missing forward error is not replaced with backward error');
}
