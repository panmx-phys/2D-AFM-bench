/* Canvas navigation and selection stay in the stored image coordinate frame. */
'use strict';
window.AFMCanvas = (() => {
  let host, imageId = null, stage = null, drawing = null, wrap = null, observer = null, gesture = null, space = false;
  let viewport = {scale:1, x:0, y:0}, paintedViewport = {...viewport}, layout = null, frame = 0, pendingMove = null;
  let viewDirty = false, overlayDirty = false, layoutDirty = false;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const editable = target => target.closest('input,textarea,select,button,[role="tab"],[contenteditable="true"]');
  function bounds() {
    if (!layout) return {left:0,top:0,width:1000,height:1000};
    const width = layout.width*viewport.scale, height = layout.height*viewport.scale;
    return {left:layout.centerX+viewport.x-width/2,top:layout.centerY+viewport.y-height/2,width,height};
  }
  function point(event) {
    const r = bounds();
    return [clamp((event.clientX-r.left)/r.width,0,1),clamp((event.clientY-r.top)/r.height,0,1)];
  }
  function measureLayout() {
    if (!wrap || !stage?.isConnected) return;
    // Read fitted geometry only on binding, resize or ancestor scroll, before
    // writing sizes. Input frames use this geometry and the viewport model.
    const padding = getComputedStyle(stage), style = getComputedStyle(wrap);
    const stageWidth = stage.clientWidth, stageHeight = stage.clientHeight;
    const left = parseFloat(padding.paddingLeft), top = parseFloat(padding.paddingTop);
    const width = stageWidth-left-parseFloat(padding.paddingRight), height = stageHeight-top-parseFloat(padding.paddingBottom);
    const aspect = host.state.scan.width_um/host.state.scan.height_um;
    const fitted = Math.max(1,Math.min(width,height*aspect,parseFloat(style.maxWidth)||Infinity));
    const w = `${fitted}px`, h = `${fitted/aspect}px`;
    if (wrap.style.width !== w) wrap.style.width = w;
    if (wrap.style.height !== h) wrap.style.height = h;
    // Capture WebKit's subpixel rounding once, rather than reading the DOM for
    // every input event. The current rendered transform is inverted exactly.
    const actual = drawing.getBoundingClientRect();
    layout = {width:actual.width/paintedViewport.scale,height:actual.height/paintedViewport.scale,stageWidth,stageHeight,
      centerX:actual.left+actual.width/2-paintedViewport.x,centerY:actual.top+actual.height/2-paintedViewport.y};
    layoutDirty = false; viewDirty = overlayDirty = true;
  }
  function clampView() {
    if (!layout) return;
    const xLimit = Math.max(0,(layout.stageWidth+layout.width*viewport.scale)/2-64);
    const yLimit = Math.max(0,(layout.stageHeight+layout.height*viewport.scale)/2-64);
    viewport.x = clamp(viewport.x,-xLimit,xLimit); viewport.y = clamp(viewport.y,-yLimit,yLimit);
  }
  function applyViewport() {
    if (!layout || !stage?.isConnected) return;
    clampView();
    const transform = `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.scale})`;
    if (wrap.style.transform !== transform) wrap.style.transform = transform;
    paintedViewport = {...viewport};
    const navigation = gesture?.kind === 'pan' ? 'dragging' : space || host.state.tool === 'pan' ? 'pan' : host.state.tool;
    if (stage.dataset.navigation !== navigation) stage.dataset.navigation = navigation;
    const readout = document.getElementById('canvas-zoom'), text = `${Math.round(viewport.scale*100)}%`;
    if (readout && readout.textContent !== text) readout.textContent = text;
    for (const [action,disabled] of [['zoom-out',viewport.scale===1],['zoom-in',viewport.scale===16]]) {
      const button = stage.querySelector(`[data-canvas-action="${action}"]`);
      if (button && button.disabled !== disabled) button.disabled = disabled;
    }
    viewDirty = false;
  }
  function hitRegion(p) {
    const r = host.state.contrastROI;
    if (host.state.inspectorHidden || !r || host.state.tool !== 'contrast') return null;
    const box = bounds(), tx = 8/box.width, ty = 8/box.height;
    if (p[0] < r.x0-tx || p[0] > r.x1+tx || p[1] < r.y0-ty || p[1] > r.y1+ty) return null;
    const x = Math.abs(p[0]-r.x0) <= tx ? 'w' : Math.abs(p[0]-r.x1) <= tx ? 'e' : '';
    const y = Math.abs(p[1]-r.y0) <= ty ? 'n' : Math.abs(p[1]-r.y1) <= ty ? 's' : '';
    return y+x || 'move';
  }
  function cursor(p) {
    if (gesture || !drawing) return;
    const edge = hitRegion(p), value = space || host.state.tool === 'pan' ? 'grab' : edge === 'move' ? 'move' : edge ? `${edge}-resize` : host.state.inspectorHidden || host.state.tool === 'inspect' ? 'default' : 'crosshair';
    if (drawing.style.cursor !== value) drawing.style.cursor = value;
  }
  function editedRegion(saved, end) {
    const r = {...saved.roi}, dx = end[0]-saved.start[0], dy = end[1]-saved.start[1];
    if (saved.edge === 'move') {
      const x = clamp(dx,-r.x0,1-r.x1), y = clamp(dy,-r.y0,1-r.y1);
      return {x0:r.x0+x,x1:r.x1+x,y0:r.y0+y,y1:r.y1+y};
    }
    if (saved.edge.includes('w')) r.x0 = end[0];
    if (saved.edge.includes('e')) r.x1 = end[0];
    if (saved.edge.includes('n')) r.y0 = end[1];
    if (saved.edge.includes('s')) r.y1 = end[1];
    return {x0:Math.min(r.x0,r.x1),x1:Math.max(r.x0,r.x1),y0:Math.min(r.y0,r.y1),y1:Math.max(r.y0,r.y1)};
  }
  function flush() {
    if (frame) cancelAnimationFrame(frame); frame = 0;
    if (!stage?.isConnected || imageId !== host.state.scan?.id || host.state.view !== 'detail') { pendingMove = null; return; }
    if (layoutDirty) measureLayout();
    if (viewDirty) applyViewport();
    const redraw = overlayDirty;
    if (overlayDirty) { overlayDirty = false; host.restoreDrawing(); }
    const sample = pendingMove || (redraw ? gesture?.last : null); pendingMove = null;
    if (!sample) return;
    const end = point(sample); host.inspect(end);
    if (!gesture || sample.pointerId !== gesture.id) { cursor(end); return; }
    if (gesture.kind === 'pan') return;
    if (gesture.kind === 'edit') {
      const roi = editedRegion(gesture,end); host.draft('contrast',[roi.x0,roi.y0],[roi.x1,roi.y1]);
    } else host.draft(gesture.tool,gesture.start,end);
  }
  function schedule() { if (!frame) frame = requestAnimationFrame(flush); }
  function refresh() { measureLayout(); flush(); }
  function zoom(factor, clientX, clientY) {
    if (!stage || gesture || host.state.loading || !layout) return;
    const next = clamp(viewport.scale*factor,1,16), ratio = next/viewport.scale;
    if (next === viewport.scale) return;
    const centerX = layout.centerX+viewport.x, centerY = layout.centerY+viewport.y;
    viewport.x += ((clientX ?? centerX)-centerX)*(1-ratio);
    viewport.y += ((clientY ?? centerY)-centerY)*(1-ratio);
    viewport.scale = next;
    if (next === 1) viewport.x = viewport.y = 0;
    clampView(); viewDirty = overlayDirty = true; schedule();
  }
  function fit() { cancel(); viewport = {scale:1,x:0,y:0}; viewDirty = overlayDirty = true; flush(); }
  function release(saved) { if (saved.target.hasPointerCapture(saved.id)) saved.target.releasePointerCapture(saved.id); }
  function cancel() {
    if (frame) cancelAnimationFrame(frame); frame = 0; pendingMove = null;
    const saved = gesture; gesture = null;
    if (saved?.kind === 'pan') viewport = {...saved.viewport};
    if (saved) { host.cancelMask(); release(saved); }
    viewDirty = true; if(saved)overlayDirty = true; flush(); return !!saved;
  }
  function down(event) {
    if (gesture || host.state.loading || !event.isPrimary || ![0,1].includes(event.button) || event.target.closest('.canvas-navigation')) return;
    const navigation = event.button === 1 || space || host.state.tool === 'pan';
    if (!navigation && (event.currentTarget === stage || host.state.tool === 'inspect')) return;
    event.preventDefault(); flush();
    document.getElementById('height-canvas')?.focus({preventScroll:true});
    if (!navigation && !host.canDraw()) return;
    const start = point(event), tool = host.state.tool;
    if (!navigation && tool === 'level') { host.level(start); return; }
    const edge = navigation ? null : hitRegion(start);
    gesture = {id:event.pointerId,target:event.currentTarget,kind:navigation?'pan':edge?'edit':'draw',tool,start,
      screen:[event.clientX,event.clientY],viewport:{...viewport},roi:edge?{...host.state.contrastROI}:null,edge};
    event.currentTarget.setPointerCapture(event.pointerId);
    if (!navigation && tool === 'mask') host.beginMask(start);
    if (!navigation) pendingMove = gesture.last = {clientX:event.clientX,clientY:event.clientY,pointerId:event.pointerId};
    viewDirty = true; schedule();
  }
  function move(event) {
    if (!drawing || gesture && event.pointerId !== gesture.id) return;
    // Keep every brush sample for the saved mask; only its preview is coalesced.
    if (layoutDirty && gesture?.tool === 'mask') measureLayout();
    if (gesture?.tool === 'mask' && gesture.kind === 'draw') host.moveMask(point(event));
    if (gesture?.kind === 'pan') {
      viewport.x = gesture.viewport.x+event.clientX-gesture.screen[0];
      viewport.y = gesture.viewport.y+event.clientY-gesture.screen[1];
      clampView(); viewDirty = true;
    }
    pendingMove = {clientX:event.clientX,clientY:event.clientY,pointerId:event.pointerId};
    if(gesture)gesture.last=pendingMove;
    schedule();
  }
  async function up(event) {
    if (!gesture || event.pointerId !== gesture.id) return;
    // The release may arrive before the next frame, or beyond the last move.
    move(event); flush();
    const saved = gesture, end = point(event); gesture = null;
    release(saved); viewDirty = true; applyViewport();
    if (saved.kind === 'pan') return;
    const box = bounds(), distance = Math.hypot(event.clientX-saved.screen[0],event.clientY-saved.screen[1]);
    let start = saved.start, finish = end;
    if (saved.kind === 'edit') { const roi = editedRegion(saved,end); start = [roi.x0,roi.y0]; finish = [roi.x1,roi.y1]; }
    const rectangle = !['mask','profile'].includes(saved.tool);
    if (saved.tool !== 'mask' && (distance < 3 || rectangle && (Math.abs(start[0]-finish[0])*box.width < 3 || Math.abs(start[1]-finish[1])*box.height < 3))) { host.restoreDrawing(); return; }
    await host.complete(saved.tool,start,finish); cursor(end);
  }
  function bind() {
    const next = document.querySelector('.canvas-stage'), surface = document.getElementById('draw-overlay');
    if (!next || !surface) return;
    if (imageId !== host.state.scan.id) { cancel(); imageId = host.state.scan.id; viewport = {scale:1,x:0,y:0}; }
    if (next !== stage) {
      cancel(); observer?.disconnect(); stage = next; drawing = surface; wrap = stage.querySelector('.canvas-wrap'); paintedViewport = {scale:1,x:0,y:0};
      observer = new ResizeObserver(() => { layoutDirty = true; schedule(); }); observer.observe(stage);
      drawing.onpointerdown = down; drawing.onpointermove = move; drawing.onpointerup = up;
      drawing.onpointercancel = event => { if (event.pointerId === gesture?.id) cancel(); };
      drawing.onlostpointercapture = event => { if (event.pointerId === gesture?.id) cancel(); };
      stage.onpointerdown = event => { if (event.target === stage) down(event); };
      stage.onpointermove = event => { if (gesture?.target === stage) move(event); };
      stage.onpointerup = event => { if (gesture?.target === stage) up(event); };
      stage.onpointercancel = drawing.onpointercancel; stage.onlostpointercapture = drawing.onlostpointercapture;
      stage.onwheel = event => {
        if (event.target.closest('.canvas-navigation')) return;
        event.preventDefault();
        const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? layout.stageHeight : 1;
        zoom(Math.exp(-clamp(event.deltaY*unit,-300,300)*(event.ctrlKey ? .01 : .002)),event.clientX,event.clientY);
      };
      drawing.ondblclick = () => { if (['inspect','pan'].includes(host.state.tool)) fit(); };
    }
    drawing.style.cursor = space || host.state.tool === 'pan' ? 'grab' : host.state.inspectorHidden || host.state.tool === 'inspect' ? 'default' : 'crosshair';
    refresh();
  }
  function attach(options) {
    host = options;
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-canvas-action]');
      if (!button || button.disabled || host.state.loading) return;
      const action = button.dataset.canvasAction; if (action === 'fit') fit(); else zoom(action === 'zoom-in'?1.25:1/1.25);
    });
    document.addEventListener('keydown', event => {
      if (host.state.view !== 'detail' || document.querySelector('.modal') || editable(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.code === 'Space') { event.preventDefault(); space = true; viewDirty = true; schedule(); if(drawing)drawing.style.cursor='grab'; }
      else if (['+','=','-','f','F'].includes(event.key)) { event.preventDefault(); if(event.key.toLowerCase()==='f')fit();else zoom(event.key==='-'?1/1.25:1.25); }
    });
    document.addEventListener('keyup', event => {
      if (event.code === 'Space') { space = false; viewDirty = true; schedule(); if(drawing)drawing.style.cursor=host.state.inspectorHidden||host.state.tool==='inspect'?'default':host.state.tool==='pan'?'grab':'crosshair'; }
    });
    document.addEventListener('scroll', event => { if(stage?.isConnected && event.target.contains?.(stage)){layoutDirty=true;schedule();} },true);
    window.addEventListener('resize', () => { if(stage?.isConnected){layoutDirty=true;schedule();} });
    window.addEventListener('blur', () => { space = false; cancel(); });
  }
  return {attach,bind,refresh,zoom,fit,cancel,flush,bounds,activeTool:()=>gesture&&gesture.kind!=='pan'?gesture.tool:null,view:()=>({...viewport})};
})();
