/* Display preferences only: limits never transform numerical image data. */
'use strict';
window.AFMDisplay = (() => {
  let host, imageId = null, prefs = defaults(), limits = [0, 1], committedLimits = [0, 1], histogram = null;
  let generation = 0, busy = false, work = Promise.resolve(), installed = false, autoOptionsOpen = false, focusIntent = 0, previewPrefs = null;
  let liveFrame = 0;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const numeric = value => finite(value) ? String(value) : '';
  // Rounded field labels are display-only. Untouched fields retain the exact
  // stored limit, including when the opposite endpoint is edited and applied.
  function fieldValue(value) {
    if (!finite(value)) return '';
    let precision = 7;
    // Keep narrow ranges distinguishable even on a large absolute height datum.
    while (precision < 17 && limits[0] !== limits[1] &&
      Number(limits[0].toPrecision(precision)) === Number(limits[1].toPrecision(precision))) precision++;
    return String(Number(value.toPrecision(precision)));
  }
  const concise = value => finite(value) ? Number(value.toPrecision(6)).toLocaleString(undefined, {maximumSignificantDigits:6}) : '—';
  function defaults() { return {palette:'amber', mode:'full', clip_percent:0, minimum:null, maximum:null}; }
  function normalize(value) {
    const result = {...defaults(), ...(value || {})};
    if (!['amber','viridis','gray'].includes(result.palette)) result.palette = 'amber';
    if (!['full','percentile','manual'].includes(result.mode)) result.mode = 'full';
    if (!finite(result.clip_percent) || result.clip_percent < 0 || result.clip_percent > 10) result.clip_percent = 0;
    if (result.mode === 'manual' && !(finite(result.minimum) && finite(result.maximum) && result.minimum < result.maximum)) result.mode = 'full';
    return result;
  }
  function syncState() {
    host.state.palette = prefs.palette;
    host.state.clip = prefs.mode === 'percentile' ? prefs.clip_percent : 0;
    host.state.contrast = prefs.mode === 'percentile' ? 'auto' : 'full';
  }
  function request(scan = host.state.scan) {
    const params = {id:scan.id, raw:!!host.state.raw};
    if (!host.state.raw && host.state.pending) params.operations = host.state.pending;
    return params;
  }
  function readLimits(result) {
    if (!(finite(result.minimum) && finite(result.maximum) && result.minimum <= result.maximum)) throw new Error('The display range could not be calculated.');
    return [result.minimum, result.maximum];
  }
  function domain() {
    const edges = histogram?.edges;
    let lo = edges?.length ? edges[0] : limits[0], hi = edges?.length ? edges.at(-1) : limits[1];
    if (!(finite(lo) && finite(hi))) { lo = 0; hi = 1; }
    if (lo === hi) { const pad = Math.max(Math.abs(lo) * .01, .5); lo -= pad; hi += pad; }
    return [lo, hi];
  }
  function sliderValue(value) { const [lo,hi] = domain(); return Math.max(0, Math.min(1000, (value-lo)/(hi-lo)*1000)); }
  function histogramSVG() {
    const counts = histogram?.counts || [], [lo,hi] = domain();
    let peak = 0; for (const count of counts) if (count > peak) peak = count;
    const position = value => Math.max(0, Math.min(260, (value-lo)/(hi-lo)*260));
    const left = position(limits[0]), right = position(limits[1]);
    const bars = counts.map((count,i) => `<rect x="${i*260/counts.length}" y="${52-(peak ? count/peak*49 : 0)}" width="${260/counts.length+.2}" height="${peak ? count/peak*49 : 0}"/>`).join('');
    return `<svg id="color-histogram" viewBox="0 0 260 56" preserveAspectRatio="none" role="img" aria-label="Full-resolution value histogram and current color limits"><g class="histogram-bars">${bars}</g><path class="histogram-clipped" d="M0 0H${left}V54H0Z M${right} 0H260V54H${right}Z"/><path class="histogram-limit" d="M${left} 0V54 M${right} 0V54"/><path class="histogram-axis" d="M0 54H260"/></svg>`;
  }
  function render() {
    if (!host?.state.scan) return '';
    const unit = escape(host.state.scan.value_unit), [lo,hi] = domain();
    const mode = prefs.mode === 'manual' ? 'Manual' : prefs.mode === 'percentile' ? `Auto · ${prefs.clip_percent}% each tail` : 'Full range';
    const lower = sliderValue(limits[0]), upper = sliderValue(limits[1]);
    return `<section id="display-controls" class="inspector-section display-controls" data-busy="${busy}" aria-busy="${busy}">
      <div class="inspector-title">Color & contrast<span class="tag">Display only</span></div>
      <label class="color-map-row">Color map<select id="palette" ${busy?'disabled':''}>${[['amber','Amber'],['viridis','Viridis'],['gray','Grayscale']].map(([value,label])=>`<option value="${value}" ${prefs.palette===value?'selected':''}>${label}</option>`).join('')}</select></label>
      <div class="color-histogram-wrap">${histogramSVG()}
        <div class="color-range-track" style="--range-low:${lower/10}%;--range-high:${upper/10}%" title="Drag either limit; use arrow keys for fine adjustment">
          <div class="color-range-rail"></div>
          <input id="color-lower-slider" type="range" min="0" max="1000" step="1" value="${lower}" aria-label="Color range minimum" aria-valuetext="${numeric(limits[0])} ${unit}" ${busy?'disabled':''}>
          <input id="color-upper-slider" type="range" min="0" max="1000" step="1" value="${upper}" aria-label="Color range maximum" aria-valuetext="${numeric(limits[1])} ${unit}" ${busy?'disabled':''}>
        </div><div class="color-histogram-extents"><span>${concise(lo)}</span><span>${concise(hi)} ${unit}</span></div>
      </div>
      <div class="color-limit-fields">${[['min','Min',limits[0]],['max','Max',limits[1]]].map(([id,label,value])=>`<label>${label} <span>${unit}</span><input id="color-${id}-input" type="number" step="any" value="${fieldValue(value)}" data-exact="${numeric(value)}" title="${numeric(value)} ${unit}; press Enter to apply" aria-describedby="color-${id}-exact" ${busy?'disabled':''}><span class="color-exact-value" id="color-${id}-exact">Stored: ${numeric(value)} ${unit}</span></label>`).join('')}<button class="button small color-set" data-display-action="manual" title="Apply display limits (Enter)" ${busy?'disabled':''}>Set</button></div>
      <div class="color-range-buttons"><button class="button small" data-display-action="auto" title="Trim 2% from each tail" ${busy?'disabled':''}>Auto</button><button class="button small" data-display-action="full" ${busy?'disabled':''}>Full</button><button class="button small" data-display-action="roi" ${busy||!(host.state.contrastROI||host.state.area?.roi)?'disabled':''} title="Use the selected region’s full-resolution limits">Use region</button><span id="color-range-mode">${mode}</span></div>
      <div class="contrast-region-controls"><button class="button small ${host.state.tool==='contrast'?'active':''}" data-display-action="select-roi" aria-pressed="${host.state.tool==='contrast'}" title="Drag a rectangle on the image (C)">${host.state.contrastROI?'Edit region':'Select region'}</button>${host.state.contrastROI?'<button class="button small" data-display-action="clear-roi" title="Remove the outline; keep the current color limits">Clear</button>':''}<span>${host.state.contrastROI?'Region selected':'Drag on image · C'}</span></div>
      <details class="color-auto-options" ${autoOptionsOpen?'open':''}><summary>Auto-range options</summary><div class="range-label"><label for="contrast-slider">Trim each tail</label><b id="contrast-label">${prefs.mode==='percentile'?prefs.clip_percent:0}%</b></div><input id="contrast-slider" type="range" min="0" max="10" value="${prefs.mode==='percentile'?prefs.clip_percent:0}" step=".5" aria-label="Contrast percentile clipping" ${busy?'disabled':''}></details>
      <p class="operation-note color-range-note">Color limits never change measured heights.</p>
    </section>`;
  }
  function refresh() {
    const section = document.getElementById('display-controls');
    if (section) {
      autoOptionsOpen = !!section.querySelector('.color-auto-options')?.open;
      section.outerHTML = render();
    }
  }
  function repaint() { syncState(); host.paintCanvas(); }
  function cancelLiveFrame() { if(liveFrame)cancelAnimationFrame(liveFrame); liveFrame = 0; }
  function flushLiveFrame() {
    if(!liveFrame)return;
    cancelLiveFrame();
    if(!document.getElementById('display-controls'))return;
    renderLiveLimits(); host.paintCanvas();
  }
  async function load(scan) {
    cancelLiveFrame();
    const token = ++generation, isNew = imageId !== scan.id;
    imageId = scan.id;
    if (isNew) { prefs = normalize(scan.display?.settings || scan.display); histogram = null; previewPrefs = null; }
    syncState();
    const settings = {...prefs};
    const result = await host.api('display_range', {...request(scan), mode:settings.mode==='percentile'?'percentile':'full', clip_percent:settings.clip_percent});
    if (token !== generation || imageId !== scan.id) return;
    histogram = result.histogram || null;
    limits = settings.mode === 'manual' ? [settings.minimum,settings.maximum] : readLimits(result);
    committedLimits = [...limits];
    refresh();
  }
  async function change(next, requestedMode = null, selectedROI = null) {
    if (!host.state.scan || busy || host.state.loading) return false;
    flushLiveFrame();
    const id = imageId, token = ++generation, previous = {...prefs}, previousLimits = [...committedLimits], previousHistogram = histogram;
    const active = document.activeElement;
    const focusId = active?.id && active.closest('#display-controls') ? active.id : null;
    const originalFocusIntent = focusIntent;
    const params = request(), roi = selectedROI || host.state.area?.roi, preview = !!host.state.pending;
    busy = true; refresh();
    try {
      next = normalize(next);
      if (requestedMode) {
        const result = await host.api('display_range', {...params, mode:requestedMode, clip_percent:next.clip_percent, ...(requestedMode==='roi'?{roi}: {})});
        const resultLimits = readLimits(result);
        if (requestedMode === 'roi') {
          if (resultLimits[0] === resultLimits[1]) {
            const pad = Math.max(Math.abs(resultLimits[0]) * .01, .5);
            resultLimits[0] -= pad; resultLimits[1] += pad;
          }
          next = {...next, mode:'manual', minimum:resultLimits[0], maximum:resultLimits[1]};
        }
        if (token === generation && id === imageId) {
          limits = resultLimits;
          if (requestedMode !== 'roi') histogram = result.histogram || histogram;
        }
      } else if (next.mode === 'manual') limits = [next.minimum, next.maximum];
      if (token !== generation || id !== imageId) return;
      if (!preview) await host.api('set_display', {id, settings:next});
      if (token !== generation || id !== imageId) return;
      prefs = next;
      committedLimits = [...limits];
      host.state.scan.display = {...next};
      host.state.revision = (host.state.revision || 0) + 1;
      repaint();
      return true;
    } catch (error) {
      if (token === generation && id === imageId) { prefs = previous; limits = previousLimits; histogram = previousHistogram; repaint(); }
      host.toast(error.message, true);
      return false;
    } finally {
      busy = false; refresh();
      // Refresh replaces the input node. Restore keyboard continuity only when
      // that replacement dropped focus; a click, Tab, or new image wins.
      if (focusId && originalFocusIntent === focusIntent && id === imageId && document.activeElement === document.body) {
        const control = document.getElementById(focusId);
        if (control && !control.disabled && control.getClientRects().length) control.focus({preventScroll:true});
      }
    }
  }
  function beginPreview() { if (!previewPrefs) previewPrefs = {...prefs}; }
  async function endPreview(keep) {
    flushLiveFrame();
    await work;
    if (!previewPrefs) return;
    if (keep) await host.api('set_display', {id:imageId, settings:prefs});
    else prefs = previewPrefs;
    previewPrefs = null;
  }
  // Initial characterization contrast is a local preview; no catalog write.
  async function outline() {
    prefs = {...prefs, mode:'percentile', clip_percent:2, minimum:null, maximum:null};
    await load(host.state.scan);
  }
  function remember(task) { work = Promise.resolve(task); return work; }
  function roi(selectedROI) {
    // A second completed drag must not be dropped while the first range/save
    // is in flight. Replay in order; each request uses a frozen rectangle.
    const id = imageId, selection = {...selectedROI};
    work = work.then(() => id === imageId ? change({...prefs, mode:'manual', clip_percent:0}, 'roi', selection) : false);
    return work;
  }
  function manualFields() {
    flushLiveFrame();
    const lower = document.getElementById('color-min-input'), upper = document.getElementById('color-max-input');
    const exactOrEdited = field => Number(field.dataset.edited === 'true' ? field.value : field.dataset.exact);
    const minimum = exactOrEdited(lower), maximum = exactOrEdited(upper);
    if (!lower.value.trim() || !upper.value.trim() || !finite(minimum) || !finite(maximum) || minimum >= maximum) {
      host.toast('Enter finite color limits with minimum below maximum.', true);
      updateLimitField(lower, limits[0]); updateLimitField(upper, limits[1]);
      return Promise.resolve();
    }
    return change({...prefs, mode:'manual', minimum, maximum});
  }
  function updateLimitField(field, value) {
    field.value = fieldValue(value); field.dataset.exact = numeric(value); delete field.dataset.edited;
    field.title = `${numeric(value)} ${host.state.scan.value_unit}; press Enter to apply`;
    const exact = document.getElementById(field.id.replace('-input', '-exact'));
    if (exact) exact.textContent = `Stored: ${numeric(value)} ${host.state.scan.value_unit}`;
  }
  function sliderInput(target) {
    if (busy || host.state.loading) return;
    const [lo,hi] = domain(), value = lo+(hi-lo)*Number(target.value)/1000;
    const gap = (hi-lo)/1000;
    if (target.id === 'color-lower-slider') limits[0] = Math.min(value, limits[1]-gap);
    else limits[1] = Math.max(value, limits[0]+gap);
    // Limits retain every input's exact value; rendering uses the latest pair
    // once per frame. Keep the active native thumb inside the valid interval.
    target.value = sliderValue(target.id === 'color-lower-slider' ? limits[0] : limits[1]);
    if(!liveFrame)liveFrame=requestAnimationFrame(flushLiveFrame);
  }
  function renderLiveLimits() {
    const [lo,hi] = domain();
    for (const [id,value] of [['color-min-input',limits[0]],['color-max-input',limits[1]]]) {
      const field=document.getElementById(id);
      if(field.dataset.edited!=='true')updateLimitField(field,value);
    }
    const lower = document.getElementById('color-lower-slider'), upper = document.getElementById('color-upper-slider');
    lower.value = sliderValue(limits[0]); upper.value = sliderValue(limits[1]);
    const track = document.querySelector('.color-range-track');
    track.style.setProperty('--range-low', `${Number(lower.value)/10}%`);
    track.style.setProperty('--range-high', `${Number(upper.value)/10}%`);
    lower.setAttribute('aria-valuetext', `${numeric(limits[0])} ${host.state.scan.value_unit}`);
    upper.setAttribute('aria-valuetext', `${numeric(limits[1])} ${host.state.scan.value_unit}`);
    document.getElementById('color-range-mode').textContent = 'Manual';
    // Histogram bins are unchanged while dragging; move only its indicators.
    const position = value => Math.max(0, Math.min(260, (value-lo)/(hi-lo)*260));
    const left = position(limits[0]), right = position(limits[1]), histogram = document.getElementById('color-histogram');
    histogram.querySelector('.histogram-clipped').setAttribute('d', `M0 0H${left}V54H0Z M${right} 0H260V54H${right}Z`);
    histogram.querySelector('.histogram-limit').setAttribute('d', `M${left} 0V54 M${right} 0V54`);
  }
  function attach(options) {
    host = options;
    if (installed) return;
    installed = true;
    document.addEventListener('focusin', () => { focusIntent++; });
    document.addEventListener('pointerdown', () => { focusIntent++; }, true);
    document.addEventListener('toggle', event => {
      if (event.target.matches('.color-auto-options') && event.target.isConnected) autoOptionsOpen = event.target.open;
    }, true);
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-display-action]');
      if (!button || button.disabled || host.state.loading) return;
      const action = button.dataset.displayAction;
      if (action === 'select-roi') { host.selectTool('contrast'); return; }
      if (action === 'clear-roi') { host.state.contrastROI = null; host.restoreDrawing(); refresh(); return; }
      if (busy) return;
      if (action === 'manual') remember(manualFields());
      else if (action === 'auto') remember(change({...prefs, mode:'percentile', clip_percent:2}, 'percentile'));
      else if (action === 'full') remember(change({...prefs, mode:'full', clip_percent:0}, 'full'));
      else if (action === 'roi' && (host.state.contrastROI||host.state.area?.roi)) roi(host.state.contrastROI||host.state.area.roi);
    });
    document.addEventListener('input', event => {
      if (!event.target.closest('#display-controls') || busy || host.state.loading) return;
      if (['color-lower-slider','color-upper-slider'].includes(event.target.id)) sliderInput(event.target);
      else if (['color-min-input','color-max-input'].includes(event.target.id)) event.target.dataset.edited = 'true';
      else if (event.target.id === 'contrast-slider') document.getElementById('contrast-label').textContent = `${event.target.value}%`;
    });
    document.addEventListener('change', event => {
      if (!event.target.closest('#display-controls') || busy || host.state.loading) return;
      const id = event.target.id;
      if (id === 'palette') remember(change({...prefs, palette:event.target.value}));
      else if (id === 'contrast-slider') {
        const value = Number(event.target.value);
        remember(change({...prefs, mode:value?'percentile':'full', clip_percent:value}, value?'percentile':'full'));
      } else if (['color-lower-slider','color-upper-slider'].includes(id)) remember(change({...prefs, mode:'manual', minimum:limits[0], maximum:limits[1]}));
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Enter' && ['color-min-input','color-max-input'].includes(event.target.id)) { event.preventDefault(); remember(manualFields()); }
    });
  }
  return {attach, render, refresh, load, beginPreview, endPreview, outline, roi,
    range:()=>[...limits], settings:()=>({...prefs}), pending:async()=>{flushLiveFrame();await work;flushLiveFrame();},
    describe:()=>`${concise(limits[0])} to ${concise(limits[1])} ${host?.state.scan?.value_unit||''} · ${prefs.palette} · ${prefs.mode==='manual'?'manual limits':prefs.mode==='percentile'?prefs.clip_percent+'% each tail':'full range'}`};
})();
