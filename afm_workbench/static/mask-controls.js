'use strict';
// Masks describe a selection in the original stored pixel grid. Editing never
// writes heights; recipes and measurements receive a frozen mask snapshot.
window.AFMMask=(()=>{
  let renderedId=null;
  let host,shape='rectangle',mode='add',radius=8,lower='',upper='',stroke=null,thresholdOpen=false;
  let decodedKey='',decoded=null;
  const previewTargets=new WeakMap();
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const current=()=>host.state.scan?.mask;
  const locked=()=>host.state.raw||!!host.state.pending;
  function active(scan=host.state.scan){const m=scan?.mask;return !!m&&m.masking!=='ignore'&&(m.count>0||m.masking==='include');}
  function parameters(){return active()?{use_saved_mask:true,masking:current().masking}:{};}
  function render(){
    const s=host.state.scan,m=current(),disabled=locked()?'disabled':'';
    if(!s)return '';
    if(renderedId!==s.id){lower='';upper='';stroke=null;renderedId=s.id;}
    const count=m?.count||0,total=s.width*s.height,masking=m?.masking||'exclude',drawing=host.state.tool==='mask';
    return `<section class="inspector-section mask-section"><div class="inspector-title">Mask <span class="tag" title="${count.toLocaleString()} of ${total.toLocaleString()} source pixels marked">${(100*count/total).toFixed(1)}% · ${count.toLocaleString()} px</span></div>
      <label>For fits & measurements<select id="mask-use" ${disabled}>${[['exclude','Exclude marked pixels'],['include','Use only marked pixels'],['ignore','Ignore mask']].map(([v,t])=>`<option value="${v}" ${masking===v?'selected':''}>${t}</option>`).join('')}</select></label>
      <div class="mask-fields mask-tool-options">
        <div><span class="mask-field-label" id="mask-shape-label">Shape</span><div id="mask-shape" class="mask-segmented" role="group" aria-labelledby="mask-shape-label">${[['rectangle','Rectangle'],['brush','Brush']].map(([v,t])=>`<button type="button" data-mask-shape="${v}" aria-pressed="${shape===v}" ${disabled}>${t}</button>`).join('')}</div></div>
        <div><span class="mask-field-label" id="mask-edit-label">Action</span><div id="mask-edit-mode" class="mask-segmented" role="group" aria-labelledby="mask-edit-label">${[['add','Add'],['erase','Erase']].map(([v,t])=>`<button type="button" data-mask-edit="${v}" aria-pressed="${mode===v}" ${disabled}>${t}</button>`).join('')}</div></div>
      </div>
      ${shape==='brush'?`<label class="mask-radius-label">Brush radius <span><input id="mask-radius" type="number" min="1" max="512" step="1" value="${radius}" aria-label="Brush radius in source pixels" ${disabled}> px</span></label>`:''}
      <button class="button small mask-draw-button ${drawing?'active':''}" data-action="tool" data-tool="${drawing?'inspect':'mask'}" aria-pressed="${drawing}" ${disabled}>${drawing?'Done drawing':'Draw mask on image'}</button>
      ${drawing&&!locked()?`<p class="operation-note mask-draw-hint">${shape==='brush'?'Paint':'Drag a rectangle'} to ${mode==='erase'?'erase':'mark'} pixels.</p>`:''}
      <div class="mask-history" role="group" aria-label="Mask edits"><button class="button small" data-mask-action="undo" title="Undo last mask edit" aria-label="Undo mask" ${disabled||!m?.can_undo?'disabled':''}>Undo</button><button class="button small" data-mask-action="redo" title="Redo mask edit" aria-label="Redo mask" ${disabled||!m?.can_redo?'disabled':''}>Redo</button><button class="button small" data-mask-action="invert" title="Swap marked and unmarked pixels" aria-label="Invert mask" ${disabled}>Invert</button><button class="button small" data-mask-action="clear" title="Clear marked pixels; can be undone" aria-label="Clear mask" ${disabled||!count?'disabled':''}>Clear</button></div>
      <details class="mask-threshold" ${thresholdOpen?'open':''}><summary>Select by value</summary><p class="operation-note">${mode==='erase'?'Erase':'Mark'} pixels in this inclusive range.</p><div class="mask-fields"><label>Min (${esc(s.value_unit)})<input id="mask-lower" type="number" step="any" placeholder="No limit" value="${esc(lower)}" ${disabled}></label><label>Max (${esc(s.value_unit)})<input id="mask-upper" type="number" step="any" placeholder="No limit" value="${esc(upper)}" ${disabled}></label></div><button class="button small" data-mask-action="threshold" ${disabled}>${mode==='erase'?'Erase':'Mark'} range</button></details>
      <div class="mask-footer"><label class="mask-visibility"><input id="mask-visible" type="checkbox" ${m?.visible!==false?'checked':''}><span class="mask-overlay-swatch" aria-hidden="true"></span>Show overlay</label><span>Saved per image</span></div>
      ${locked()?'<p class="operation-note mask-lock-note">Select Result to edit the mask.</p>':''}
    </section>`;
  }
  function paint(){
    const canvas=document.getElementById('mask-canvas'),s=host.state.scan,m=current();if(!canvas||!s)return;
    const w=s.data_width||s.width,h=s.data_height||s.height;
    const paintKey=`${s.id}:${m?.revision}:${m?.visible}:${w}:${h}`;
    if(canvas.dataset.maskKey===paintKey)return;
    canvas.dataset.maskKey=paintKey;canvas.width=w;canvas.height=h;
    const ctx=canvas.getContext('2d');ctx.clearRect(0,0,w,h);
    if(!m||m.visible===false||!m.count||!m.data_base64)return;
    const key=`${s.id}:${m.revision}`;
    if(key!==decodedKey){const bytes=atob(m.data_base64);decoded=Uint8Array.from(bytes,c=>c.charCodeAt(0));decodedKey=key;}
    const image=ctx.createImageData(w,h);
    // Conservative display coverage: even a single marked source pixel stays
    // visible when the height display is reduced. This never changes the mask.
    for(let byte=0;byte<decoded.length;byte++)if(decoded[byte])for(let bit=0;bit<8;bit++){
      const i=byte*8+bit;if(i>=s.width*s.height)break;
      if(!(decoded[byte]&(128>>bit)))continue;
      const x=Math.floor(((i%s.width)+.5)*w/s.width),y=Math.floor((Math.floor(i/s.width)+.5)*h/s.height);
      image.data.set([88,155,200,105],4*(y*w+x));
    }
    ctx.putImageData(image,0,0);
  }
  async function update(action,payload={}){
    if(host.state.loading)return;
    if(locked()&&action!=='visibility')throw new Error('Select Result before editing a mask.');
    host.setBusy('Saving mask…');
    try{
      const id=host.state.scan.id;
      if(action==='visibility'){
        host.state.scan.mask=await host.api('update_mask',{id,visible:payload.visible});paint();return;
      }
      await host.api(action==='settings'?'update_mask':'edit_mask',{id,...(action==='settings'?payload:{action,...payload,mode:(payload.mode||mode)==='erase'?'remove':(payload.mode||mode)})});
      host.state.scan=await host.api('scan',{id});
      host.state.area=null;host.state.profile=null;host.state.step=null;host.state.regions=[];
      host.renderContent();
    }finally{host.setBusy(null);}
  }
  function begin(point){
    const s=host.state.scan;
    stroke={points:[point],shape,mode,radius,width:s.width,height:s.height,path:`M${point[0]*s.width} ${point[1]*s.height}`};
  }
  function move(point){
    if(!stroke)return;
    const prev=stroke.points.at(-1);
    if(Math.hypot(point[0]-prev[0],point[1]-prev[1])>.001){
      stroke.points.push(point);
      // Append once per accepted scientific sample; previews reuse this path.
      if(stroke.shape==='brush')stroke.path+=` L${point[0]*stroke.width} ${point[1]*stroke.height}`;
    }
  }
  function preview(){
    if(!stroke)return '';
    const points=stroke.points,a=points[0],b=points.at(-1),c=stroke.mode==='erase'?'#f1d9b6':'#8ac4e7';
    if(stroke.shape==='rectangle')return `<rect x="${Math.min(a[0],b[0])*1000}" y="${Math.min(a[1],b[1])*1000}" width="${Math.abs(a[0]-b[0])*1000}" height="${Math.abs(a[1]-b[1])*1000}" fill="${c}60" stroke="${c}" stroke-width="2"/>`;
    return `<g transform="scale(${1000/stroke.width} ${1000/stroke.height})" opacity=".6"><path d="${stroke.path}" fill="none" stroke="${c}" stroke-width="${2*stroke.radius}" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${b[0]*stroke.width}" cy="${b[1]*stroke.height}" r="${stroke.radius}" fill="${c}"/></g>`;
  }
  function attribute(node,name,value){
    const next=value===null?null:String(value);
    if(node.getAttribute(name)===next)return;
    if(next===null)node.removeAttribute(name);else node.setAttribute(name,next);
  }
  function paintPreview(target){
    if(!target)return;
    if(!stroke){target.style.display='none';return;}
    target.style.display='';
    let view=previewTargets.get(target);
    if(!view||view.shape!==stroke.shape||view.nodes[0].parentNode!==target){
      const names=stroke.shape==='rectangle'?['rect']:['path','circle'];
      const nodes=names.map(name=>document.createElementNS('http://www.w3.org/2000/svg',name));
      target.replaceChildren(...nodes);
      view={shape:stroke.shape,nodes};previewTargets.set(target,view);
    }
    const a=stroke.points[0],b=stroke.points.at(-1),c=stroke.mode==='erase'?'#f1d9b6':'#8ac4e7';
    if(stroke.shape==='rectangle'){
      attribute(target,'transform',null);attribute(target,'opacity',null);
      const [rect]=view.nodes;
      attribute(rect,'x',Math.min(a[0],b[0])*1000);attribute(rect,'y',Math.min(a[1],b[1])*1000);
      attribute(rect,'width',Math.abs(a[0]-b[0])*1000);attribute(rect,'height',Math.abs(a[1]-b[1])*1000);
      attribute(rect,'fill',c+'60');attribute(rect,'stroke',c);attribute(rect,'stroke-width',2);
      return;
    }
    attribute(target,'transform',`scale(${1000/stroke.width} ${1000/stroke.height})`);attribute(target,'opacity','.6');
    const [path,circle]=view.nodes;
    attribute(path,'d',stroke.path);attribute(path,'fill','none');attribute(path,'stroke',c);
    attribute(path,'stroke-width',2*stroke.radius);attribute(path,'stroke-linecap','round');attribute(path,'stroke-linejoin','round');
    attribute(circle,'cx',b[0]*stroke.width);attribute(circle,'cy',b[1]*stroke.height);
    attribute(circle,'r',stroke.radius);attribute(circle,'fill',c);
  }
  async function finish(point){
    move(point);const saved=stroke;stroke=null;if(!saved)return;
    const a=saved.points[0],b=saved.points.at(-1);
    if(saved.shape==='brush')await update('brush',{points:saved.points,radius:saved.radius,mode:saved.mode});
    else if(Math.abs(a[0]-b[0])>0&&Math.abs(a[1]-b[1])>0)await update('rectangle',{roi:{x0:Math.min(a[0],b[0]),y0:Math.min(a[1],b[1]),x1:Math.max(a[0],b[0]),y1:Math.max(a[1],b[1])},mode:saved.mode});
  }
  function attach(context){
    host=context;
    const selectMaskTool=()=>{
      stroke=null;
      if(host.selectTool)host.selectTool('mask');
      else{host.state.tool='mask';host.renderContent();}
    };
    document.addEventListener('toggle',e=>{if(e.target.matches('.mask-threshold')&&e.target.isConnected)thresholdOpen=e.target.open;},true);
    document.addEventListener('change',async e=>{
      if(!e.target.id.startsWith('mask-'))return;
      try{
        const id=e.target.id;
        if(id==='mask-radius'){
          const value=Number(e.target.value);if(!Number.isInteger(value)||value<1||value>512){e.target.value=radius;throw new Error('Enter a brush radius from 1 to 512 pixels.');}radius=value;
        }else if(id==='mask-use')await update('settings',{masking:e.target.value});
        else if(id==='mask-visible')await update('visibility',{visible:e.target.checked});
        else if(id==='mask-lower')lower=e.target.value;
        else if(id==='mask-upper')upper=e.target.value;
      }catch(error){host.toast(error.message,true);}
    });
    document.addEventListener('click',async e=>{
      const option=e.target.closest('[data-mask-shape],[data-mask-edit]');
      if(option){
        if(option.disabled||locked()||host.state.loading)return;
        if(option.dataset.maskShape)shape=option.dataset.maskShape;
        if(option.dataset.maskEdit)mode=option.dataset.maskEdit;
        selectMaskTool();
        return;
      }
      const button=e.target.closest('[data-mask-action]');if(!button||button.disabled||host.state.loading)return;
      try{
        const action=button.dataset.maskAction,payload={};
        if(action==='threshold'){
          lower=document.getElementById('mask-lower').value.trim();upper=document.getElementById('mask-upper').value.trim();
          if(!lower&&!upper)throw new Error('Enter at least one threshold limit.');
          if(lower!=='')payload.lower=Number(lower);if(upper!=='')payload.upper=Number(upper);
          if(Object.values(payload).some(x=>!Number.isFinite(x))||(payload.lower!==undefined&&payload.upper!==undefined&&payload.lower>payload.upper))throw new Error('Minimum must be no greater than maximum.');
        }
        await update(action,payload);
      }catch(error){host.toast(error.message,true);}
    });
  }
  return {attach,render,paint,active,parameters,begin,move,preview,paintPreview,finish,cancel:()=>{stroke=null;}};
})();
