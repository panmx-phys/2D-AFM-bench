/* Synthetic map regression checks, using an isolated demo workspace.
   AFM_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/map-smoke.cjs URL [browser-executable]
   Fixtures replace browser metadata only; no experimental catalog writes. */
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
    await page.addInitScript(()=>{localStorage.setItem('afm-auto-prepare','false');localStorage.removeItem('afm-map-opacity');});
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    await page.goto(process.argv[2]||'http://127.0.0.1:8786');
    await page.waitForSelector('.acquisition-card');
    const baseline=await page.evaluate(()=>{
      if(!state.session.synthetic)throw new Error('Use a dedicated synthetic workspace.');
      const scans=state.session.scans,base=primaryScan(scans),back=scans.find(s=>s.direction==='Backward');
      const make=(acquisition,x,y,w,h,angle=0,source=base)=>{
        const position={x_um:x,y_um:y,reference:'center',rotation_deg:angle,calibrated:true};
        return {...source,acquisition,width_um:w,height_um:h,position,map_footprint:position};
      };
      const fixtures=[make('001',0,0,40,40),make('002',0,0,8,8),make('003',0,0,8,8),
        make('003',0,0,8,8,0,back),make('004',12,6,30,4,45),make('005',-35,20,6,6),
        {...make('006',0,0,5,5),position:{calibrated:false},map_footprint:null}];
      state.session={...state.session,name:'Synthetic overlapping footprints',scans:fixtures};
      state.tab='map';renderContent();return JSON.stringify(fixtures);
    });
    const rows=()=>page.locator('.map-aside [data-action="map-select"]');
    const select=i=>page.locator(`.map-aside [data-action="map-select"][data-key="${i}"]`).click();
    const all=()=>page.getByRole('button',{name:'All images',exact:true}).click();
    assert.equal(await rows().count(),6,'every acquisition stays accessible');
    assert.equal(await page.locator('.map-image').count(),5,'all placed images shown by default');
    assert.equal(await page.locator('.map-hit').count(),5);
    assert.equal(await page.locator('.map-selected-label').count(),0,'no implicit first selection');
    assert.equal(await page.locator('.map-image').first().getAttribute('opacity'),'0.75');
    assert.match(await page.locator('.map-hint').innerText(),/5 on map · 1 not placed/);
    assert.equal(await page.locator('.map-unplaced-card').count(),1);
    await page.getByLabel('Map image opacity').fill('40');
    assert(await page.locator('.map-image').evaluateAll(images=>images.every(i=>i.getAttribute('opacity')==='0.4')));
    assert.equal(await page.locator('.map-opacity output').innerText(),'40%');
    await page.screenshot({path:path.join(output,'all-images.png')});
    await select(1);
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 002/);
    assert.equal(await page.locator('.map-image').count(),1);
    assert.equal(await page.locator('.map-image').getAttribute('opacity'),'1','focus stays opaque');
    assert.equal(await page.locator('.map-image').getAttribute('data-key'),'1','hidden nested scan reachable');
    await select(1);
    assert.equal(await page.locator('.map-image').count(),5,'second click returns to overview');
    assert.equal(await page.locator('.map-image').first().getAttribute('opacity'),'0.4','opacity survives focus');
    await clickMapPoint(page,0,0);
    assert.equal(await page.locator('.modal [data-action="map-select"]').count(),3,'all coincident/nested hits');
    await page.screenshot({path:path.join(output,'overlap-chooser.png')});
    await page.locator('.modal [data-key="2"]').click();
    assert.equal(await page.locator('.map-image').getAttribute('data-key'),'2');
    await page.getByRole('button',{name:/Open channels/}).click();
    assert.equal(await page.locator('.modal [data-action="open-map-image"]').count(),2,'directions stay together');
    await page.keyboard.press('Escape');
    await clickMapPoint(page,0,0);
    assert.equal(await page.locator('.modal').count(),0,'focused overlap can be unclicked directly');
    assert.equal(await page.locator('.map-image').count(),5);
    await select(2);await clickMapPoint(page,22,-2);
    assert.equal(await page.locator('.map-image').count(),5,'empty corner outside rotated footprint clears focus');
    await select(2);await page.keyboard.press('Escape');
    assert.equal(await page.locator('.map-image').count(),5,'Escape restores overview');
    await page.getByRole('button',{name:'Outlines',exact:true}).click();
    assert.equal(await page.locator('.map-image').count(),0);
    await clickMapPoint(page,18,12);
    assert.equal(await page.locator('.modal [data-action="map-select"]').count(),2,'rotated hit included');
    await page.keyboard.press('Escape');
    await clickMapPoint(page,22,-2);
    assert.equal(await page.locator('.modal').count(),0,'rotated bounding-box corner excluded');
    const geometry=await page.evaluate(()=>{
      const g={placed:true,x:10,y:-4,w:20,h:4,angle:45},a=Math.PI/4,s=state.session.scans[0];
      return {edges:[mapContains(g,10+10*Math.cos(a)-2*Math.sin(a),-4+10*Math.sin(a)+2*Math.cos(a)),
        mapContains(g,10-2.01*Math.sin(a),-4+2.01*Math.cos(a))],
        invalid:[NaN,Infinity,null,'0'].map(rotation_deg=>position({...s,map_footprint:{...s.map_footprint,rotation_deg}})),
        corner:position({...s,width_um:20,height_um:4,map_footprint:{...s.map_footprint,x_um:10,y_um:-4,reference:'corner',rotation_deg:90}})};
    });
    assert.deepEqual(geometry.edges,[true,false]);assert.deepEqual(geometry.invalid,[null,null,null,null]);
    assert(Math.abs(geometry.corner.x-8)<1e-9&&Math.abs(geometry.corner.y-6)<1e-9,'rotated corner converted to center');
    await page.locator('.map-hit[data-key="4"]').focus();await page.keyboard.press('Enter');
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 005/);
    await page.locator('.map-hit[data-key="4"]').focus();await page.keyboard.press('Space');
    assert.equal(await page.locator('.map-image').count(),5,'keyboard toggles focus');
    await select(2);await page.locator('#direction-filter').selectOption('Backward');
    assert.equal(await rows().count(),1);
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 003.*Backward/);
    await page.locator('#direction-filter').selectOption('all');
    assert.match(await page.locator('.map-selected-label').innerText(),/Scan 003/,'stable selection through filtering');
    await page.locator('#acquisition-filter').selectOption('006');
    assert.equal(await rows().count(),1);assert.equal(await page.locator('.map-unplaced-card').count(),1);
    assert.equal(await page.locator('.map-selected-label').count(),0,'filtered-out selection is cleared');
    await select(0);
    assert.equal(await page.locator('.map-unplaced-preview img').count(),1,'unplaced scan can be focused');
    await page.getByRole('button',{name:/Open channels/}).click();
    assert.equal(await page.locator('.modal [data-action="open-map-image"]').count(),1);
    await page.keyboard.press('Escape');await select(0);
    await page.locator('#acquisition-filter').selectOption('all');
    await page.locator('[data-action="starred-filter"]').click();
    assert.match(await page.locator('.empty-state').innerText(),/No matching images/);
    await page.getByRole('button',{name:'Reset filters',exact:true}).click();
    for(const viewport of [{width:1440,height:1000},{width:900,height:650},{width:700,height:850}]){
      await all();await page.setViewportSize(viewport);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow');
      await page.locator('[data-action="map-zoom"][data-value="in"]').click();
      await clickMapPoint(page,0,0);
      assert.equal(await page.locator('.modal [data-action="map-select"]').count(),3,'zoom and letterbox hit test');
      await page.locator('.modal [data-key="1"]').click();
      const aside=await page.locator('.map-aside').boundingBox(),channels=await page.locator('.map-channels').boundingBox();
      assert(channels.y>=aside.y&&channels.y+channels.height<=aside.y+aside.height,'channel control in scrollable list');
      await page.locator('[data-action="map-zoom"][data-value="fit"]').click();
      await page.screenshot({path:path.join(output,`focus-${viewport.width}.png`)});
    }
    await page.setViewportSize({width:1440,height:1000});
    assert.equal(await page.evaluate(()=>JSON.stringify(state.session.scans)),baseline,'metadata/recipes unchanged');
    await page.evaluate(()=>{
      state.session.scans=state.session.scans.map(s=>s.acquisition==='005'?{...s,channel:'Error Signal',direction:'Backward'}:s);renderContent();
    });
    await select(4);
    assert.match(await page.locator('.map-selected-label').innerText(),/Z height unavailable.*Error Signal.*Backward/);
    await page.locator('#channel-filter').selectOption('Error Signal');
    assert.doesNotMatch(await page.locator('.map-selected-label').innerText(),/unavailable/);
    await page.locator('#channel-filter').selectOption('overview');
    await page.evaluate(saved=>{state.session.scans=JSON.parse(saved);renderContent();},baseline);
    await select(2);await page.getByRole('button',{name:/Open channels/}).click();
    await page.locator('.modal [data-action="open-map-image"]').first().click();
    await page.waitForSelector('#height-canvas');
    assert.equal(await page.locator('.modal').count(),0);
    await page.evaluate(()=>openSession(state.session.id));
    assert.equal(await page.evaluate(()=>state.mapMode),'all','opening session resets focus');
    assert.equal(await page.evaluate(()=>state.mapSelected),null);
    assert.deepEqual(errors,[],'no browser errors');
    console.log(JSON.stringify({passed:true,checks:['all images default','opacity display only','click and keyboard focus/deselect','overlap chooser','rotated hits and corner origins','invalid geometry','filters and stable identity','unplaced gallery and channels','empty results','responsive layouts','unchanged metadata and recipes','session reset'],screenshots:output},null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
async function clickMapPoint(page,x,y){
  const p=await page.locator('.map-panel>svg').evaluate((svg,{x,y})=>{
    const point=svg.createSVGPoint();point.x=400+(x-Number(svg.dataset.centerX))*Number(svg.dataset.scale);
    point.y=280-(y-Number(svg.dataset.centerY))*Number(svg.dataset.scale);
    const screen=point.matrixTransform(svg.getScreenCTM());return {x:screen.x,y:screen.y};
  },{x,y});await page.mouse.click(p.x,p.y);
}
