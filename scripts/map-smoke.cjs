/* Synthetic overlap regression checks, using an isolated demo workspace.
   AFM_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/map-smoke.cjs URL [browser-executable]
   The fixtures replace browser metadata only; no catalog or original-file writes. */
const {chromium}=require(process.env.AFM_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const output=path.resolve('.test-artifacts/map-overlap');
fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    await page.addInitScript(() => localStorage.setItem('afm-auto-prepare', 'false')); // Exercise explicit corrections; automatic preparation has its own smoke test.
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    await page.goto(process.argv[2]||'http://127.0.0.1:8786');
    await page.waitForSelector('.acquisition-card');
    const baseline=await page.evaluate(()=>{
      if(!state.session.synthetic)throw new Error('Use a dedicated synthetic workspace.');
      const scans=state.session.scans,base=primaryScan(scans),back=scans.find(s=>s.direction==='Backward');
      const make=(acquisition,x,y,w,h,angle=0,source=base)=>({...source,acquisition,width_um:w,height_um:h,
        position:{x_um:x,y_um:y,reference:'center',rotation_deg:angle,calibrated:true}});
      const fixtures=[make('001',0,0,40,40),make('002',0,0,8,8),make('003',0,0,8,8),
        make('003',0,0,8,8,0,back),make('004',12,6,30,4,45),make('005',-35,20,6,6),
        {...make('006',0,0,5,5),position:{calibrated:false}}];
      state.session={...state.session,name:'Synthetic overlapping footprints',scans:fixtures};
      state.tab='map';renderContent();
      return JSON.stringify(fixtures);
    });
    const rows=()=>page.locator('.map-aside [data-action="map-select"]');
    assert.equal(await rows().count(),5,'unpositioned scans are omitted');
    assert.equal(await page.locator('.map-image').count(),1,'focus displays one image');
    assert.equal(await page.locator('.map-hit').count(),5,'all footprint outlines remain available');
    assert.match(await page.locator('.map-footnote').innerText(),/1 image has no position/);
    await page.locator('[data-action="map-select"][data-key="1"]').click();
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 002/);
    assert.equal(await page.locator('.map-image').getAttribute('data-key'),'1','fully hidden nested scan is reachable');
    await page.getByRole('button',{name:'All images',exact:true}).click();
    assert.equal(await page.locator('.map-image').count(),5);
    assert.equal(await page.locator('.map-image').last().getAttribute('data-key'),'1','selection is brought to front');
    assert.equal(await page.locator('.map-selected-label').count(),1,'one label, no per-footprint label pile');
    await clickMapPoint(page,0,0);
    assert.equal(await page.locator('.modal [data-action="map-select"]').count(),3,'coincident and nested scans all appear');
    assert.match(await page.locator('.modal h2').innerText(),/3 scans/);
    await page.screenshot({path:path.join(output,'overlap-chooser.png')});
    await page.locator('.modal [data-key="2"]').click();
    assert.equal(await page.locator('.modal').count(),0);
    assert.equal(await page.locator('.map-image').last().getAttribute('data-key'),'2');
    await page.getByRole('button',{name:/Open channels/}).click();
    assert.equal(await page.locator('.modal [data-action="open-map-image"]').count(),2,'directions stay under one acquisition');
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Outlines',exact:true}).click();
    assert.equal(await page.locator('.map-image').count(),0);
    await clickMapPoint(page,18,12);
    assert.equal(await page.locator('.modal [data-action="map-select"]').count(),2,'rotated footprint hit is included');
    await page.keyboard.press('Escape');
    await clickMapPoint(page,22,-2);
    assert.equal(await page.locator('.modal').count(),0,'empty rotated bounding-box corner is excluded');
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 003/,'empty space does not select a false hit');
    const boundaries=await page.evaluate(()=>{
      const g={x:10,y:-4,w:20,h:4,angle:45},a=Math.PI/4;
      return [mapContains(g,10+10*Math.cos(a)-2*Math.sin(a),-4+10*Math.sin(a)+2*Math.cos(a)),
        mapContains(g,10-2.01*Math.sin(a),-4+2.01*Math.cos(a))];
    });
    assert.deepEqual(boundaries,[true,false],'rotated edge included, outside point excluded');
    const hit=page.locator('.map-hit[data-key="4"]');
    await hit.focus();await page.keyboard.press('Enter');
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 005/,'keyboard chooses its focused footprint');
    assert.equal(await page.locator('.modal').count(),0);
    await page.getByRole('button',{name:'Focus',exact:true}).click();
    await page.locator('.map-aside [data-key="2"]').click();
    await page.locator('#direction-filter').selectOption('Backward');
    assert.equal(await rows().count(),1);
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 003.*Backward/);
    await page.locator('#direction-filter').selectOption('all');
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 003/,'selection identity survives filtered group indexes');
    await page.locator('#acquisition-filter').selectOption('006');
    assert.match(await page.locator('.empty-state').innerText(),/No calibrated positions/);
    await page.locator('#acquisition-filter').selectOption('all');
    await page.locator('.map-aside [data-key="1"]').click();
    for(const viewport of [{width:1440,height:1000},{width:900,height:650},{width:700,height:850}]){
      await page.setViewportSize(viewport);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow');
      await page.locator('[data-action="map-zoom"][data-value="in"]').click();
      await clickMapPoint(page,0,0);
      assert.equal(await page.locator('.modal [data-action="map-select"]').count(),3,'zoomed hit test handles SVG letterboxing');
      await page.locator('.modal [data-key="1"]').click();
      const aside=await page.locator('.map-aside').boundingBox(),channels=await page.locator('.map-channels').boundingBox();
      assert(channels.y>=aside.y&&channels.y+channels.height<=aside.y+aside.height,'selected channel control stays inside the scrollable list');
      await page.locator('[data-action="map-zoom"][data-value="fit"]').click();
      await page.screenshot({path:path.join(output,`focus-${viewport.width}.png`)});
    }
    await page.setViewportSize({width:1440,height:1000});
    assert.equal(await page.evaluate(()=>JSON.stringify(state.session.scans)),baseline,'map operations leave metadata and recipes unchanged');
    await page.evaluate(()=>{
      const g=state.session.scans.find(s=>s.acquisition==='005');
      state.session.scans=state.session.scans.map(s=>s===g?{...s,channel:'Error Signal',direction:'Backward'}:s);
      renderContent();
    });
    await page.locator('.map-aside [data-key="4"]').click();
    assert.match(await page.locator('.map-selected-label').innerText(),/Z height unavailable.*Error Signal.*Backward/,'fallback channel is explicit');
    await page.locator('#channel-filter').selectOption('Error Signal');
    assert.doesNotMatch(await page.locator('.map-selected-label').innerText(),/unavailable/,'an explicit channel choice is not reported as missing height');
    await page.locator('#channel-filter').selectOption('overview');
    await page.evaluate(saved=>{state.session.scans=JSON.parse(saved);renderContent();},baseline);
    await page.locator('.map-aside [data-key="2"]').click();
    await page.getByRole('button',{name:/Open channels/}).click();
    await page.locator('.modal [data-action="open-map-image"]').first().click();
    await page.waitForSelector('#height-canvas');
    assert.equal(await page.locator('.modal').count(),0,'channel chooser opens the analysis view');
    assert.deepEqual(errors,[],'no browser errors');
    console.log(JSON.stringify({passed:true,checks:['nested and coincident acquisitions','rotated hits and boundaries','empty-space rejection','focus/all/outlines modes','selected layer in front','single label','channel and direction access','keyboard selection','stable filtered identity','missing positions','explicit height fallback','zoom and letterbox coordinates','desktop and compact layouts','unchanged metadata and recipes'],screenshots:output},null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
async function clickMapPoint(page,x,y){
  const p=await page.locator('.map-panel>svg').evaluate((svg,{x,y})=>{
    const point=svg.createSVGPoint();
    point.x=400+(x-Number(svg.dataset.centerX))*Number(svg.dataset.scale);
    point.y=280-(y-Number(svg.dataset.centerY))*Number(svg.dataset.scale);
    const screen=point.matrixTransform(svg.getScreenCTM());return {x:screen.x,y:screen.y};
  },{x,y});
  await page.mouse.click(p.x,p.y);
}
