/* Synthetic UI regression for task navigation, precision and compact layout.
   AFM_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/inspector-smoke.cjs URL [browser executable] */
const {chromium}=require(process.env.AFM_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
  try {
    const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[];
    await page.addInitScript(() => localStorage.setItem('afm-auto-prepare', 'false')); // Exercise explicit corrections; automatic preparation has its own smoke test.
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.argv[2]||'http://127.0.0.1:8792');
    await page.waitForSelector('.session-heading,.empty-state');
    const id=await page.evaluate(async()=>{
      const session=await api('demo');await openSession(session.id);
      const id=session.scans.find(s=>s.channel==='Z Height'&&s.direction==='Forward').id;
      await api('process',{id,operations:[]});await api('edit_mask',{id,action:'clear'});
      await api('update_mask',{id,masking:'exclude',visible:true});
      await api('set_display',{id,settings:{palette:'amber',mode:'full',clip_percent:0}});
      await openScan(id);return id;
    });
    const idle=()=>page.waitForFunction(()=>!state.loading);
    const tab=name=>page.locator('#inspector-tab-'+name).click();
    const button=selector=>page.locator(selector).click();
    const draw=async(a,b)=>{
      const box=await page.locator('#draw-overlay').boundingBox();
      await page.mouse.move(box.x+box.width*a[0],box.y+box.height*a[1]);await page.mouse.down();
      await page.mouse.move(box.x+box.width*b[0],box.y+box.height*b[1],{steps:8});await page.mouse.up();await idle();
    };
    assert.equal(await page.locator('.inspector-panel:visible').count(),1);
    // Keyboard tab navigation must not advance to a different AFM acquisition.
    await tab('view');await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#inspector-tab-prepare').getAttribute('aria-selected'),'true');
    assert.equal(await page.evaluate(()=>state.scan.id),id);
    await page.keyboard.press('End');assert.equal(await page.locator('#inspector-tab-record').getAttribute('aria-selected'),'true');
    await page.keyboard.press('Home');assert.equal(await page.locator('#inspector-tab-view').getAttribute('aria-selected'),'true');
    // Fields may be formatted, but committing an untouched endpoint must not round it.
    const exact=[-1269.35780187654,-1193.17031323568];
    await page.locator('#color-min-input').fill(String(exact[0]));await page.locator('#color-max-input').fill(String(exact[1]));
    await button('[data-display-action=manual]');await page.evaluate(()=>AFMDisplay.pending());
    await page.locator('#color-min-input').fill('-1268.25');await page.locator('#color-min-input').press('Enter');await page.evaluate(()=>AFMDisplay.pending());
    assert.equal(await page.evaluate(()=>AFMDisplay.range()[1]),exact[1]);
    assert.equal(await page.evaluate(()=>AFMDisplay.range()[0]),-1268.25);
    await page.locator('#color-max-input').press('ArrowLeft');assert.equal(await page.evaluate(()=>state.scan.id),id);
    // A single focused thumb is adjustable with a keyboard; display leaves numerical results intact.
    const original=await page.evaluate(()=>state.scan.statistics);
    await button('#display-controls [data-display-action=full]');await page.evaluate(()=>AFMDisplay.pending());
    await page.locator('#color-lower-slider').focus();await page.keyboard.press('ArrowRight');await page.evaluate(()=>AFMDisplay.pending());
    assert.equal(await page.evaluate(()=>AFMDisplay.settings().mode),'manual');
    const firstLimit=await page.evaluate(()=>AFMDisplay.range()[0]);
    await page.keyboard.press('ArrowRight');await page.evaluate(()=>AFMDisplay.pending());
    assert.equal(await page.evaluate(()=>document.activeElement.id),'color-lower-slider');
    assert.equal(await page.evaluate(()=>state.scan.id),id);
    assert((await page.evaluate(()=>AFMDisplay.range()[0]))>firstLimit,'repeated keyboard range adjustments keep working');
    assert.deepEqual(await page.evaluate(()=>state.scan.statistics),original);
    await page.locator('#height-canvas').focus();await page.keyboard.press('m');
    assert.equal(await page.evaluate(()=>state.inspectorTab),'prepare');assert.equal(await page.evaluate(()=>state.tool),'mask');
    await button('[data-mask-shape=brush]');await button('[data-mask-edit=erase]');
    await tab('view');await tab('prepare');
    assert.equal(await page.locator('[data-mask-shape=brush]').getAttribute('aria-pressed'),'true');
    assert.equal(await page.locator('[data-mask-edit=erase]').getAttribute('aria-pressed'),'true');
    await page.locator('#height-canvas').focus();await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>state.tool),'inspect');assert.equal(await page.evaluate(()=>state.view),'detail');
    // Selecting an area for a fit survives task navigation and range selection.
    await button('[data-tool=area][data-panel=prepare]');await draw([.1,.1],[.3,.3]);
    const roi=await page.evaluate(()=>state.area.roi);
    await page.locator('#reference-mode').selectOption('exclude');
    assert.match(await page.locator('.fit-reference strong').innerText(),/Outside selected area/);
    assert.match(await page.locator('.inspector-footer').innerText(),/Reference: Outside selected area/);
    await tab('measure');assert.match(await page.locator('.measurement-tools .operation-note').first().innerText(),/inside selected area/);
    await tab('prepare');await page.locator('#reference-mode').selectOption('include');
    await tab('view');assert.equal(await page.locator('[data-display-action=roi]').isDisabled(),false);
    await button('[data-display-action=roi]');await page.evaluate(()=>AFMDisplay.pending());
    await tab('prepare');assert.deepEqual(await page.evaluate(()=>state.area.roi),roi);
    // Disclosures and scroll position survive tab switches and inspector rerenders.
    await page.locator('#more-corrections summary').click();
    await page.locator('#inspector-panel-prepare').evaluate(e=>e.scrollTop=e.scrollHeight);
    const scroll=await page.locator('#inspector-panel-prepare').evaluate(e=>e.scrollTop);
    await tab('view');await tab('prepare');
    assert.equal(await page.locator('#more-corrections').evaluate(e=>e.open),true);
    assert.equal(await page.locator('#inspector-panel-prepare').evaluate(e=>e.scrollTop),scroll);
    await page.locator('#polynomial-mode').selectOption('total');
    assert.equal(await page.locator('#more-corrections').evaluate(e=>e.open),true);
    // Preview decisions remain outside the scrollable panel, including on the smallest desktop window.
    await button('[data-operation=plane]');await page.waitForSelector('[data-action=apply-preview]');await idle();
    assert.match(await page.locator('.inspector-footer').innerText(),/Selected area/,'preview retains the saved operation reference after drawing is cleared');
    await page.setViewportSize({width:900,height:650});await tab('record');
    await page.locator('#inspector-panel-record').evaluate(e=>e.scrollTop=e.scrollHeight);
    for(const selector of ['.inspector-nav','.preview-decision','.inspector-footer','#height-canvas']) {
      const b=await page.locator(selector).boundingBox();assert(b&&b.x>=0&&b.y>=0&&b.x+b.width<=901&&b.y+b.height<=651,selector+' stays visible');
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    fs.mkdirSync('.test-artifacts',{recursive:true});
    await page.screenshot({path:'.test-artifacts/inspector-preview-compact.png'});
    await button('[data-action=discard-preview]');await idle();
    // Actual profile survives inspector navigation; keyboard shortcut opens matching controls.
    await page.locator('#height-canvas').focus();await page.keyboard.press('p');
    await draw([.1,.5],[.8,.5]);await page.waitForSelector('#profile-panel svg');
    const selection=await page.evaluate(()=>state.profile.selection);
    await tab('view');await tab('measure');assert.deepEqual(await page.evaluate(()=>state.profile.selection),selection);
    await page.locator('#height-canvas').focus();await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>state.tool),'inspect');
    assert.deepEqual(await page.evaluate(()=>state.profile.selection),selection,'leaving drawing preserves the measured profile');
    assert(await page.locator('#profile-panel svg').isVisible());
    assert.deepEqual(errors,[]);
    console.log('PASS: workflow keyboard access, exact numeric limits, range keyboard input, mask tool retention, ROI/profile retention, disclosure/scroll retention, fixed preview decisions, compact layout.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
