'use strict';
const icons={layers:'<path d="m3 8 9-5 9 5-9 5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',folder:'<path d="M3 7V5a1 1 0 0 1 1-1h6l2 3h8a1 1 0 0 1 1 1v11H3Z"/>',plus:'<path d="M12 5v14M5 12h14"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z"/>',map:'<path d="m3 5 6-2 6 3 6-2v15l-6 2-6-3-6 2ZM9 3v15M15 6v15"/>',arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',back:'<path d="M19 12H5m5-5-5 5 5 5"/>',chevron:'<path d="m9 5 7 7-7 7"/>',down:'<path d="m6 9 6 6 6-6"/>',check:'<path d="m5 12 4 4L19 6"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor" stroke="none"/><circle cx="15" cy="17" r="3" fill="currentColor" stroke="none"/>',compare:'<rect x="3" y="4" width="7" height="16" rx="1"/><rect x="14" y="4" width="7" height="16" rx="1"/>',note:'<path d="M14 3H5v18h14V8Z"/><path d="M14 3v6h5M8 13h8M8 17h6"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',line:'<path d="M3 18 9 8l6 6 6-11"/>',plane:'<path d="m3 15 11-9 7 3-11 9Z"/><path d="M3 20h18"/>',undo:'<path d="M4 10h10a6 6 0 0 1 0 12M4 10l5-5M4 10l5 5"/>',reset:'<path d="M3 10a9 9 0 1 1 1 8M3 4v6h6"/>',crop:'<rect x="5" y="5" width="14" height="14" stroke-dasharray="3 2"/>',rows:'<path d="M3 6h15M6 12h15M3 18h15"/>',columns:'<path d="M6 3v15M12 6v15M18 3v15"/>',minus:'<path d="M5 12h14"/>',expand:'<path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6"/>',help:'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5M12 17v1"/>',cursor:'<path d="m5 3 14 10-7 1-3 7Z"/>',tag:'<path d="M3 3h8l10 10-8 8L3 11Z"/><circle cx="7" cy="7" r="1"/>',smallgrid:'<path d="M3 3h18v18H3ZM9 3v18M15 3v18M3 9h18M3 15h18"/>',contrast:'<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18Z" fill="currentColor" stroke="none"/>',brush:'<path d="M15 4l5 5-9 9-5 1 1-5Z"/><path d="m13 6 5 5"/>',hand:'<path d="M8 13V5a2 2 0 0 1 4 0v6-7a2 2 0 0 1 4 0v7-5a2 2 0 0 1 4 0v9c0 5-3 7-7 7h-1c-2 0-4-1-5-3l-4-5a2 2 0 0 1 3-3l2 2Z"/>',swap:'<path d="M4 8h15l-4-4M20 16H5l4 4"/>'};
const icon=(name,extra='')=>`<svg class="icon ${extra}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.info}</svg>`;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=2)=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
const date=v=>{if(!v)return'Local session';const d=new Date(v);return Number.isNaN(d.getTime())?v:d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});};
const stored=(key,fallback)=>{try{const v=localStorage.getItem(key);return v===null?fallback:v;}catch{return fallback;}};
const state={folders:[],folderFilter:'active',importJob:null,undoStack:[],lineDir:null,autoPrepare:stored('afm-auto-prepare','true')!=='false',browseLevel:stored('afm-browse-level','true')!=='false',levelPoints:[],contrastROI:null,sessions:[],session:null,view:'session',tab:'grid',query:'',channel:'overview',direction:'all',acquisition:'all',starred:false,compact:false,selected:new Set(),scan:null,tool:'inspect',palette:'amber',contrast:'auto',clip:0,raw:false,pending:null,profile:null,area:null,regions:[],step:null,mapZoom:1,mapMode:'all',mapOpacity:Math.min(100,Math.max(10,Number(stored('afm-map-opacity','75'))||75)),mapSelected:null,revision:0,loading:false,autoLineCorrection:true,processingAxis:'auto',lineMethod:'median',lineDegree:1,lineTrim:5,polynomialMode:'independent',polynomialDegree:3,polynomialDegreeX:3,polynomialDegreeY:3,manualCorrections:false,referenceMode:'include',profileWidth:1,profileInterpolation:'linear',inspectorHidden:stored('afm-inspector-hidden','false')==='true',inspectorTab:'view',inspectorScroll:{},inspectorDetails:{}};
let requestSerial=0,toastTimer,searchTimer,canvasRanges=[0,1];
async function api(method,payload={}){
  if(['scan','process','preview','update_scan'].includes(method))payload={...payload,data_encoding:'f64le'};
  const response=await fetch(`/api/${method}`,{method:'POST',headers:{'Content-Type':'application/json','X-AFM-Token':document.querySelector('meta[name="afm-token"]').content},body:JSON.stringify(payload)});
  const result=await response.json();
  if(!response.ok||result.error)throw new Error(typeof result.error==='string'?result.error:result.error?.message||`Request failed (${response.status})`);
  if(result.data_encoding==='f64le'){
    const binary=atob(result.data_base64),bytes=new Uint8Array(binary.length);
    for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
    const view=new DataView(bytes.buffer),count=result.data_width*result.data_height;
    if(bytes.length!==count*8)throw new Error('Incomplete image data.');
    const values=new Float64Array(count);
    for(let i=0;i<count;i++)values[i]=view.getFloat64(i*8,true);
    result.data=values;delete result.data_base64;
  }
  return result;
}
function thumb(s,options={}){const params=new URLSearchParams({recipe:'1',level:state.browseLevel?'1':'0',v:String(state.revision),...options});return `/api/thumbnail/${encodeURIComponent(s.id)}?${params}`;}
function toast(message,error=false,button=null){const el=document.getElementById('toast');el.textContent=message;if(button){const b=document.createElement('button');b.type='button';b.className='toast-action';b.dataset.action=button.action;b.textContent=button.label;el.append(' ',b);}el.className=`show${error?' error':''}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='',error?7000:button?6000:3500);}
function setBusy(message){if(message)AFMCanvas.cancel();document.querySelector('.loading-overlay')?.remove();state.loading=!!message;if(message){const el=document.createElement('div');el.className='loading-overlay';el.innerHTML=`<div class="loading-pill"><span class="spinner"></span>${esc(message)}</div>`;document.body.append(el);}}
function isHeight(channel){return !/error/i.test(channel)&&/height|topograph/i.test(channel);}
function channelRank(channel){
  if (/^z[ _-]*height$/i.test(channel.trim())) return 0;
  if (isHeight(channel)) return 1;
  return /error/i.test(channel)?2:/amplitude/i.test(channel)?3:/phase/i.test(channel)?4:5;
}
function browseLeveled(s){return state.browseLevel&&isHeight(s.channel)&&s.value_unit==='nm'&&!s.operations?.length;}
function directionRank(direction){return direction==='Forward'?0:direction==='Backward'?1:2;}
function acquisitionKey(scan){
  const p=position(scan);
  return JSON.stringify([scan.acquisition,scan.width_um,scan.height_um,p?[p.x,p.y,p.angle]:null]);
}
function acquisitionGroups(scans){
  const groups=new Map();
  for(const scan of sorted(scans)){
    const key=acquisitionKey(scan);
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(scan);
  }
  return [...groups.values()];
}
function primaryScan(scans){
  const heights=scans.filter(s=>isHeight(s.channel));
  return [...(heights.length?heights:scans)].sort((a,b)=>directionRank(a.direction)-directionRank(b.direction)||channelRank(a.channel)-channelRank(b.channel)||a.channel.localeCompare(b.channel)||a.filename.localeCompare(b.filename))[0];
}
function matchingSignals(primary,scans){
  return sorted(scans.filter(s=>s.id!==primary.id&&!isHeight(s.channel)&&s.direction===primary.direction&&acquisitionKey(s)===acquisitionKey(primary)));
}
function heightOverview(){return state.channel==='overview'&&!state.query.trim()&&!state.starred;}
function overviewGroups(scans){
  return acquisitionGroups(scans).map(group=>state.direction==='all'?group:group.filter(s=>s.direction===state.direction)).filter(group=>group.length&&filtered(group).length);
}
function sorted(scans){return [...scans].sort((a,b)=>String(a.acquisition).localeCompare(String(b.acquisition),undefined,{numeric:true})||channelRank(a.channel)-channelRank(b.channel)||a.channel.localeCompare(b.channel)||directionRank(a.direction)-directionRank(b.direction)||a.filename.localeCompare(b.filename));}
function filtered(scans){const q=state.query.trim().toLowerCase();return sorted(scans.filter(s=>(state.channel==='overview'||state.channel==='all'||s.channel===state.channel)&&(state.direction==='all'||s.direction===state.direction)&&(state.acquisition==='all'||s.acquisition===state.acquisition)&&(!state.starred||s.starred)&&(!q||[s.filename,s.channel,s.acquisition,s.direction,s.review_status].join(' ').toLowerCase().includes(q))));}
function renderShell(){
  rememberInspector();
  document.getElementById('app').innerHTML=`<div class="app-shell"><aside class="sidebar"><div class="brand"><img src="/favicon.svg" alt=""><span>AFM Workbench</span></div><nav class="nav-group" aria-label="Library"><button class="nav-button ${state.view==='library'?'active':''}" data-action="library">${icon('grid')}<span>All sessions</span><span class="count">${state.sessions.length}</span></button><button class="nav-button ${state.view==='starred'?'active':''}" data-action="starred">${icon('star')}<span>Starred</span></button><button class="nav-button ${state.view==='folders'?'active':''}" data-action="folders">${icon('folder')}<span>Folders</span></button></nav><div class="sessions-nav"><div class="section-label">Sessions<button class="icon-button" title="Import a folder" data-action="import">${icon('plus')}</button></div>${state.sessions.map(s=>`<button class="session-link ${state.session?.id===s.id&&!['library','starred','folders'].includes(state.view)?'selected':''}" data-action="session" data-id="${esc(s.id)}"><span class="folder-mark">${icon('folder')}</span><span><strong>${esc(s.name)}</strong>${s.synthetic?'<small>Synthetic</small>':''}</span></button>`).join('')}</div><div class="nav-group"><button class="nav-button" data-action="help">${icon('help')}<span>Help & shortcuts</span></button></div></aside><main class="workspace"><header class="topbar"><div class="breadcrumb">${state.view==='detail'?esc(state.session?.name):state.view==='compare'?'Compare':state.view==='starred'?'Starred images':'Sessions'}</div><div class="top-actions"><label class="searchbox">${icon('search')}<input id="global-search" aria-label="Search images or sessions" placeholder="Search…" value="${esc(state.query)}"><kbd>⌘ K</kbd></label><button class="button primary" data-action="import">${icon('plus')} Import folder</button></div></header><div id="main-content" class="${['detail','compare'].includes(state.view)?'':'content'}"></div></main></div>`;
  renderContent();renderImportProgress();
}
function renderContent(){rememberInspector();const main=document.getElementById('main-content');if(!main)return;main.className=['detail','compare'].includes(state.view)?'':'content';if(state.view==='detail')renderDetail(main);else if(state.view==='compare')renderCompare(main);else if(state.view==='starred')renderStarred(main);else if(state.view==='folders')renderFolders(main);else if(state.view==='library'||!state.session)renderLibrary(main);else renderSession(main);renderTray();}
function renderLibrary(main){
  const sessions=state.sessions.filter(s=>!state.query||[s.name,s.notes,s.source_path].join(' ').toLowerCase().includes(state.query.toLowerCase()));
  main.innerHTML=`<div class="session-heading"><h1>Sessions</h1></div>${!state.sessions.length?`<div class="empty-state"><h2>No sessions</h2><p>Import a folder of Park SmartScan TIFF files.</p><div class="empty-actions"><button class="button primary" data-action="import">${icon('folder')}Import folder</button><button class="button" data-action="demo">Open synthetic example</button></div></div>`:`<div class="library-grid">${sessions.map(s=>`<button class="session-card" data-action="session" data-id="${esc(s.id)}"><div class="session-previews" data-session-preview="${esc(s.id)}">${icon('layers')}</div><div class="session-card-info"><h3>${esc(s.name)}</h3><p>${s.scan_count} images · ${date(s.imported_at)}${s.synthetic?' · Synthetic':''}</p></div></button>`).join('')}</div>${sessions.length?'':'<div class="empty-state"><p>No matching sessions.</p></div>'}`}`;
  for(const session of sessions){api('session',{id:session.id}).then(full=>{const target=document.querySelector(`[data-session-preview="${CSS.escape(session.id)}"]`);if(target)target.innerHTML=acquisitionGroups(full.scans).map(primaryScan).slice(0,2).map(scan=>`<img src="${thumb(scan)}" alt="${esc(scan.channel)} ${esc(scan.direction)}">`).join('');}).catch(()=>{});}
}
function renderStarred(main){const sessions=(state.starredSessions||[]).map(s=>({...s,scans:s.scans.filter(x=>x.starred&&(!state.query||[x.filename,x.channel,x.acquisition,s.name].join(' ').toLowerCase().includes(state.query.toLowerCase())))})).filter(s=>s.scans.length);main.innerHTML=`<div class="session-heading"><h1>Starred images</h1></div>${sessions.map(s=>`<div class="group-heading"><h3>${esc(s.name)}</h3><span>${s.scans.length} images</span></div><div class="scan-grid">${sorted(s.scans).map(card).join('')}</div>`).join('')||'<div class="empty-state"><h2>No starred images</h2><p>Use the star beside an image to save it here.</p></div>'}`;}
function sessionDetails(){
  const s=state.session;
  showModal('Session details',`<dl class="metadata-list"><dt>Source folder</dt><dd>${esc(s.source_path||'Synthetic example')}</dd><dt>Imported</dt><dd>${date(s.imported_at)}</dd><dt>Instrument</dt><dd>${esc(s.scans[0]?.instrument||'Not recorded')}</dd><dt>Images</dt><dd>${s.scans.length}</dd><dt>Channels</dt><dd>${esc([...new Set(s.scans.map(x=>x.channel))].join(', '))}</dd><dt>Origin</dt><dd>${s.synthetic?'Synthetic data':'Instrument data'}</dd></dl>${s.notes?`<p class="session-notes">${esc(s.notes)}</p>`:''}`);
}
function renderSession(main){
  const s=state.session,scans=filtered(s.scans),overview=heightOverview();
  const channels=[...new Set(s.scans.map(x=>x.channel))].sort((a,b)=>channelRank(a)-channelRank(b)||a.localeCompare(b));
  const acqs=[...new Set(s.scans.map(x=>x.acquisition))].sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
  const groups=overview?overviewGroups(s.scans):[];
  main.innerHTML=`<div class="session-heading"><div class="session-title"><h1>${esc(s.name)}</h1>${s.synthetic?'<span class="session-context">Synthetic</span>':''}</div><div class="heading-actions"><button class="button small" data-action="manage-folder" data-id="${esc(s.id)}">${icon('folder')}Manage folder</button><button class="button small" data-action="session-details">Details</button><button class="button small" data-action="notes" title="Session notes">${icon('note')}Notes${s.notes?' •':''}</button><button class="button small" data-action="export-session" title="Export the session manifest">${icon('download')}Export</button></div></div><div class="view-tabs"><button class="view-tab ${state.tab==='grid'?'active':''}" data-action="tab" data-tab="grid">${icon('grid')}Contact sheet</button><button class="view-tab ${state.tab==='map'?'active':''}" data-action="tab" data-tab="map">${icon('map')}Sample map</button></div><div class="filterbar"><label class="select-wrap"><select aria-label="Filter channel" id="channel-filter"><option value="overview" ${state.channel==='overview'?'selected':''}>Z height + signals</option><option value="all" ${state.channel==='all'?'selected':''}>All channels</option>${channels.map(c=>`<option value="${esc(c)}" ${c===state.channel?'selected':''}>${esc(c)}</option>`).join('')}</select></label><label class="select-wrap"><select aria-label="Filter direction" id="direction-filter">${['all',...new Set(s.scans.map(x=>x.direction))].map(d=>`<option value="${esc(d)}" ${state.direction===d?'selected':''}>${d==='all'?(overview?'Forward preferred':'Both directions'):esc(d)}</option>`).join('')}</select></label><label class="select-wrap"><select aria-label="Filter acquisition" id="acquisition-filter"><option value="all">All acquisitions</option>${acqs.map(a=>`<option value="${esc(a)}" ${state.acquisition===a?'selected':''}>Scan ${esc(a)}</option>`).join('')}</select></label><button class="button small ${state.starred?'active':''}" data-action="starred-filter" aria-pressed="${state.starred}">${icon('star')}Starred</button><button class="button small ${state.browseLevel?'active':''}" data-action="browse-level" aria-pressed="${state.browseLevel}" title="Display-only scan-line + plane leveling of unprocessed height thumbnails. Data and saved recipes are unchanged.">${icon('plane')}Leveled thumbnails</button><span class="push result-count">${overview?`${groups.length} acquisitions`:`${scans.length} images`}</span>${state.tab==='grid'&&!overview?`<div class="toggle-group"><button class="${!state.compact?'active':''}" data-action="density" data-value="comfortable" title="Larger images">${icon('grid')}</button><button class="${state.compact?'active':''}" data-action="density" data-value="compact" title="Smaller images">${icon('smallgrid')}</button></div>`:''}</div><div id="session-results">${state.tab==='grid'?renderGrid(overview?s.scans:scans):renderMap(scans)}</div>`;
}
function renderGrid(scans){
  const groups=heightOverview()?overviewGroups(scans):acquisitionGroups(scans);
  if(!groups.length)return `<div class="empty-state"><h3>No matching images</h3><button class="button" data-action="clear-filters">Reset filters</button></div>`;
  if(heightOverview())return `<div class="acquisition-grid ${state.compact?'compact':''}">${groups.map(group=>{
    const primary=primaryScan(group),related=matchingSignals(primary,group).slice(0,3);
    const all=sorted(scans.filter(s=>acquisitionKey(s)===acquisitionKey(primary)));
    const fallback=!isHeight(primary.channel)?'Z height unavailable':primary.direction!=='Forward'&&state.direction==='all'?'Forward Z height unavailable':'';
    return `<section class="acquisition-card" data-acquisition="${esc(primary.acquisition)}"><div class="group-heading"><h3>Scan ${esc(primary.acquisition)}</h3><span>${num(primary.width_um)} × ${num(primary.height_um)} µm</span></div>${fallback?`<p class="acquisition-note">${fallback} · showing ${esc(primary.channel)} ${esc(primary.direction)}</p>`:''}<div class="acquisition-layout"><div class="primary-scan">${card(primary)}</div><aside class="related-signals"><div class="related-title">Signals · ${esc(primary.direction)}</div>${related.map(s=>`<button class="related-signal" data-action="open" data-id="${esc(s.id)}" aria-label="Open ${esc(s.channel)} ${esc(s.direction)} scan ${esc(s.acquisition)}"><img class="signal-preview" src="${thumb(s,{palette:'gray'})}" alt="" loading="lazy"><span class="signal-label"><strong>${esc(s.channel)}</strong><small>${esc(s.direction)} · ${esc(s.value_unit)}</small></span></button>`).join('')||'<p class="signal-empty">No matching signals</p>'}<details class="channel-list"><summary>All channels (${all.length})</summary>${all.map(s=>channelSwitch(s,primary.id)).join('')}</details></aside></div></section>`;
  }).join('')}</div>`;
  return groups.map(group=>`<section class="scan-group"><div class="group-heading"><h3>Scan ${esc(group[0].acquisition)}</h3><span>${num(group[0].width_um)} × ${num(group[0].height_um)} µm</span></div><div class="scan-grid ${state.compact?'compact':''}">${group.map(card).join('')}</div></section>`).join('');
}
function channelSwitch(scan,activeId,preview=false){
  return `<button class="channel-switch ${scan.id===activeId?'active':''}" data-action="open" data-id="${esc(scan.id)}" ${scan.id===activeId?'aria-current="true"':''}>${preview?`<img src="${thumb(scan,{palette:isHeight(scan.channel)?state.palette:'gray'})}" alt="">`:''}<span><strong>${esc(scan.channel)}</strong><small>${esc(scan.direction)} · ${esc(scan.value_unit)}</small></span></button>`;
}
function card(s){return `<article class="scan-card ${state.selected.has(s.id)?'selected':''}" data-scan-card="${esc(s.id)}"><input class="card-select" type="checkbox" aria-label="Select ${esc(s.channel)} ${esc(s.direction)} scan ${esc(s.acquisition)} for comparison" data-select="${esc(s.id)}" ${state.selected.has(s.id)?'checked':''}><button class="card-image-button" style="aspect-ratio:${s.width_um/s.height_um}" data-action="open" data-id="${esc(s.id)}" aria-label="Open ${esc(s.channel)} ${esc(s.direction)} scan ${esc(s.acquisition)}"><img src="${thumb(s)}" alt="${esc(s.channel)} scan ${esc(s.acquisition)}" loading="lazy"><span class="image-top"><span class="image-badge">${s.direction==='Backward'?'←':'→'} ${esc(s.direction)}</span>${s.operations?.length?'<span class="image-badge edited">Processed</span>':browseLeveled(s)?'<span class="image-badge" title="Display-only leveling; the stored data is unchanged">Leveled view</span>':''}</span><span class="scale-bar">${num(s.width_um/4)} µm</span></button><div class="card-info"><div class="card-title"><button class="title-link" data-action="open" data-id="${esc(s.id)}">${esc(s.channel)}</button><button class="icon-button ${s.starred?'active':''}" data-action="star" data-id="${esc(s.id)}" title="${s.starred?'Unstar':'Star'} image" aria-label="${s.starred?'Unstar':'Star'} ${esc(s.channel)} scan ${esc(s.acquisition)}">${icon('star')}</button></div><div class="card-meta">${s.width} × ${s.height} px <span>·</span>${num(s.width_um)} µm</div><div class="card-footer"><span title="${isHeight(s.channel)&&!s.operations?.length?'Computed from the stored, unleveled data':'Computed from the saved result'}">${isHeight(s.channel)?'Sq':'RMS variation'} <strong>${num(s.statistics?.sq)} ${esc(s.value_unit)}</strong>${isHeight(s.channel)&&!s.operations?.length?' <small>unleveled</small>':''}</span>${s.review_status==='reviewed'?`<span class="review-mark">${icon('check')}Reviewed</span>`:`<span>${s.warnings?.length?'Metadata note':s.operations?.length?`${s.operations.length} saved correction${s.operations.length===1?'':'s'}`:'Unprocessed'}</span>`}</div></div></article>`;}
function position(s){
  const p=Object.hasOwn(s,'map_footprint')?s.map_footprint:s.position||s.metadata?.position;
  if(!p||p.calibrated!==true||!['center','corner'].includes(p.reference))return null;
  let x=p.x_um,y=p.y_um;const w=s.width_um,h=s.height_um,angle=p.rotation_deg;
  if(![x,y,w,h,angle].every(Number.isFinite)||w<=0||h<=0)return null;
  if(p.reference==='corner'){
    const a=angle*Math.PI/180;
    x+=(w*Math.cos(a)-h*Math.sin(a))/2;y+=(w*Math.sin(a)+h*Math.cos(a))/2;
  }
  return {x,y,w,h,angle,note:p.orientation_note||''};
}
function mapGroups(scans){
  return acquisitionGroups(scans).map(scans=>{
    const p=position(scans[0]);
    return {...p,key:acquisitionKey(scans[0]),placed:!!p,scans};
  });
}
function mapContains(g,x,y){
  if(!g.placed)return false;
  // Invert the recorded footprint rotation, without transforming scan pixels.
  const a=g.angle*Math.PI/180,dx=x-g.x,dy=y-g.y;
  const localX=dx*Math.cos(a)+dy*Math.sin(a),localY=-dx*Math.sin(a)+dy*Math.cos(a);
  const tolerance=Math.max(g.w,g.h)*1e-10;
  return Math.abs(localX)<=g.w/2+tolerance&&Math.abs(localY)<=g.h/2+tolerance;
}
function mapScanDescription(g){
  const s=primaryScan(g.scans);
  const heightPreferred=['overview','all'].includes(state.channel);
  const fallback=heightPreferred&&!isHeight(s.channel)?'Z height unavailable · ':heightPreferred&&s.direction!=='Forward'&&state.direction==='all'?'Forward Z height unavailable · ':'';
  return `${fallback}${s.channel} · ${s.direction}`;
}
function clearMapFocus(){state.mapSelected=null;state.mapMode='all';renderContent();}
function selectMapGroup(index){
  const g=mapGroups(filtered(state.session.scans))[index];if(!g)return;
  const deselect=state.mapSelected===g.key&&state.mapMode==='focus';
  state.mapSelected=deselect?null:g.key;state.mapMode=deselect?'all':'focus';
  closeModal();renderContent();
  const row=document.querySelector(`.map-aside [data-action="map-select"][data-key="${index}"]`);
  row?.focus({preventScroll:true});
  row?.closest('.map-acquisition')?.scrollIntoView({block:'nearest',inline:'nearest'});
}
function pickMapLocation(el,event){
  const groups=mapGroups(filtered(state.session.scans));
  // Keyboard activation selects the focused footprint; pointer activation considers every layer.
  if(!event?.detail){if(el.dataset.key!==undefined)selectMapGroup(Number(el.dataset.key));return;}
  const svg=el.ownerSVGElement||el,matrix=svg.getScreenCTM();if(!matrix)return;
  const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
  const local=point.matrixTransform(matrix.inverse());
  const x=Number(svg.dataset.centerX)+(local.x-400)/Number(svg.dataset.scale);
  const y=Number(svg.dataset.centerY)-(local.y-280)/Number(svg.dataset.scale);
  const hits=groups.map((g,index)=>({g,index})).filter(({g})=>mapContains(g,x,y));
  if(!hits.length||state.mapMode==='focus'&&hits.some(({g})=>g.key===state.mapSelected)){clearMapFocus();return;}
  if(hits.length===1){selectMapGroup(hits[0].index);return;}
  showModal(`${hits.length} scans at this point`,`<p>Choose a scan to focus. Click it again to show all images.</p>${hits.map(({g,index})=>`<button class="map-location" data-action="map-select" data-key="${index}"><img src="${thumb(primaryScan(g.scans))}" alt=""><span><strong>Scan ${esc(g.scans[0].acquisition)}</strong><small>${num(g.w)} × ${num(g.h)} µm · ${g.scans.length} image${g.scans.length===1?'':'s'}</small><small>${esc(mapScanDescription(g))}</small></span>${icon('chevron')}</button>`).join('')}`);
  document.querySelector('.modal [data-action="map-select"]')?.focus();
}
function mapUnplaced(groups){
  return `<section class="map-unplaced"><h3>Not placed on map</h3><p>Position, angle or size is unavailable. Images remain available here.</p><div class="map-unplaced-grid">${groups.map((g,i)=>g.placed?'':`<button class="map-unplaced-card" data-action="map-select" data-key="${i}"><img src="${thumb(primaryScan(g.scans))}" alt="${esc(mapScanDescription(g))}"><strong>Scan ${esc(g.scans[0].acquisition)}</strong><small>${esc(mapScanDescription(g))}</small></button>`).join('')}</div></section>`;
}
function renderMapPlot(groups,selected){
  const placed=groups.filter(g=>g.placed);
  if(selected&&!selected.placed)return `<div class="map-unplaced-preview"><button data-action="map-select" data-key="${groups.indexOf(selected)}" title="Show all images"><img src="${thumb(primaryScan(selected.scans))}" alt="${esc(mapScanDescription(selected))}"></button><p>Scan ${esc(selected.scans[0].acquisition)} · Not placed on map</p></div>`;
  if(!placed.length)return `<div class="map-no-positions">${mapUnplaced(groups)}</div>`;
  let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  for(const g of placed){
    const a=g.angle*Math.PI/180;
    const dx=Math.abs(g.w*Math.cos(a))/2+Math.abs(g.h*Math.sin(a))/2,dy=Math.abs(g.w*Math.sin(a))/2+Math.abs(g.h*Math.cos(a))/2;
    minX=Math.min(minX,g.x-dx);maxX=Math.max(maxX,g.x+dx);minY=Math.min(minY,g.y-dy);maxY=Math.max(maxY,g.y+dy);
  }
  const centerX=(minX+maxX)/2,centerY=(minY+maxY)/2,span=Math.max(maxX-minX,(maxY-minY)*1.4,1)*1.4/state.mapZoom;
  const viewW=800,viewH=560,scale=viewW/span,x=v=>viewW/2+(v-centerX)*scale,y=v=>viewH/2-(v-centerY)*scale;
  const tickStep=niceStep(span/7);let grid='';
  // Bounded tick indexes avoid a non-advancing float increment for distant offsets.
  const ticks=(center,extent)=>Array.from({length:Math.min(100,Math.ceil(extent/tickStep)+1)},(_,i)=>(Math.ceil((center-extent/2)/tickStep)+i)*tickStep);
  for(const i of ticks(centerX,span))grid+=`<line x1="${x(i)}" y1="0" x2="${x(i)}" y2="${viewH}" stroke="#d1d4d7" stroke-width=".7"/><text x="${x(i)+4}" y="${viewH-44}" fill="#747a80" font-size="9">${num(i,2)}</text>`;
  for(const i of ticks(centerY,viewH/scale))grid+=`<line x1="0" y1="${y(i)}" x2="${viewW}" y2="${y(i)}" stroke="#d1d4d7" stroke-width=".7"/><text x="7" y="${y(i)-5}" fill="#747a80" font-size="9">${num(i,2)}</text>`;
  const transform=g=>`translate(${x(g.x)} ${y(g.y)}) rotate(${-g.angle})`;
  const layers=placed.filter(g=>g!==selected).sort((a,b)=>b.w*b.h-a.w*a.h);
  if(selected)layers.push(selected);
  const images=state.mapMode==='outlines'?'':layers.filter(g=>state.mapMode==='all'||g===selected).map(g=>`<image class="map-image" data-key="${groups.indexOf(g)}" opacity="${state.mapMode==='focus'?1:state.mapOpacity/100}" href="${thumb(primaryScan(g.scans))}" transform="${transform(g)}" x="${-g.w*scale/2}" y="${-g.h*scale/2}" width="${g.w*scale}" height="${g.h*scale}" preserveAspectRatio="none" pointer-events="none"/>`).join('');
  const outlines=layers.map(g=>`<g class="map-hit ${g===selected?'selected':''}" data-action="map-pick" data-key="${groups.indexOf(g)}" tabindex="0" role="button" aria-pressed="${g===selected}" aria-label="${g===selected?'Unfocus':'Focus'} scan ${esc(g.scans[0].acquisition)}, ${g.scans.length} images" transform="${transform(g)}"><title>Scan ${esc(g.scans[0].acquisition)} · ${esc(mapScanDescription(g))}</title><rect class="map-outline-halo" x="${-g.w*scale/2}" y="${-g.h*scale/2}" width="${g.w*scale}" height="${g.h*scale}"/><rect class="map-outline" x="${-g.w*scale/2}" y="${-g.h*scale/2}" width="${g.w*scale}" height="${g.h*scale}"/></g>`).join('');
  return `<svg viewBox="0 0 800 560" role="group" aria-label="AFM scan footprints at recorded sample positions, in micrometers" data-action="map-pick" data-center-x="${centerX}" data-center-y="${centerY}" data-scale="${scale}"><rect width="800" height="560" fill="#e7e9eb"/>${grid}${images}${outlines}</svg><div class="map-label">${icon('map')} SAMPLE COORDINATES <span>µm</span></div>${selected?`<div class="map-selected-label">Scan ${esc(selected.scans[0].acquisition)} · ${esc(mapScanDescription(selected))}${selected.note?`<br>${esc(selected.note)}`:''}</div>`:''}<div class="map-legend">x → &nbsp; y ↑ · ${num(state.mapZoom,1)}×</div><div class="map-tools"><button class="icon-button" data-action="map-zoom" data-value="out" title="Zoom out">${icon('minus')}</button><button class="icon-button" data-action="map-zoom" data-value="fit" title="Fit all positions">${icon('expand')}</button><button class="icon-button" data-action="map-zoom" data-value="in" title="Zoom in">${icon('plus')}</button></div>`;
}
function renderMap(scans){
  const groups=mapGroups(scans),selected=groups.find(g=>g.key===state.mapSelected);
  if(!selected){state.mapSelected=null;if(state.mapMode==='focus')state.mapMode='all';}
  if(!groups.length)return `<div class="empty-state"><h3>No matching images</h3><button class="button" data-action="clear-filters">Reset filters</button></div>`;
  const placed=groups.filter(g=>g.placed),missing=groups.length-placed.length;
  const controls=`<div class="map-controls"><div class="toggle-group" role="group" aria-label="Map display">${[['all','All images'],['focus','Focus'],['outlines','Outlines']].map(([value,label])=>`<button class="${state.mapMode===value?'active':''}" data-action="map-mode" data-value="${value}" aria-pressed="${state.mapMode===value}" ${value==='focus'&&!selected?'disabled':''}>${label}</button>`).join('')}</div><label class="map-opacity">Opacity <input id="map-opacity" aria-label="Map image opacity" type="range" min="10" max="100" step="5" value="${state.mapOpacity}" ${state.mapMode!=='all'?'disabled':''}><output for="map-opacity">${state.mapOpacity}%</output></label><span>${selected?'Click again, empty space, or Escape to show all.':'Click an image to focus; choose a scan where images overlap.'}</span></div>`;
  const aside=`<aside class="map-aside"><div class="map-aside-heading"><h3>Acquisitions</h3><span>${groups.length}</span></div><p class="map-hint">${placed.length} on map${missing?` · ${missing} not placed`:''} · One image per acquisition</p>${groups.map((g,i)=>{const s=primaryScan(g.scans);return `<div class="map-acquisition ${g===selected?'selected':''}"><button class="map-location" data-action="map-select" data-key="${i}" aria-pressed="${g===selected}"><img src="${thumb(s)}" alt=""><span><strong>Scan ${esc(s.acquisition)}</strong><small>${num(s.width_um)} × ${num(s.height_um)} µm · ${g.scans.length} image${g.scans.length===1?'':'s'}</small><small>${g.placed?`x ${num(g.x)} · y ${num(g.y)} µm`:'Not placed · position, angle or size unavailable'}</small>${g.note?`<small>${esc(g.note)}</small>`:''}</span></button>${g===selected?`<button class="button small map-channels" data-action="map-location" data-key="${i}">Open channels (${g.scans.length}) ${icon('chevron')}</button>`:''}</div>`;}).join('')}</aside>`;
  return `${controls}<div class="map-layout"><div class="map-panel">${renderMapPlot(groups,selected)}</div>${aside}</div>${placed.length&&missing?mapUnplaced(groups):''}<div class="map-footnote">${icon('info')}<span>Recorded offsets, sizes and angles define the footprints. Previews retain stored pixel orientation; they are not registered or stitched. Opacity changes display only.</span></div>`;
}
function niceStep(v){const power=10**Math.floor(Math.log10(v));const n=v/power;return (n<2?1:n<5?2:5)*power;}
function renderTray(){document.querySelector('.comparison-tray')?.remove();if(!state.selected.size||!['session','starred'].includes(state.view))return;const tray=document.createElement('div');tray.className='comparison-tray';tray.innerHTML=`<span>${state.selected.size} image${state.selected.size===1?'':'s'} selected</span><button class="button" data-action="compare" ${state.selected.size<2?'disabled':''}>${icon('compare')}Compare images</button><button class="icon-button" data-action="clear-selection" aria-label="Clear selection">${icon('close')}</button>`;document.body.append(tray);}
async function refreshSession(){if(state.session)state.session=await api('session',{id:state.session.id});const boot=await api('bootstrap');state.sessions=boot.sessions;}
async function openSession(id){const serial=++requestSerial;setBusy('Opening session…');try{const session=await api('session',{id});if(serial!==requestSerial)return;state.session=session;state.view='session';state.scan=null;state.selected.clear();state.channel='overview';state.direction='all';state.acquisition='all';state.query='';state.starred=false;state.mapZoom=1;state.mapSelected=null;state.mapMode='all';state.pending=null;renderShell();}finally{setBusy(null);}}
function syncScanSummary(scan){
  for(const session of [state.session,...(state.starredSessions||[])]){
    const item=session?.scans.find(s=>s.id===scan.id);if(!item)continue;
    for(const key of Object.keys(item))if(Object.hasOwn(scan,key))item[key]=scan[key];
    const summary=state.sessions.find(s=>s.id===session.id);
    if(summary){summary.reviewed_count=session.scans.filter(s=>s.review_status==='reviewed').length;summary.starred_count=session.scans.filter(s=>s.starred).length;}
  }
}
async function openScan(id){if(state.view==='detail'&&state.scan?.id===id)return;AFMCanvas.cancel();state.undoStack=[];state.lineDir=null;AFMMask.cancel();state.processingError=null;state.processingAxis='auto';state.levelPoints=[];state.contrastROI=null;await AFMDisplay.endPreview(false);const owner=state.starredSessions?.find(s=>s.scans.some(x=>x.id===id));if(owner)state.session=owner;const serial=++requestSerial;setBusy('Loading image…');try{const scan=await api('scan',{id});if(serial!==requestSerial)return;state.scan=scan;state.view='detail';state.raw=false;state.pending=null;state.profile=null;state.area=null;state.regions=[];state.step=null;state.tool='inspect';await AFMDisplay.load(scan);renderShell();}finally{setBusy(null);}if(serial===requestSerial&&state.autoPrepare&&isHeight(state.scan.channel)&&state.scan.value_unit==='nm'&&!state.scan.operations.length){try{await runOperation('auto_characterize');}catch(error){toast('Auto preparation needs your reference points.',true);}}}
function metric(label,value,unit){return `<div class="metric"><span>${esc(label)}</span><b>${num(value)} <small>${esc(unit)}</small></b></div>`;}
const lineMethods=[['median','Median'],['mean','Mean'],['median_difference','Median of differences'],['modus','Modus'],['matching','Matching'],['polynomial','Polynomial'],['trimmed_mean','Trimmed mean'],['trimmed_difference','Trimmed mean of differences'],['facet_tilt','Facet tilt']];
function opName(op){
  if(['align_scan','align_rows','align_columns'].includes(op.type)){
    const axis=op.type==='align_scan'?'Scan lines':op.type==='align_rows'?'Rows':'Columns';
    if(!op.method)return `${axis} · legacy ${op.type==='align_scan'?'median differences':'median alignment'}`;
    const method=lineMethods.find(([value])=>value===op.method)?.[1]||op.method;
    return `${axis} · ${method}${op.method==='polynomial'?` (degree ${op.degree??1})`:op.method.startsWith('trimmed')?` (${num(100*(op.trim_fraction??.05))}% each tail)`:''}`;
  }
  if(op.type==='plane')return op.method==='gwyddion'?'Plane leveling':'Plane leveling · legacy zero datum';
  if(op.type==='polynomial')return op.mode==='total'?`Polynomial background · total degree ${op.degree??3}`:`Polynomial background · x ${op.degree_x??3}, y ${op.degree_y??3}`;
  return {auto_characterize:'Auto level · line alignment + three-point plane',three_point:'Three-point leveling',auto_2d:'2D material · scan background + planes',terrace_plane:'2D material · up to 3 planes',zero_mean:'Center at zero',zero_min:'Minimum to zero',zero_max:'Maximum to zero'}[op.type]||op.type;
}
function scanAxisLabel(s){const m=s.metadata||{},o=m.orientation||{};return m.format==='Park TIFF'&&o.transform_applied==='none'&&typeof o.swap_fast_slow==='boolean'?(o.swap_fast_slow?'Columns':'Rows')+' · Park header':'Unknown · select an override';}
const lineTypes=['align_scan','align_rows','align_columns'],autoLineTypes=['auto_characterize','auto_2d'];
function recordedAxis(s){const l=scanAxisLabel(s);return l.startsWith('Rows')?'rows':l.startsWith('Columns')?'columns':null;}
// One scan-line slot per recipe: an explicit alignment step, Auto level's built-in terrace-aware correction, or none.
function lineState(ops=state.scan?.operations||[]){
  const explicit=ops.findLastIndex(o=>lineTypes.includes(o.type));
  if(explicit>=0){const o=ops[explicit];return {kind:'method',method:o.method||'legacy',dir:o.type==='align_columns'||(o.type==='align_scan'&&o.axis==='columns')?'columns':o.type==='align_rows'||(o.type==='align_scan'&&o.axis==='rows')?'rows':recordedAxis(state.scan)||'rows'};}
  if(ops.some(o=>autoLineTypes.includes(o.type)&&o.line_correction!==false))return {kind:'auto'};
  return {kind:'off'};
}
function lineRecipe(choice){
  const ops=structuredClone(state.scan.operations||[]);
  const explicit=ops.findLastIndex(o=>lineTypes.includes(o.type));
  if(explicit>=0)ops.splice(explicit,1);
  const autoIndex=ops.findLastIndex(o=>autoLineTypes.includes(o.type));
  if(autoIndex>=0)ops[autoIndex].line_correction=choice==='auto';
  if(choice==='off'||choice==='auto')return ops;
  const op={type:state.lineDir==='columns'?'align_columns':'align_rows',method:choice};
  if(choice==='polynomial')op.degree=state.lineDegree;
  if(choice.startsWith('trimmed'))op.trim_fraction=state.lineTrim/100;
  Object.assign(op,AFMMask.parameters());
  // Replace in place; otherwise align before Auto level's plane fit, or first in the recipe.
  ops.splice(explicit>=0?explicit:autoIndex>=0?autoIndex:0,0,op);
  return ops;
}
const lineChoiceLabels={off:'Off',auto:'Terrace (Auto level)',median:'Median',mean:'Mean',matching:'Matching',modus:'Modus',median_difference:'Median of differences',polynomial:'Polynomial',trimmed_mean:'Trimmed mean',trimmed_difference:'Trimmed mean of differences',facet_tilt:'Facet tilt'};
async function applyLine(choice){
  if(state.raw||state.loading)return;
  await AFMDisplay.pending();
  let operations=lineRecipe(choice),dropped=null;const previous=structuredClone(state.scan.operations||[]);
  setBusy('Aligning scan lines…');
  try{
    try{state.scan=await api('process',{id:state.scan.id,operations});}
    catch(error){
      // Auto level's plane gate can reject the new lines. Keep the chosen method, drop that step, and ask for points.
      if(!operations.some(o=>autoLineTypes.includes(o.type))||['off','auto'].includes(choice))throw error;
      dropped=error.message;operations=operations.filter(o=>!autoLineTypes.includes(o.type));
      state.scan=await api('process',{id:state.scan.id,operations});
    }
    state.processingError=dropped?`Auto level could not fit a reference plane after ${lineChoiceLabels[choice]} alignment, so that step was removed. Choose three points on one plane, or undo to restore it.`:null;
    state.undoStack.push(previous);state.revision++;state.profile=null;state.step=null;state.area=null;state.regions=[];await AFMDisplay.load(state.scan);syncScanSummary(state.scan);renderContent();
    toast(dropped?`Scan lines: ${lineChoiceLabels[choice]}. Auto level removed — needs your points.`:choice==='off'?'Scan-line correction removed.':choice==='auto'?'Using Auto level’s terrace-aware line correction.':`Scan lines: ${lineChoiceLabels[choice]} · ${state.lineDir}.`,false,{label:'Undo',action:'undo'});}
  catch(error){toast(error.message,true);}finally{setBusy(null);}
}
function renderScanLines(s){
  const disabled=state.raw?'disabled':'',height=isHeight(s.channel)&&s.value_unit==='nm',ls=lineState(),recorded=recordedAxis(s);
  if(ls.kind==='method')state.lineDir=ls.dir;else state.lineDir=state.lineDir||recorded||'rows';
  const active=ls.kind==='method'?(ls.method==='legacy'?'':ls.method):ls.kind;
  const hasAuto=(s.operations||[]).some(o=>autoLineTypes.includes(o.type));
  const chip=(v,l,extra='')=>`<button type="button" class="method-chip ${active===v?'active':''}" data-action="line-choice" data-choice="${v}" aria-pressed="${active===v}" title="${esc(lineChoiceLabels[v])}" ${disabled||extra}>${l}</button>`;
  const more=[['median_difference','Median Δ'],['polynomial','Polynomial'],['trimmed_mean','Trimmed'],['trimmed_difference','Trimmed Δ'],['facet_tilt','Facet tilt']];
  return `<section class="inspector-section scanline-section"><div class="inspector-title">Scan lines<span class="tag">${ls.kind==='off'?'Not corrected':ls.kind==='auto'?'Terrace · from Auto level':ls.method==='legacy'?'Legacy step':'Applied'}</span></div>
    ${state.raw?'<div class="lock-note lock-bar"><span>Showing Original. Switch to Result to apply corrections.</span><button class="button small" data-action="raw" data-value="processed">Show Result</button></div>':''}
    <div class="segmented" role="group" aria-label="Line direction">${['rows','columns'].map(d=>`<button type="button" data-action="line-dir" data-dir="${d}" aria-pressed="${state.lineDir===d}" ${disabled}>${d==='rows'?'Rows':'Columns'}${recorded===d?'<small>file</small>':''}</button>`).join('')}</div>
    <div class="method-chips">${chip('off','Off')}${hasAuto?chip('auto','Terrace'):''}${[['median','Median'],['mean','Mean'],['matching','Matching'],['modus','Modus']].map(([v,l])=>chip(v,l)).join('')}</div>
    <details id="more-line-methods" class="more-methods" ${more.some(([v])=>v===active)?'open':''}><summary>More methods</summary><div class="method-chips">${more.map(([v,l])=>chip(v,l,v==='facet_tilt'&&!height?'disabled':'')).join('')}</div></details>
    ${active==='polynomial'?`<label class="inline-field">Degree<input id="line-degree" type="number" min="0" max="5" step="1" value="${state.lineDegree}" ${disabled}></label>`:''}
    ${active.startsWith('trimmed')?`<label class="inline-field">Trim each tail (%)<input id="line-trim" type="number" min="0" max="50" step="1" value="${state.lineTrim}" ${disabled}></label>`:''}
    <p class="operation-note">Click a method to apply it; it replaces the previous one. Line correction can remove features spanning a whole line, so compare with Original.</p>
  </section>`;
}
function renderProcessing(s){
  const disabled=state.raw?'disabled':'';
  const height=isHeight(s.channel)&&s.value_unit==='nm';
  const heightOnly=disabled||(!height?'disabled':'');
  const model=s.history?.findLast(h=>['auto_characterize','auto_2d','terrace_plane'].includes(h.type))?.model;
  const lockNote=state.raw?'Showing Original. Switch to Result to apply corrections.':'';
  const op=(type,label,extra='')=>{const off=extra||disabled;return `<button class="operation-button" data-action="operation" data-operation="${type}" ${off} ${off?`title="${esc(lockNote||'Needs a calibrated height channel')}"`:''}><span>${label}</span>${icon('plus')}</button>`;};
  const lockBar=lockNote?`<div class="lock-note lock-bar"><span>${lockNote}</span><button class="button small" data-action="raw" data-value="processed">Show Result</button></div>`:'';
  return `<section class="inspector-section processing-section"><div class="inspector-title">Level surface<span class="tag">Saved · ⌘Z to undo</span></div>
    ${!height?'<p class="operation-note">Leveling needs a calibrated height channel. Scan-line and background corrections still apply.</p>':''}
    <div class="level-actions">
      <button class="level-action" data-action="operation" data-operation="auto_characterize" ${heightOnly}><strong>${icon('plane')}Auto level</strong><small>Align lines, fit one plane</small></button>
      <button class="level-action ${state.tool==='level'?'active':''}" data-action="tool" data-tool="level" data-panel="prepare" ${heightOnly}><strong>${icon('cursor')}3-point level</strong><small>Click 3 points on one plane</small></button>
    </div>
    ${state.tool==='level'?`<p class="operation-note level-progress">Click three clean, well-spaced points on the same plane · <b><span id="level-point-count">${state.levelPoints.length}</span>/3</b>. Each point averages a 5 × 5 pixel patch.</p>`:''}
    <div class="fit-reference"><span>Reference</span><strong>${esc(referenceDescription())}</strong><span class="fit-reference-actions"><button class="button small" data-action="tool" data-tool="area" data-panel="prepare" ${disabled}>${state.area?'Redraw area':'Draw area'}</button>${state.area?'<button class="button small" data-action="clear-area">Clear</button>':''}</span>
    ${state.area&&!AFMMask.active()?`<label>Use area as<select id="reference-mode" ${disabled}>${[['include','Fit inside area'],['exclude','Fit outside area'],['ignore','Whole image']].map(([value,label])=>`<option value="${value}" ${state.referenceMode===value?'selected':''}>${label}</option>`).join('')}</select></label>`:''}</div>
    ${model?`<details id="fit-model"><summary>${model.plane_count} fitted plane${model.plane_count===1?'':'s'} · proposal</summary><p class="operation-note">Fit-reference RMS ${num(model.residual_rms,4)} ${esc(s.value_unit)}. Tilt: x ${num(model.coefficients[1],4)}, y ${num(model.coefficients[2],4)} ${esc(s.value_unit)} across the image. ${model.reference_coverage!==undefined?`${num(100*model.reference_coverage,1)}% reference support · reference plane ${(model.reference_plane??0)+1}`:(model.pairs||[]).map(p=>`${p.axis}: ${p.accepted_pairs}/${p.candidate_pairs} pairs`).join(' · ')}.</p><button class="button small" data-action="inspect-plane">Inspect fitted planes</button>${model.warnings.map(w=>`<p class="operation-note">${esc(w)}</p>`).join('')}</details>`:''}
    <details id="more-corrections" class="processing-disclosure" ${state.processingError?'open':''}><summary>More corrections</summary>${lockBar}
      <label>Fast scan axis<select id="processing-axis" ${disabled}><option value="auto" ${state.processingAxis==='auto'?'selected':''}>Automatic · ${esc(scanAxisLabel(s))}</option><option value="rows" ${state.processingAxis==='rows'?'selected':''}>Rows · manual override</option><option value="columns" ${state.processingAxis==='columns'?'selected':''}>Columns · manual override</option></select></label>
      <div class="correction-group"><div class="correction-heading">2D material terraces</div>
        <label class="inline-check"><input id="auto-line-correction" type="checkbox" ${state.autoLineCorrection?'checked':''} ${disabled}>Correct scan-line background <small>(off keeps slow-axis shape)</small></label>
        ${op('auto_2d',`${icon('plane')}Fit up to 3 terrace planes`,heightOnly)}</div>
      <div class="correction-group"><div class="correction-heading">Background</div>
        ${op('plane',`${icon('plane')}Subtract reference plane`)}
        <label>Polynomial<select id="polynomial-mode" ${disabled}><option value="independent" ${state.polynomialMode==='independent'?'selected':''}>Independent x and y degrees</option><option value="total" ${state.polynomialMode==='total'?'selected':''}>Limited total degree</option></select></label>
        ${state.polynomialMode==='total'?`<label>Total degree<input id="polynomial-degree" type="number" min="0" max="11" step="1" value="${state.polynomialDegree}" ${disabled}></label>`:`<div class="field-pair"><label>X degree<input id="polynomial-degree-x" type="number" min="0" max="11" step="1" value="${state.polynomialDegreeX}" ${disabled}></label><label>Y degree<input id="polynomial-degree-y" type="number" min="0" max="11" step="1" value="${state.polynomialDegreeY}" ${disabled}></label></div>`}
        ${op('polynomial','Subtract polynomial background')}</div>
      <div class="correction-group"><div class="correction-heading">Zero reference</div>
        <div class="button-row">${op('zero_mean','Mean')}${op('zero_min','Minimum')}${op('zero_max','Maximum')}</div></div>
      ${(s.history||[]).filter(h=>h.type==='align_scan').slice(-1).map(h=>`<p class="operation-note">Last alignment: ${esc(h.model.axis)} · ${esc(h.model.axis_source)}.</p>`).join('')}
    </details>
    <label class="auto-prepare-setting"><input id="auto-prepare-on-open" type="checkbox" ${state.autoPrepare?'checked':''}>Auto level new height images when opened</label>
  </section>`;
}
function inspectPlane(){
  const s=state.scan,model=s.history?.findLast(h=>['auto_characterize','auto_2d','terrace_plane'].includes(h.type))?.model;if(!model)return;const ratio=s.width_um/s.height_um,fitW=Math.max(1,Math.round(240*Math.min(1,ratio))),fitH=Math.max(1,Math.round(240/Math.max(1,ratio)));
  showModal('Terrace plane fit',`<p>Removed background in ${esc(s.value_unit)} (left), including enabled scan-line correction. Terrace plane assignments (right): shades distinguish fitted planes; dark pixels are excluded from fitting or outside the reference. These are fit assignments, not identified materials.</p><div style="display:flex;gap:12px"><canvas id="fit-plane" width="${fitW}" height="${fitH}" style="width:48%;height:auto" aria-label="Removed fitted plane"></canvas><canvas id="fit-support" width="${fitW}" height="${fitH}" style="width:48%;height:auto" aria-label="Terrace plane assignments"></canvas></div><p>Offset ${num(model.coefficients[0],4)}; x tilt ${num(model.coefficients[1],4)}; y tilt ${num(model.coefficients[2],4)} ${esc(s.value_unit)}. One reference tilt is removed everywhere. Other terrace tilts remain. Review the fitted background and use Undo if it is unsuitable.</p>`);
  const coeff=model.coefficients,line=model.line_correction,background=(xx,yy)=>{const offsets=line?.offsets||[];const t=line?.axis==='columns'?xx:yy;const v=offsets.length?offsets[Math.min(offsets.length-1,Math.floor(t*offsets.length))]:0;return coeff[0]+coeff[1]*xx+coeff[2]*yy+v;};
  let lo=Infinity,hi=-Infinity;for(let y=0;y<fitH;y++)for(let x=0;x<fitW;x++){const v=background((x+.5)/fitW,(y+.5)/fitH);lo=Math.min(lo,v);hi=Math.max(hi,v);}
  const assignments=Uint8Array.from(atob(model.assignment_uint8_base64),c=>c.charCodeAt(0));
  for(const id of ['fit-plane','fit-support']){const c=document.getElementById(id),ctx=c.getContext('2d'),im=ctx.createImageData(fitW,fitH);for(let y=0;y<fitH;y++)for(let x=0;x<fitW;x++){
    const xx=(x+.5)/fitW,yy=(y+.5)/fitH;let rgb;
    if(id==='fit-plane')rgb=color((background(xx,yy)-lo)/(hi-lo||1));
    else{const col=Math.min(s.width-1,Math.floor(xx*s.width)),row=Math.min(s.height-1,Math.floor(yy*s.height));const label=assignments[row*s.width+col];rgb=label===255?[38,42,46]:[[210,216,221],[140,155,165],[80,100,115]][label];}
    im.data.set([...rgb,255],4*(y*fitW+x));}ctx.putImageData(im,0,0);}
}
const inspectorTabs = [['view','View','1'],['prepare','Prepare','2'],['measure','Measure','3'],['record','Record','4']];
function rememberInspector() {
  document.querySelectorAll('.inspector-panel').forEach(panel => { if (!panel.hidden && !panel.closest('.inspector[hidden]')) state.inspectorScroll[panel.dataset.panel] = panel.scrollTop; });
  document.querySelectorAll('.inspector details[id]').forEach(detail => { state.inspectorDetails[detail.id] = detail.open; });
}
function restoreInspector() {
  document.querySelectorAll('.inspector details[id]').forEach(detail => {
    if (detail.id === 'more-corrections' && state.processingError) detail.open = true;
    else if (Object.hasOwn(state.inspectorDetails, detail.id)) detail.open = state.inspectorDetails[detail.id];
  });
  document.querySelectorAll('.inspector-panel').forEach(panel => { panel.scrollTop = state.inspectorScroll[panel.dataset.panel] || 0; });
}
function setInspectorHidden(hidden) {
  if (hidden) { AFMCanvas.cancel(); AFMMask.cancel(); }
  state.inspectorHidden = hidden;
  document.querySelector('.detail-view')?.classList.toggle('controls-hidden', hidden);
  try { localStorage.setItem('afm-inspector-hidden', String(hidden)); } catch {}
  const panel = document.getElementById('image-inspector');
  if (panel) panel.hidden = hidden;
  const button = document.querySelector('[data-action="toggle-inspector"]');
  if (button) {
    const label = hidden ? 'Show controls and overlays' : 'Hide controls and overlays';
    button.setAttribute('aria-label', label);
    button.title = label;
    button.setAttribute('aria-expanded', String(!hidden));
  }
}
function showInspector(tab, focus = false) {
  if (!inspectorTabs.some(([id]) => id === tab)) return;
  rememberInspector(); setInspectorHidden(false); state.inspectorTab = tab;
  document.querySelectorAll('[data-inspector-tab]').forEach(button => {
    const active = button.dataset.inspectorTab === tab;
    button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
  });
  document.querySelectorAll('.inspector-panel').forEach(panel => { panel.hidden = panel.dataset.panel !== tab; });
  restoreInspector();
  if (focus) document.getElementById('inspector-tab-'+tab)?.focus();
}
function selectTool(tool, panel) {
  const blocked = toolBlocked(tool);
  if (blocked) { toast(blocked + '.'); return; }
  if (!['inspect','pan'].includes(tool)) setInspectorHidden(false);
  const changed = state.tool !== tool;
  AFMCanvas.cancel(); AFMMask.cancel(); state.tool = tool;
  if (changed && !['inspect','contrast','pan'].includes(tool)) {
    state.area = null; state.profile = null; state.regions = []; state.step = null;
  }
  if (tool === 'level') state.levelPoints = [];
  if (panel) state.inspectorTab = panel;
  else if (tool === 'contrast') state.inspectorTab = 'view';
  else if (tool === 'mask') state.inspectorTab = 'prepare';
  else if (['profile','step'].includes(tool)) state.inspectorTab = 'measure';
  else if (tool === 'area' && !['prepare','view'].includes(state.inspectorTab)) state.inspectorTab = 'measure';
  renderContent();
}
function referenceDescription() {
  const preview = state.pending?.at(-1);
  if (preview) {
    const masked = !!preview.mask && preview.masking !== 'ignore';
    const base = masked ? (preview.masking === 'include' ? 'Only marked pixels' : 'Marked pixels excluded') : 'All valid pixels';
    if (!preview.roi) return base;
    if (masked) return base + ' · inside area';
    return preview.masking === 'ignore' ? base : preview.masking === 'exclude' ? 'Outside selected area' : 'Selected area';
  }
  const mask = state.scan.mask;
  const base = AFMMask.active() ? (mask.masking === 'include' ? 'Only marked pixels' : 'Marked pixels excluded') : 'All valid pixels';
  if (!state.area) return base;
  if (AFMMask.active()) return base + ' · inside area';
  return state.referenceMode === 'ignore' ? base : state.referenceMode === 'exclude' ? 'Outside selected area' : 'Selected area';
}
function measurementDescription() {
  const mask = state.scan.mask;
  const base = AFMMask.active() ? (mask.masking === 'include' ? 'Only marked pixels' : 'Marked pixels excluded') : 'All valid pixels';
  return state.area ? base + ' · inside selected area' : base;
}
function renderMeasureTools(s) {
  return `<section class="inspector-section measurement-tools"><div class="inspector-title">Measure surface<span class="tag">${esc(s.value_unit)}</span></div>
    ${[['profile','Line profile','Cross-section across an edge','P'],['step',isHeight(s.channel)?'Step height':'Region difference','Mean height of region B − A','T'],['area',isHeight(s.channel)?'Area roughness':'Area statistics','Statistics inside a rectangle','A']].map(([tool,title,description,key])=>`<button class="measurement-tool ${state.tool===tool?'active':''}" data-action="tool" data-tool="${tool}" data-panel="measure" aria-pressed="${state.tool===tool}" ${toolBlocked(tool)?'disabled':''}><span><strong>${title}</strong><small>${description}</small></span><kbd>${key}</kbd></button>`).join('')}
    <p class="operation-note ${state.raw?'lock-note':''}">${state.raw?'Switch to Result to measure.':esc(measurementDescription())+'. Measurements use full-resolution data.'}</p>
    ${state.tool==='step'?`<div class="step-progress" aria-label="Step reference regions"><span class="${state.regions.length?'complete':'current'}">A · ${state.regions.length?'Selected':'Draw substrate'}</span><span class="${state.regions.length===2?'complete':state.regions.length===1?'current':''}">B · ${state.regions.length===2?'Selected':'Draw flake'}</span></div>${state.regions.length===2?'<p class="operation-note">Draw again to start a new region A.</p>':''}<p class="operation-note">Choose flat regions away from edges. B − A is a height difference; it does not identify a layer count.</p>`:''}
  </section>`;
}
function renderInspector(s) {
  const masked=AFMMask.active(), stats=state.area?.statistics||state.area||(masked?(s.masked_statistics||{}):s.statistics), warnings=s.warnings||s.metadata?.warnings||[];
  const view = AFMDisplay.render();
  const prepare = `${renderScanLines(s)}${renderProcessing(s)}${AFMMask.render()}`;
  const measure = `${renderMeasureTools(s)}<section class="inspector-section"><div class="inspector-title">${state.area?'Selected area':masked?'Selected pixels':'Surface statistics'}<span class="tag">${state.area?'ROI':masked?'Mask':'Whole image'}</span></div><div class="metrics-grid">${metric(isHeight(s.channel)?'Sq · RMS roughness':'RMS variation',stats.sq,s.value_unit)}${metric(isHeight(s.channel)?'Sa · Mean roughness':'Mean absolute variation',stats.sa,s.value_unit)}${metric('Peak to valley',stats.peak_to_valley,s.value_unit)}${metric('Mean',stats.mean,s.value_unit)}</div><details style="margin-top:10px"><summary>More statistics</summary><div class="metrics-grid">${metric('Median',stats.median,s.value_unit)}${metric('Sp · Peak above mean',stats.sp,s.value_unit)}${metric('Sv · Pit below mean',stats.sv,s.value_unit)}${metric('Skewness',stats.skewness,'')}${metric('Excess kurtosis',stats.excess_kurtosis,'')}${metric('Valid pixels',stats.count,'')}</div></details><p class="operation-note" style="margin-top:10px">Relative to the mean of valid pixels. ${state.raw?'Values for the original data.':state.area?'Selected-region statistics.':masked?esc(s.masked_statistics_error||'Current mask applied.'):s.operations?.length?'Values for the saved result.':'Stored data; no leveling applied.'}</p></section>`;
  const record = `<section class="inspector-section"><div class="inspector-title">Processing history<button class="icon-button" data-action="undo" title="${s.operations?.length?'Undo '+esc(opName(s.operations.at(-1)))+' (⌘Z)':'Nothing to undo'}" aria-label="Undo last correction" ${!s.operations?.length?'disabled':''}>${icon('undo')}</button></div><div class="history-item"><span class="history-number">0</span><div>Original calibrated data<small>Preserved · never overwritten</small></div></div>${(s.operations||[]).map((op,i)=>`<div class="history-item"><span class="history-number">${i+1}</span><div>${esc(opName(op))}<small>${op.mask?('Saved mask snapshot'+(op.roi?' · selected area':'')):op.roi?(op.masking==='exclude'?'Outside selected reference region':op.masking==='ignore'?'All valid pixels':'Selected reference region'):op.type==='auto_2d'?'Masked terrace fit':op.type==='terrace_plane'?'Within-terrace pairs':'All valid pixels'}</small></div></div>`).join('')}</section><section class="inspector-section"><details id="acquisition-provenance" ${warnings.length?'open':''}><summary>Acquisition & provenance ${warnings.length?'· '+warnings.length+' note'+(warnings.length>1?'s':''):''}</summary>${warnings.map(w=>`<div class="warning">${esc(w)}</div>`).join('')}<dl class="metadata-list"><dt>Channel</dt><dd>${esc(s.channel)}</dd><dt>Direction</dt><dd>${esc(s.direction)}</dd><dt>Direction source</dt><dd>${esc(s.metadata?.direction_source||'Not recorded')}</dd><dt>Header fast / slow</dt><dd>${esc(s.metadata?.orientation?.header_fast_direction||'Unknown')} / ${esc(s.metadata?.orientation?.slow_direction||'Unknown')}</dd><dt>Fast scan axis</dt><dd>${esc(scanAxisLabel(s))}</dd><dt>Scan angle</dt><dd>${num(s.metadata?.scan_angle_deg)}°</dd><dt>File</dt><dd>${esc(s.filename)}</dd><dt>Position</dt><dd>${position(s)?`${num(position(s).x)}, ${num(position(s).y)} µm`:'Not available'}</dd><dt>Pixel size</dt><dd>${num(s.width_um/s.width*1000)} × ${num(s.height_um/s.height*1000)} nm</dd><dt>Origin</dt><dd>${state.session.synthetic?'Synthetic ground truth':'Instrument data'}</dd><dt>Review</dt><dd>Workflow status; no physical interpretation implied</dd></dl></details></section>`;
  const panels={view,prepare,measure,record};
  return `<aside id="image-inspector" class="inspector" aria-label="Image inspector" ${state.inspectorHidden?'hidden':''}><div class="inspector-nav" role="tablist" aria-label="Characterization workflow">${inspectorTabs.map(([id,label,key])=>`<button id="inspector-tab-${id}" role="tab" aria-controls="inspector-panel-${id}" aria-selected="${state.inspectorTab===id}" tabindex="${state.inspectorTab===id?0:-1}" data-action="inspector-tab" data-tab="${id}" data-inspector-tab="${id}" title="${label} (${key})">${label}</button>`).join('')}</div>
    ${state.processingError?`<section class="preparation-error" role="alert"><strong>Reference plane needs your input</strong><p>${esc(state.processingError)}</p><button class="button small" data-action="tool" data-tool="level" data-panel="prepare">Choose 3 leveling points</button></section>`:''}
    ${inspectorTabs.map(([id])=>`<div class="inspector-panel" id="inspector-panel-${id}" data-panel="${id}" role="tabpanel" aria-labelledby="inspector-tab-${id}" tabindex="0" ${state.inspectorTab===id?'':'hidden'}>${panels[id]}</div>`).join('')}
    <div class="inspector-footer"><span title="Reference for the next correction: ${esc(referenceDescription())}">Reference: ${esc(referenceDescription())}</span><button data-action="help" title="Keyboard shortcuts">${icon('help')}Keys</button></div></aside>`;
}
function counterpart(s,related){return related.find(r=>r.channel===s.channel&&r.direction!==s.direction&&['Forward','Backward'].includes(r.direction));}
function toolBlocked(tool){
  if(['inspect','contrast','pan'].includes(tool))return '';
  if(state.raw)return 'Switch to Result first';
  return '';
}
function renderDetail(main){const s=state.scan;if(!s){main.innerHTML='';return;}const priorStage=main.querySelector('.canvas-stage');const retained=priorStage?.dataset.imageId===s.id?priorStage:null;if(retained)AFMCanvas.cancel();const related=state.session.scans.filter(x=>acquisitionKey(x)===acquisitionKey(s));main.innerHTML=`<div class="detail-view ${state.inspectorHidden?'controls-hidden':''}"><div class="detail-header"><button class="detail-back" data-action="back" title="Back to session">${icon('back')}</button><div><h2>Scan ${esc(s.acquisition)} <span style="color:#767b80;font-weight:400">/</span> ${esc(s.channel)}</h2><div class="detail-subtitle">${esc(s.direction)} · ${num(s.width_um)} × ${num(s.height_um)} µm · ${s.width} × ${s.height} px</div></div><div class="detail-actions"><label class="select-wrap"><select id="related-scan" aria-label="Switch channel or direction">${sorted(related).map(r=>`<option value="${esc(r.id)}" ${r.id===s.id?'selected':''}>${esc(r.channel)} · ${esc(r.direction)}</option>`).join('')}</select></label>${counterpart(s,related)?`<button class="button small" data-action="open" data-id="${esc(counterpart(s,related).id)}" title="Show the ${esc(counterpart(s,related).direction.toLowerCase())} scan of this channel (B)">${icon('swap')}${esc(counterpart(s,related).direction)}</button>`:''}<button class="icon-button ${s.starred?'active':''}" data-action="star" data-id="${esc(s.id)}" title="${s.starred?'Unstar':'Star'} image (S)">${icon('star')}</button><button class="button small ${s.review_status==='reviewed'?'active':''}" data-action="review">${icon('check')}${s.review_status==='reviewed'?'Reviewed':'Mark reviewed'}</button><button class="button small" data-action="export">${icon('download')}Export</button><button class="icon-button controls-toggle" data-action="toggle-inspector" aria-controls="image-inspector canvas-tools mask-canvas draw-overlay profile-panel" aria-expanded="${!state.inspectorHidden}" aria-label="${state.inspectorHidden?'Show controls and overlays':'Hide controls and overlays'}" title="${state.inspectorHidden?'Show controls and overlays':'Hide controls and overlays'}">${icon('chevron')}</button></div></div><div class="detail-body"><section class="image-workspace"><div class="canvas-toolbar" id="canvas-tools"><div class="toggle-group" aria-label="Image tools">${[['inspect','cursor','Inspect'],['pan','hand','Pan'],['contrast','contrast','Contrast'],['profile','line','Profile'],['area','crop','Area'],['mask','brush','Mask'],['step','layers',isHeight(s.channel)?'Step':'Difference']].map(([t,i,l])=>{const blocked=toolBlocked(t);return `<button class="${state.tool===t?'active':''} ${blocked?'blocked':''}" data-action="tool" data-tool="${t}" aria-pressed="${state.tool===t}" ${blocked?'aria-disabled="true"':''} title="${l} (${{inspect:'V',pan:'H',contrast:'C',profile:'P',area:'A',mask:'M',step:'T'}[t]})${blocked?' · '+blocked:''}">${icon(i)}${l}</button>`;}).join('')}</div><div class="toggle-group"><button class="${!state.raw?'active':''}" data-action="raw" data-value="processed">Result</button><button class="${state.raw?'active':''}" data-action="raw" data-value="raw">Original</button></div><button class="button small quick-contrast" data-display-action="auto" title="Auto contrast · display only">Auto contrast</button><span class="hint">${state.tool==='contrast'?'Drag to select · Drag region or handles to adjust':state.tool==='pan'?'Drag to pan · Scroll to zoom':state.tool==='level'?'Click 3 points on the same plane':state.tool==='profile'?'Drag a line across the image':state.tool==='area'?'Drag a region to measure':state.tool==='mask'?'Draw to add or erase marked pixels':state.tool==='step'?`Draw reference region ${state.regions.length===1?'B':'A'}`:'Move over the image to inspect'}</span></div><div class="canvas-stage" aria-label="Image canvas. Scroll to zoom; hold Space and drag to pan."><div class="canvas-wrap" style="aspect-ratio:${s.width_um/s.height_um};--scan-aspect:${s.width_um/s.height_um}"><canvas id="height-canvas" tabindex="0" aria-label="Calibrated ${esc(s.channel)} image"></canvas><canvas id="mask-canvas" aria-hidden="true"></canvas><svg class="draw-overlay" id="draw-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Draw a profile or measurement region"></svg><div class="canvas-axis-x"><span>0</span><span>${num(s.width_um)} µm</span></div><div class="canvas-axis-y"><span>0</span><span>${num(s.height_um)} µm</span></div></div><div id="colorbar" class="colorbar"></div><div class="colorbar-labels"><span id="color-max"></span><span>${esc(s.value_unit)}</span><span id="color-min"></span></div><div class="canvas-navigation" role="group" aria-label="Canvas navigation"><span class="navigation-hint">Scroll to zoom · Space + drag to pan</span><button type="button" class="icon-button" data-canvas-action="zoom-out" title="Zoom out (−)" aria-label="Zoom out">${icon('minus')}</button><output id="canvas-zoom" title="Magnification relative to Fit">100%</output><button type="button" class="icon-button" data-canvas-action="zoom-in" title="Zoom in (+)" aria-label="Zoom in">${icon('plus')}</button><button type="button" class="button small" data-canvas-action="fit" title="Fit image (F)">Fit</button></div></div><div class="canvas-status"><span id="cursor-value">${esc(s.channel)} · ${esc(s.value_unit)}</span><span class="right">${state.raw?'Original':s.operations?.length?`${s.operations.length} saved correction${s.operations.length===1?'':'s'}`:'Original'} · ${s.data_width||s.width} × ${s.data_height||s.height} display</span></div><div class="profile-panel ${['inspect','pan','mask','area','contrast','level'].includes(state.tool)&&!state.profile&&!state.step?'hidden':''}" id="profile-panel">${renderMeasurement()}</div></section>${renderInspector(s)}</div></div>`;if(retained)main.querySelector('.canvas-stage').replaceWith(retained);main.querySelector('.canvas-stage').dataset.imageId=s.id;restoreInspector();bindCanvas();requestAnimationFrame(()=>{paintCanvas();restoreDrawing();});}
function flattenData(s){return Array.isArray(s.data?.[0])?s.data.flat():s.data||[];}
const palettes={amber:[[0,[25,15,13]],[.22,[88,42,18]],[.5,[173,105,35]],[.76,[230,183,86]],[1,[255,246,205]]],viridis:[[0,[68,1,84]],[.25,[59,82,139]],[.5,[33,145,140]],[.75,[94,201,98]],[1,[253,231,37]]],gray:[[0,[12,17,16]],[1,[246,249,244]]]};
function color(v,palette=state.palette){const p=palettes[palette]||palettes.amber;v=Math.max(0,Math.min(1,v));let j=1;while(j<p.length-1&&v>p[j][0])j++;const lo=p[j-1],hi=p[j],t=(v-lo[0])/(hi[0]-lo[0]);return lo[1].map((x,i)=>Math.round(x+(hi[1][i]-x)*t));}
// Keep interpolation exact while avoiding temporary RGB arrays for every pixel.
const pixelBuffers=new WeakMap(),paintedImages=new WeakMap();
function paintPixels(canvas,scan,lo,hi,palette=state.palette){
  const w=scan.data_width||scan.width,h=scan.data_height||scan.height,data=flattenData(scan);
  if(canvas.width!==w)canvas.width=w;if(canvas.height!==h)canvas.height=h;
  let buffer=pixelBuffers.get(canvas);
  if(!buffer||buffer.w!==w||buffer.h!==h){const ctx=canvas.getContext('2d');buffer={w,h,ctx,image:ctx.createImageData(w,h)};pixelBuffers.set(canvas,buffer);}
  const {ctx,image:im}=buffer,pixels=im.data,p=palettes[palette]||palettes.amber,span=hi-lo||1;
  for(let i=0;i<data.length;i++){
    const offset=i*4,value=data[i];pixels[offset+3]=255;
    if(value===null||!Number.isFinite(value)){pixels[offset]=168;pixels[offset+1]=177;pixels[offset+2]=158;continue;}
    const v=Math.max(0,Math.min(1,(value-lo)/span));let j=1;
    while(j<p.length-1&&v>p[j][0])j++;
    const low=p[j-1],high=p[j],t=(v-low[0])/(high[0]-low[0]);
    for(let c=0;c<3;c++)pixels[offset+c]=Math.round(low[1][c]+(high[1][c]-low[1][c])*t);
  }
  ctx.putImageData(im,0,0);
}
function paintCanvas(){
  const canvas=document.getElementById('height-canvas');if(!canvas||!state.scan)return;
  const [lo,hi]=AFMDisplay.range(),s=state.scan,w=s.data_width||s.width,h=s.data_height||s.height;canvasRanges=[lo,hi];
  const previous=paintedImages.get(canvas);
  if(!previous||previous.data!==s.data||previous.w!==w||previous.h!==h||previous.lo!==lo||previous.hi!==hi||previous.palette!==state.palette){
    paintPixels(canvas,s,lo,hi);paintedImages.set(canvas,{data:s.data,w,h,lo,hi,palette:state.palette});
  }
  document.getElementById('color-max').textContent=num(hi);document.getElementById('color-min').textContent=num(lo);
  document.getElementById('colorbar').style.background=`linear-gradient(to top,${palettes[state.palette].map(([v,rgb])=>`rgb(${rgb}) ${v*100}%`).join(',')})`;
}
function profileControls(){return `<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:8px 0"><label>Interpolation <select id="profile-interpolation" ${state.raw||state.pending?'disabled':''}><option value="linear" ${state.profileInterpolation==='linear'?'selected':''}>Linear</option><option value="nearest" ${state.profileInterpolation==='nearest'?'selected':''}>Nearest</option></select></label><label>Averaging width <input id="profile-width" type="number" min="1" max="128" step="1" value="${state.profileWidth}" style="width:64px" ${state.raw||state.pending?'disabled':''}> px</label></div>`;}
async function measureProfile(start,end){
  const result=await api('profile',{id:state.scan.id,start,end,interpolation:state.profileInterpolation,averaging_width_pixels:state.profileWidth,sampling:'gwyddion',...AFMMask.parameters()});
  result.selection={start,end};state.profile=result;
}
function renderMeasurement(){if(state.step){return `<h3>${isHeight(state.scan.channel)?'Step height':'Region difference'} · B − A <span>Mean difference between selected regions</span></h3><div class="metrics-grid" style="max-width:580px;margin-top:13px;grid-template-columns:repeat(3,1fr)">${metric(isHeight(state.scan.channel)?'Signed height':'Signed difference',state.step.difference,state.scan.value_unit)}${metric('Region A mean',state.step.region_a?.mean,state.scan.value_unit)}${metric('Region B mean',state.step.region_b?.mean,state.scan.value_unit)}</div>`;}if(!state.profile)return `${state.tool==='profile'?profileControls():''}<h3>${state.tool==='step'?'Step height':state.tool==='area'?'Area measurement':'Line profile'}<span>Measurements use full-resolution data</span></h3><div class="profile-placeholder">${state.tool==='step'?`Draw ${state.regions.length?'region B':'two reference regions'} to measure their mean height difference.`:state.tool==='area'?'Drag a rectangle on the image. The selected area also becomes the correction reference.':'Choose Profile, then drag across the image to see a calibrated cross-section.'}</div>`;const p=state.profile,values=p.values,dist=p.distance_um;const valid=values.filter(v=>v!==null&&Number.isFinite(v));if(!valid.length)return `${profileControls()}<h3>Line profile</h3><div class="profile-placeholder">This line crosses only invalid or excluded pixels. Choose another profile.</div>`;let lo=Math.min(...valid),hi=Math.max(...valid);if(lo===hi){lo-=.5;hi+=.5;}const W=800,H=110,px=i=>48+(W-65)*dist[i]/(p.length_um||1),py=v=>12+(H-35)*(1-(v-lo)/(hi-lo));let path='';values.forEach((v,i)=>{if(v===null||!Number.isFinite(v))return;path+=`${i&&values[i-1]!==null?'L':'M'}${px(i).toFixed(2)},${py(v).toFixed(2)} `;});return `${profileControls()}<h3>Line profile <span>${num(p.length_um)} µm · ${values.length} samples · ${p.averaging_width_pixels||1} px width · ${esc(state.scan.value_unit)}</span></h3><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Line profile chart"><line x1="48" y1="${H-22}" x2="${W-15}" y2="${H-22}" stroke="#ccd0d4"/><line x1="48" y1="12" x2="${W-15}" y2="12" stroke="#d8dce0" stroke-dasharray="3 4"/><line x1="48" y1="50" x2="${W-15}" y2="50" stroke="#d8dce0" stroke-dasharray="3 4"/><path d="${path}" fill="none" stroke="#4e6a7e" stroke-width="1.8"/><g fill="#666d74" font-size="8" font-family="sans-serif"><text x="0" y="15">${num(hi)}</text><text x="0" y="${H-25}">${num(lo)}</text><text x="48" y="${H-3}">0</text><text x="${W-60}" y="${H-3}">${num(p.length_um)} µm</text></g></svg>`;}
function pointSVG(points){
  const ratio=state.scan.width_um/state.scan.height_um;
  return points.map((p,i)=>`<g transform="translate(${p[0]*1000} ${p[1]*1000}) scale(1 ${ratio})"><circle r="10" fill="#fff" stroke="#333" stroke-width="2"/><text x="${p[0]>.94?-35:15}" y="${p[1]>.9?-12:26}" fill="white" stroke="#222" stroke-width="1.2" paint-order="stroke" font-size="28">${i+1}</text></g>`).join('');
}
function restoreDrawing(){
  AFMMask.paint();const overlay=document.getElementById('draw-overlay');if(!overlay)return;
  let shapes=overlay.querySelector('#drawing-static');
  if(!shapes){shapes=document.createElementNS('http://www.w3.org/2000/svg','g');shapes.id='drawing-static';overlay.prepend(shapes);}
  shapes.innerHTML=state.regions.map((r,i)=>rectSVG(r,i?'B':'A',i?'#e5c785':'#d9edc1')).join('')+(state.area?.roi?rectSVG(state.area.roi,'Reference','#d9edc1'):'')+(state.profile?.selection?lineSVG(state.profile.selection.start,state.profile.selection.end):'')+contrastSVG()+pointSVG(state.tool==='level'?state.levelPoints:!state.raw?(state.scan.history?.at(-1)?.model?.points||[]).map(p=>p.point):[]);
  const active=AFMCanvas.activeTool(),draft=overlay.querySelector('#drawing-draft');
  if(!active)draft?.remove();else if(active==='contrast'&&draft)shapes.querySelector('.contrast-region')?.setAttribute('visibility','hidden');
}
function rectSVG(r,label,c){return `<rect x="${r.x0*1000}" y="${r.y0*1000}" width="${(r.x1-r.x0)*1000}" height="${(r.y1-r.y0)*1000}" fill="${c}" fill-opacity=".12" stroke="${c}" stroke-width="2.5" stroke-dasharray="8 5"/><text x="${r.x0*1000+8}" y="${r.y0*1000+28}" fill="${c}" stroke="#1d2328" stroke-width="3" paint-order="stroke" stroke-opacity=".7" font-size="23" font-family="sans-serif">${label}</text>`;}
function lineSVG(a,b){return `<line x1="${a[0]*1000}" y1="${a[1]*1000}" x2="${b[0]*1000}" y2="${b[1]*1000}" stroke="#ebf5d8" stroke-width="3"/><circle cx="${a[0]*1000}" cy="${a[1]*1000}" r="6" fill="#ebf5d8"/><circle cx="${b[0]*1000}" cy="${b[1]*1000}" r="6" fill="#ebf5d8"/>`;}
function asRect(a,b){return {x0:Math.min(a[0],b[0]),y0:Math.min(a[1],b[1]),x1:Math.max(a[0],b[0]),y1:Math.max(a[1],b[1])};}
function contrastSVG(){
  const r=state.contrastROI;if(!r)return '';
  const box=AFMCanvas.bounds();
  const w=8000/(box?.width||1000),h=8000/(box?.height||1000);
  const handles=state.tool==='contrast'?[[r.x0,r.y0],[r.x1,r.y0],[r.x0,r.y1],[r.x1,r.y1]].map(([x,y])=>`<rect class="contrast-handle" x="${x*1000-w/2}" y="${y*1000-h/2}" width="${w}" height="${h}"/>`).join(''):'';
  const label=`<g transform="translate(${r.x0*1000} ${r.y0*1000}) scale(${1000/(box?.width||1000)} ${1000/(box?.height||1000)})"><text x="6" y="16" fill="#fff" stroke="#222" stroke-width="2" paint-order="stroke" font-size="11" font-family="sans-serif">Contrast</text></g>`;
  return `<g class="contrast-region"><rect x="${r.x0*1000}" y="${r.y0*1000}" width="${(r.x1-r.x0)*1000}" height="${(r.y1-r.y0)*1000}" fill="none" stroke-dasharray="6 4"/>${label}${handles}</g>`;
}
function bindCanvas(){AFMCanvas.bind();}
function inspectPoint(p){
  const s=state.scan,w=s.data_width||s.width,h=s.data_height||s.height;
  const xx=Math.min(w-1,Math.floor(p[0]*w)),yy=Math.min(h-1,Math.floor(p[1]*h));
  const v=Array.isArray(s.data?.[0])?s.data[yy]?.[xx]:s.data?.[yy*w+xx];
  const cursor=document.getElementById('cursor-value'),text=`x ${num(p[0]*s.width_um)} µm · y ${num(p[1]*s.height_um)} µm · ${num(v)} ${s.value_unit}`;if(cursor&&cursor.textContent!==text)cursor.textContent=text;
}
function draftDrawing(tool,start,end){
  const overlay=document.getElementById('draw-overlay');if(!overlay)return;
  let draft=overlay.querySelector('#drawing-draft');
  if(!draft){draft=document.createElementNS('http://www.w3.org/2000/svg','g');draft.id='drawing-draft';overlay.append(draft);}
  if(tool==='mask'){AFMMask.paintPreview(draft);return;}
  const shape=tool==='profile'?'profile':'rectangle';
  if(draft.dataset.shape!==shape){draft.innerHTML=shape==='profile'?lineSVG(start,end):rectSVG(asRect(start,end),'','#e5f1d2');draft.dataset.shape=shape;}
  const attr=(node,values)=>{for(const [name,value] of Object.entries(values))if(node.getAttribute(name)!==String(value))node.setAttribute(name,value);};
  if(shape==='profile'){
    attr(draft.querySelector('line'),{x1:start[0]*1000,y1:start[1]*1000,x2:end[0]*1000,y2:end[1]*1000});
    const circles=draft.querySelectorAll('circle');attr(circles[0],{cx:start[0]*1000,cy:start[1]*1000});attr(circles[1],{cx:end[0]*1000,cy:end[1]*1000});
  }else{
    const r=asRect(start,end);attr(draft.querySelector('rect'),{x:r.x0*1000,y:r.y0*1000,width:(r.x1-r.x0)*1000,height:(r.y1-r.y0)*1000});
    const text=draft.querySelector('text'),label=tool==='contrast'?'Contrast':tool==='step'?(state.regions.length===1?'B':'A'):'Reference';
    attr(text,{x:r.x0*1000+8,y:r.y0*1000+28});if(text.textContent!==label)text.textContent=label;
    if(tool==='contrast')document.querySelector('.contrast-region')?.setAttribute('visibility','hidden');
  }
}
async function completeDrawing(tool,start,end){
  if(tool==='contrast'){
    const previous=state.contrastROI,selection=asRect(start,end);
    state.contrastROI=selection;restoreDrawing();AFMDisplay.refresh();
    const applied=await AFMDisplay.roi(selection);
    if(!applied&&state.contrastROI===selection)state.contrastROI=previous;
    restoreDrawing();AFMDisplay.refresh();return;
  }
  try{
    if(tool==='mask'){await AFMMask.finish(end);restoreDrawing();return;}
    setBusy('Measuring full-resolution data…');
    if(tool==='profile')await measureProfile(start,end);
    else if(tool==='area'){
      const roi=asRect(start,end);state.area=await api('measure_area',{id:state.scan.id,roi,...AFMMask.parameters()});
      if(!state.area.statistics)state.area={statistics:state.area,roi};else state.area.roi=roi;
    }else if(tool==='step'){
      state.step=null;if(state.regions.length===2)state.regions=[];state.regions.push(asRect(start,end));
      if(state.regions.length===2)state.step=await api('step_height',{id:state.scan.id,region_a:state.regions[0],region_b:state.regions[1],...AFMMask.parameters()});
    }
    renderContent();
  }catch(error){toast(error.message,true);restoreDrawing();}finally{if(tool!=='mask')setBusy(null);}
}
function renderCompare(main){const scans=state.comparison||[];const sameUnit=scans.every(s=>s.value_unit===scans[0]?.value_unit);main.innerHTML=`<div class="compare-view"><div class="compare-header"><button class="detail-back" data-action="back">${icon('back')}</button><div><p class="eyebrow">SIDE BY SIDE</p><h2>Compare images</h2></div><button class="button ${state.commonRange?'active':''}" data-action="common-range" ${!sameUnit?'disabled':''}>${icon('settings')}${state.commonRange?'Shared display range':'Independent display ranges'}</button></div><div class="compare-grid">${scans.map(s=>`<section class="compare-panel"><canvas class="compare-image" style="aspect-ratio:${s.width_um/s.height_um}" data-compare-canvas="${esc(s.id)}" aria-label="${esc(s.channel)} ${esc(s.direction)} comparison"></canvas><h3>${esc(s.channel)} <span style="color:#767b80;font-weight:400">· Scan ${esc(s.acquisition)}</span></h3><p>${esc(s.direction)} · ${num(s.width_um)} × ${num(s.height_um)} µm · ${s.operations.length?'Processed':'Original'} · ${AFMMask.active(s)?'Mask applied to statistics':'Whole-image statistics'}</p><div class="metrics-grid">${metric('Sq',(AFMMask.active(s)?s.masked_statistics:s.statistics)?.sq,s.value_unit)}${metric('Sa',(AFMMask.active(s)?s.masked_statistics:s.statistics)?.sa,s.value_unit)}${metric('Peak to valley',(AFMMask.active(s)?s.masked_statistics:s.statistics)?.peak_to_valley,s.value_unit)}</div><button class="button small" data-action="open" data-id="${esc(s.id)}" style="margin-top:12px">Open image ${icon('arrow')}</button></section>`).join('')}</div><div class="compare-notice">${icon('info')}${sameUnit?'Shared display range uses the same numeric color limits; measurements are unaffected.':'Different physical units: each image uses its own display range.'} Images are displayed in their stored orientation.</div></div>`;requestAnimationFrame(()=>{const ranges=scans.map(s=>s.comparison_range);const common=[Math.min(...ranges.map(x=>x[0])),Math.max(...ranges.map(x=>x[1]))];scans.forEach((s,j)=>{const canvas=document.querySelector(`[data-compare-canvas="${CSS.escape(s.id)}"]`);if(!canvas)return;const [lo,hi]=state.commonRange?common:ranges[j];paintPixels(canvas,s,lo,hi,state.commonRange?state.palette:s.display?.palette);});});}
function showModal(title,content,actions=''){const root=document.getElementById('modal-root');root.innerHTML=`<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-header"><h2>${esc(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></div>${content}<div class="form-error" id="form-error" role="alert"></div>${actions?`<div class="modal-actions">${actions}</div>`:''}</section></div>`;setTimeout(()=>root.querySelector('input,textarea,button')?.focus(),50);}
function closeModal(){document.getElementById('modal-root').innerHTML='';}
async function importDialog(){if(window.pywebview?.api?.choose_folder){const path=await window.pywebview.api.choose_folder();if(path)await importFolder(path);return;}showModal('Import an AFM session',`<p>Choose the folder containing your session. All supported TIFF images in that folder will stay together.</p><label>Folder path<input id="folder-path" placeholder="/path/to/session or C:\\Data\\Session" autocomplete="off"></label><div class="modal-note">${icon('shield')}<span>Original files are copied into your local workspace and preserved. Importing the same folder again adds only new files.</span></div>`,`<button class="button" data-action="close-modal">Cancel</button><button class="button primary" data-action="import-confirm">${icon('folder')}Import session</button>`);setTimeout(()=>document.getElementById('folder-path')?.focus(),60);}
let importPollTimer=null;
function renderImportProgress(){
  document.getElementById('import-progress')?.remove();
  const job=state.importJob;if(!job)return;
  const running=job.status==='running',el=document.createElement('section');el.id='import-progress';el.className='import-progress';el.setAttribute('aria-label','Folder import');
  const label=running?(job.cancelling?'Stopping after current file…':job.total?`Checking ${job.completed} / ${job.total} files`:'Reading folder…'):job.status==='failed'?'Import failed':job.status==='cancelled'?'Import stopped':'Import complete';
  el.innerHTML=`<div><strong role="status">${esc(label)}</strong><small title="${esc(job.filename||job.path)}">${esc(job.filename||job.path)}</small><span>${job.added} added · ${job.skipped} unchanged · ${job.errors.length} failed</span>${job.message?`<p class="warning">${esc(job.message)}</p>`:''}${running?`<progress max="${job.total||1}" value="${job.completed}"></progress>`:''}${job.cancelling?'<small>Completed files are kept. You can continue browsing.</small>':''}</div><div class="import-actions">${running?`<button class="button small" data-action="cancel-import" ${job.cancelling?'disabled':''}>Cancel import</button>`:`${job.session_id?`<button class="button small" data-action="import-open" data-id="${esc(job.session_id)}">Open session</button>`:''}${job.errors.length?'<button class="button small" data-action="import-errors">View errors</button>':''}<button class="icon-button" data-action="dismiss-import" aria-label="Dismiss import status">${icon('close')}</button>`}</div>`;
  document.body.append(el);
}
async function pollImport(){
  clearTimeout(importPollTimer);
  try{
    state.importJob=await api('import_status');renderImportProgress();
    if(state.importJob?.status==='running'){importPollTimer=setTimeout(pollImport,500);return;}
    state.sessions=(await api('bootstrap')).sessions;
    if(state.view==='folders'){state.folders=await api('list_folders');renderShell();}
    else if(state.view==='library')renderShell();
    else if(state.view==='session'&&state.session?.id===state.importJob?.session_id){await refreshSession();renderShell();}
  }catch(error){toast(`Import status unavailable: ${error.message}. Retrying…`,true);importPollTimer=setTimeout(pollImport,2000);}
}
async function importFolder(path,sessionId=null){
  if(!path.trim())throw new Error('Enter the path to an AFM session folder.');
  state.importJob=await api('start_import',{path:path.trim(),session_id:sessionId});
  closeModal();renderImportProgress();pollImport();
}
// Keep the drop target outside the rerendered app shell. Only native pywebview
// drop events supply a local path; never infer it from a filename or a URI.
let folderDragDepth=0;
const fileDrag=event=>Array.from(event.dataTransfer?.types||[]).includes('Files');
function clearFolderDrop(){folderDragDepth=0;document.getElementById('folder-drop').hidden=true;}
document.addEventListener('dragenter',event=>{if(!fileDrag(event))return;event.preventDefault();folderDragDepth++;document.getElementById('folder-drop').hidden=false;});
document.addEventListener('dragover',event=>{if(!fileDrag(event))return;event.preventDefault();event.dataTransfer.dropEffect='copy';});
document.addEventListener('dragleave',event=>{if(!fileDrag(event)&&!folderDragDepth)return;if(--folderDragDepth<=0||!event.relatedTarget)clearFolderDrop();});
document.addEventListener('drop',event=>{
  clearFolderDrop();if(!fileDrag(event))return;event.preventDefault();
  if(!window.afmFolderDropReady)toast(window.pywebview?'Folder drop is not ready. Use Import folder to choose it.':'Folder drag-and-drop requires the desktop app. Use Import folder to enter its path.',true);
});
document.addEventListener('dragend',clearFolderDrop);
window.addEventListener('blur',clearFolderDrop);
window.afmImportDrop=async result=>{
  clearFolderDrop();
  try{if(result.error)throw new Error(result.error);await importFolder(result.path);}
  catch(error){toast(error.message,true);}
};
async function folderLibrary(){state.folders=await api('list_folders');state.view='folders';state.query='';state.selected.clear();renderShell();}
function renderFolders(main){
  const folders=state.folders.filter(s=>(state.folderFilter==='archived'?s.archived:!s.archived)&&(!state.query||[s.name,s.notes,s.source_path].join(' ').toLowerCase().includes(state.query.toLowerCase())));
  main.innerHTML=`<div class="session-heading"><h1>Folders</h1></div><p class="folder-help">One source folder is one session. Update to add new or changed files. Archived sessions keep their images and analysis.</p><div class="view-tabs"><button class="view-tab ${state.folderFilter==='active'?'active':''}" data-action="folder-filter" data-value="active">Active</button><button class="view-tab ${state.folderFilter==='archived'?'active':''}" data-action="folder-filter" data-value="archived">Archived</button></div><div class="folder-list">${folders.map(s=>`<article class="folder-row" data-folder-id="${esc(s.id)}"><div class="folder-info"><button class="folder-title" data-action="session" data-id="${esc(s.id)}">${icon('folder')}${esc(s.name)}</button><p title="${esc(s.source_path)}">${s.synthetic?'Synthetic example':esc(s.source_path)}</p><small>${s.scan_count} images · ${date(s.imported_at)}${s.import_errors.length?` · ${s.import_errors.length} import errors`:''}</small></div><div class="folder-actions">${!s.synthetic&&!s.archived?`<button class="button small" data-action="update-folder" data-id="${esc(s.id)}">${icon('reset')}Update</button>`:''}<button class="button small" data-action="manage-folder" data-id="${esc(s.id)}">Manage</button>${s.archived?`<button class="button small" data-action="restore-folder" data-id="${esc(s.id)}">Restore</button>`:''}</div></article>`).join('')||'<div class="empty-state"><p>No matching folders.</p></div>'}</div>`;
}
async function manageFolder(id){
  const folders=await api('list_folders'),s=folders.find(s=>s.id===id);if(!s)throw new Error('Session not found.');state.folderSession=s;
  showModal('Manage folder',`<label>Session name<input id="managed-name" maxlength="300" value="${esc(s.name)}"></label><label>Notes<textarea id="managed-notes">${esc(s.notes)}</textarea></label><div class="folder-source"><strong>Source folder</strong><p>${esc(s.source_path)}</p>${s.source_history.length?`<details><summary>Previous source locations</summary>${s.source_history.map(h=>`<p>${esc(h.path)}</p>`).join('')}</details>`:''}</div>${!s.synthetic?`<p>Reconnect if this folder moved. Updates preserve previous image versions and saved analysis.</p><div class="folder-actions"><button class="button" data-action="update-managed-folder">Update folder</button><button class="button" data-action="reconnect-folder">Reconnect…</button></div>`:''}<p>Archive hides this session from browsing. Its images, notes and analysis stay in the catalog and can be restored.</p>`,`<button class="button" data-action="archive-folder">${s.archived?'Restore session':'Archive session'}</button><button class="button primary" data-action="save-folder">Save changes</button>`);
}
function reconnectDialog(){
  const s=state.folderSession;
  showModal('Reconnect source folder',`<p>Choose the new location of <b>${esc(s.name)}</b>. Its images will join this existing session. Previous source locations remain recorded.</p><label>Folder path<input id="reconnect-path" value="${esc(s.source_path)}"></label>${window.pywebview?.api?.choose_folder?'<button class="button" data-action="browse-reconnect">Choose folder…</button>':''}`,`<button class="button" data-action="close-modal">Cancel</button><button class="button primary" data-action="reconnect-confirm">Reconnect and update</button>`);
}
async function refreshFolders(){
  state.sessions=(await api('bootstrap')).sessions;state.folders=await api('list_folders');
  if(state.session){const s=state.folders.find(s=>s.id===state.session.id);if(s?.archived){state.session=null;state.scan=null;state.view='folders';}else await refreshSession();}
  renderShell();
}
function notesDialog(){showModal('Session notes',`<label>Session name<input id="session-name" value="${esc(state.session.name)}" maxlength="160"></label><label>Notes<textarea id="session-notes" placeholder="Sample, preparation, questions to revisit…">${esc(state.session.notes||'')}</textarea></label><div class="modal-note">${icon('note')}Notes stay with this session. You can browse and analyze without assigning a sample.</div>`,`<button class="button" data-action="close-modal">Cancel</button><button class="button primary" data-action="save-notes">Save notes</button>`);}
function exportDialog(){showModal('Export this image',`<p>Export ${esc(state.scan.channel)} from scan ${esc(state.scan.acquisition)}. Data exports use the full-resolution, saved analysis.</p><button class="operation-button" data-action="export-format" data-format="csv">Calibrated data · CSV ${icon('download')}</button><button class="operation-button" data-action="export-format" data-format="json">Provenance & recipe · JSON ${icon('download')}</button><button class="operation-button" data-action="export-format" data-format="png">Current view · PNG figure ${icon('download')}</button><div class="modal-note">${icon('info')}For reproducibility, save the provenance manifest alongside your data or figure. Figures include the displayed range and processing state.</div>`);}
async function download(filename,content,mime,base64=false){if(window.pywebview?.api?.save_export){const result=await window.pywebview.api.save_export(filename,content,base64);if(result?.error)throw new Error(result.error);if(result?.path)toast('Export saved.');return;}const blob=base64?new Blob([Uint8Array.from(atob(content),x=>x.charCodeAt(0))],{type:mime}):new Blob([content],{type:mime});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Export downloaded.');}
async function exportFigure(){await AFMDisplay.pending();const source=document.getElementById('height-canvas'),s=state.scan,canvas=document.createElement('canvas');canvas.width=1100;canvas.height=1240;const ctx=canvas.getContext('2d');ctx.fillStyle='#f2f3f4';ctx.fillRect(0,0,1100,1240);ctx.fillStyle='#282d32';ctx.font='28px sans-serif';ctx.fillText(`${s.channel} · Scan ${s.acquisition} · ${s.direction}`,60,55);const ratio=s.width_um/s.height_um,w=ratio>=1?940:940*ratio,h=ratio>=1?940/ratio:940;ctx.drawImage(source,80+(940-w)/2,95,w,h);const maskCanvas=document.getElementById('mask-canvas'),maskShown=!state.inspectorHidden&&s.mask?.visible!==false;if(maskShown&&s.mask?.count&&maskCanvas)ctx.drawImage(maskCanvas,80+(940-w)/2,95,w,h);ctx.strokeStyle='#fff';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(80+(940-w)/2+w*.68,95+h-40);ctx.lineTo(80+(940-w)/2+w*.93,95+h-40);ctx.stroke();ctx.fillStyle='#fff';ctx.font='20px sans-serif';ctx.fillText(`${num(s.width_um/4)} µm`,80+(940-w)/2+w*.72,95+h-53);ctx.fillStyle='#626970';ctx.font='19px sans-serif';ctx.fillText(`${num(s.width_um)} × ${num(s.height_um)} µm · ${s.width} × ${s.height} pixels`,60,1100);ctx.fillText(`Display: ${AFMDisplay.describe()}`,60,1135);ctx.fillText(`${state.raw?'Original':state.pending?'Unsaved preview':s.operations.length+' saved correction(s)'} · Mask: ${s.mask?.count||0} pixels, ${maskShown?'shown':'hidden'} · AFM Workbench`,60,1170);ctx.font='14px sans-serif';ctx.fillText(s.filename.slice(0,110),60,1205);await download(`${s.acquisition}-${s.channel.replace(/[^a-z0-9]/gi,'-')}.png`,canvas.toDataURL('image/png').split(',')[1],'image/png',true);}
async function runOperation(type){await AFMDisplay.pending();state.processingError=null;const op={type};
  if(['align_scan','auto_2d','auto_characterize'].includes(type))op.axis=state.processingAxis;
  if(['align_scan','align_rows','align_columns'].includes(type)){op.method=state.lineMethod;if(op.method==='polynomial')op.degree=state.lineDegree;if(op.method.startsWith('trimmed'))op.trim_fraction=state.lineTrim/100;}
  if(['plane','zero_mean','zero_min','zero_max'].includes(type))op.method='gwyddion';
  if(type==='polynomial'){op.mode=state.polynomialMode;if(op.mode==='total')op.degree=state.polynomialDegree;else {op.degree_x=state.polynomialDegreeX;op.degree_y=state.polynomialDegreeY;}}
  if(['auto_2d','auto_characterize'].includes(type))op.line_correction=state.autoLineCorrection;
  if(type==='three_point'){op.points=state.levelPoints.map(p=>[...p]);op.radius=2;}
  Object.assign(op,AFMMask.parameters());if(state.area?.roi){op.roi=state.area.roi;if(!AFMMask.active())op.masking=state.referenceMode;}const operations=[...state.scan.operations,op],previous=structuredClone(state.scan.operations||[]);setBusy('Applying correction…');try{state.scan=await api('process',{id:state.scan.id,operations});state.revision++;state.raw=false;state.profile=null;state.step=null;state.area=null;state.regions=[];if(['auto_characterize','three_point'].includes(type)){AFMDisplay.beginPreview();await AFMDisplay.outline();await AFMDisplay.endPreview(true);state.tool='contrast';}else await AFMDisplay.load(state.scan);syncScanSummary(state.scan);renderContent();state.undoStack.push(previous);toast(`${opName(op)} applied.`,false,{label:'Undo',action:'undo'});}catch(error){if(['terrace_plane','auto_2d','auto_characterize','three_point'].includes(type)){state.processingError=error.message;renderContent();}throw error;}finally{setBusy(null);}}
async function rawMode(raw){if(raw===state.raw)return;await AFMDisplay.pending();setBusy('Loading image…');try{const payload={id:state.scan.id};state.scan=await api(raw?'scan':state.pending?'preview':'scan',raw?{...payload,raw:true}:state.pending?{...payload,operations:state.pending}:payload);state.raw=raw;state.profile=null;state.area=null;state.regions=[];state.step=null;await AFMDisplay.load(state.scan);renderContent();}finally{setBusy(null);}}
async function star(id){const item=state.session?.scans.find(s=>s.id===id)||state.starredSessions?.flatMap(s=>s.scans).find(s=>s.id===id)||state.scan;const updated=await api('update_scan',{id,starred:!item.starred});if(state.session){const index=state.session.scans.findIndex(s=>s.id===id);if(index>=0)state.session.scans[index]={...state.session.scans[index],starred:updated.starred};}if(state.scan?.id===id)state.scan.starred=updated.starred;for(const session of state.starredSessions||[]){const match=session.scans.find(s=>s.id===id);if(match)match.starred=updated.starred;}state.sessions=(await api('bootstrap')).sessions;if(state.view==='detail'){document.querySelectorAll(`[data-action="star"][data-id="${CSS.escape(id)}"]`).forEach(b=>b.classList.toggle('active',updated.starred));}else renderContent();toast(updated.starred?'Added to starred images.':'Removed from starred images.');}
const actions={
'folders':folderLibrary,
'folder-filter':el=>{state.folderFilter=el.dataset.value;renderContent();},
'manage-folder':el=>manageFolder(el.dataset.id),
'update-folder':el=>{const s=state.folders.find(s=>s.id===el.dataset.id);return importFolder(s.source_path,s.id);},
'update-managed-folder':()=>importFolder(state.folderSession.source_path,state.folderSession.id),
'reconnect-folder':reconnectDialog,
'browse-reconnect':async()=>{const path=await window.pywebview.api.choose_folder();if(path)document.getElementById('reconnect-path').value=path;},
'reconnect-confirm':()=>importFolder(document.getElementById('reconnect-path').value,state.folderSession.id),
'save-folder':async()=>{await api('update_session',{id:state.folderSession.id,name:document.getElementById('managed-name').value,notes:document.getElementById('managed-notes').value});closeModal();await refreshFolders();toast('Folder details saved.');},
'archive-folder':async()=>{await api('update_session',{id:state.folderSession.id,archived:!state.folderSession.archived});closeModal();await refreshFolders();toast(state.folderSession.archived?'Session restored.':'Session archived. Restore it from Folders → Archived.');},
'restore-folder':async el=>{await api('update_session',{id:el.dataset.id,archived:false});await refreshFolders();toast('Session restored.');},
'cancel-import':async()=>{state.importJob=await api('cancel_import');renderImportProgress();},
'dismiss-import':()=>{state.importJob=null;renderImportProgress();},
'import-open':async el=>{closeModal();await openSession(el.dataset.id);},
'import-errors':()=>showModal('Import errors',state.importJob.errors.map(e=>`<div class="warning"><b>${esc(e.filename)}</b><br>${esc(e.error)}</div>`).join('')),
'import':importDialog,'import-confirm':()=>importFolder(document.getElementById('folder-path').value),
'demo':async()=>{setBusy('Creating synthetic session…');try{const s=await api('demo');state.sessions=(await api('bootstrap')).sessions;state.session=s;state.view='session';state.tab='grid';renderShell();toast('Synthetic session opened.');}finally{setBusy(null);}},
'library':()=>{state.view='library';state.query='';state.starred=false;state.pending=null;renderShell();},
'session':el=>openSession(el.dataset.id),'open':el=>openScan(el.dataset.id),
'back':async()=>{await AFMDisplay.endPreview(false);state.pending=null;state.view='session';await refreshSession();renderShell();},
'session-details':sessionDetails,'notes':notesDialog,'save-notes':async()=>{const name=document.getElementById('session-name').value.trim();if(!name)throw new Error('Give this session a name.');state.session=await api('update_session',{id:state.session.id,name,notes:document.getElementById('session-notes').value});state.sessions=(await api('bootstrap')).sessions;closeModal();renderShell();toast('Session notes saved.');},
'close-modal':closeModal,
'star':el=>star(el.dataset.id),
'starred':async()=>{setBusy('Opening starred images…');try{state.starredSessions=await Promise.all(state.sessions.map(s=>api('session',{id:s.id})));state.view='starred';state.query='';state.pending=null;state.selected.clear();renderShell();}finally{setBusy(null);}},
'starred-filter':()=>{state.starred=!state.starred;renderContent();},
'clear-filters':()=>{state.query='';state.channel='overview';state.direction='all';state.acquisition='all';state.starred=false;renderShell();},
'density':el=>{state.compact=el.dataset.value==='compact';renderContent();},
'browse-level':()=>{state.browseLevel=!state.browseLevel;try{localStorage.setItem('afm-browse-level',String(state.browseLevel));}catch{}renderContent();},
'tab':el=>{state.tab=el.dataset.tab;renderContent();},
'clear-selection':()=>{state.selected.clear();renderContent();},
'compare':async()=>{setBusy('Preparing comparison…');try{state.comparison=await Promise.all([...state.selected].map(async id=>{const s=await api('scan',{id}),d=s.display||{};if(d.mode==='manual')s.comparison_range=[d.minimum,d.maximum];else{const r=await api('display_range',{id,mode:d.mode||'full',clip_percent:d.clip_percent||0});s.comparison_range=[r.minimum,r.maximum];}return s;}));state.commonRange=false;state.view='compare';renderShell();}finally{setBusy(null);}},
'common-range':()=>{state.commonRange=!state.commonRange;renderContent();},
'map-mode':el=>{if(!['all','focus','outlines'].includes(el.dataset.value))return;state.mapMode=el.dataset.value;if(state.mapMode!=='focus')state.mapSelected=null;renderContent();document.querySelector(`[data-action="map-mode"][data-value="${state.mapMode}"]`)?.focus();},
'map-select':el=>selectMapGroup(Number(el.dataset.key)),
'map-pick':pickMapLocation,
'map-zoom':el=>{state.mapZoom=el.dataset.value==='fit'?1:Math.min(8,Math.max(.25,state.mapZoom*(el.dataset.value==='in'?1.4:1/1.4)));renderContent();},
'map-location':el=>{const g=mapGroups(filtered(state.session.scans))[Number(el.dataset.key)];if(!g)return;showModal(`Scan ${g.scans[0].acquisition}`,`<p>${g.placed?`${num(g.w)} × ${num(g.h)} µm at x ${num(g.x)}, y ${num(g.y)} µm`:`Not placed on map`} · ${g.scans.length} images.</p>${g.scans.map(s=>`<button class="map-location" data-action="open-map-image" data-id="${esc(s.id)}"><img src="${thumb(s)}" alt=""><span><strong>${esc(s.channel)}</strong><small>${esc(s.direction)} · ${s.width} × ${s.height} px</small></span>${icon('chevron')}</button>`).join('')}`);},
'open-map-image':el=>{closeModal();return openScan(el.dataset.id);},
'review':async()=>{const updated=await api('update_scan',{id:state.scan.id,review_status:state.scan.review_status==='reviewed'?'unreviewed':'reviewed'});state.scan.review_status=updated.review_status;await refreshSession();renderContent();toast(state.scan.review_status==='reviewed'?'Marked as reviewed.':'Marked as unreviewed.');},
'inspect-plane':inspectPlane,
'operation':el=>runOperation(el.dataset.operation),
'line-choice':el=>applyLine(el.dataset.choice),
'line-dir':el=>{state.lineDir=el.dataset.dir;const ls=lineState();if(ls.kind==='method'&&ls.method!=='legacy')return applyLine(ls.method);renderContent();},
'undo':async()=>{await AFMDisplay.pending();setBusy('Replaying previous recipe…');try{state.processingError=null;state.scan=await api('process',{id:state.scan.id,operations:state.undoStack.length?state.undoStack.pop():state.scan.operations.slice(0,-1)});state.revision++;state.raw=false;state.profile=null;state.area=null;state.regions=[];state.step=null;syncScanSummary(state.scan);await AFMDisplay.load(state.scan);renderContent();toast('Last correction undone.');}finally{setBusy(null);}},
'raw':el=>rawMode(el.dataset.value==='raw'),
'clear-area':()=>{state.area=null;renderContent();},
'toggle-inspector':()=>setInspectorHidden(!state.inspectorHidden),
'inspector-tab':el=>showInspector(el.dataset.tab,true),
'export':exportDialog,
'export-format':async el=>{await AFMDisplay.pending();if(el.dataset.format==='png'){await exportFigure();}else{const result=await api('export_scan',{id:state.scan.id,format:el.dataset.format,display:{...AFMDisplay.settings(),range:canvasRanges,raw:state.raw,preview:!!state.pending}});await download(result.filename,result.content,result.mime);}closeModal();},
'export-session':async()=>{const result=await api('export_session',{id:state.session.id});await download(result.filename,result.content,result.mime);},
'help':()=>showModal('Help & shortcuts',`<p>The contact sheet shows one forward Z height per acquisition, with signals from the same direction and position. Use All channels for other channels and backward scans. <b>Leveled thumbnails</b> applies display-only scan-line and plane leveling to unprocessed height images; turn it off to see the stored data.</p><p>Select up to four images to compare. Open an image for profiles, area measurements and corrections. Corrections are saved when you apply them and can be undone (⌘/Ctrl Z or Record); the original data is never changed, and display contrast does not change data. New height images are automatically aligned and three-point leveled when opened; turn this off at the bottom of Prepare. If reference selection fails, choose three clean points on the same plane. Press C and drag a rectangle for local contrast.</p><table class="keyboard-table"><tr><td>Search</td><td><kbd>⌘ / Ctrl K</kbd></td></tr><tr><td>Back to session / close dialog</td><td><kbd>Esc</kbd></td></tr><tr><td>Next / previous image</td><td><kbd>→ / ←</kbd></td></tr><tr><td>Star current image</td><td><kbd>S</kbd></td></tr><tr><td>Switch forward / backward scan</td><td><kbd>B</kbd></td></tr><tr><td>Undo last correction</td><td><kbd>⌘ / Ctrl Z</kbd></td></tr><tr><td>View / Prepare / Measure / Record</td><td><kbd>1 / 2 / 3 / 4</kbd></td></tr><tr><td>Inspect / Pan / Profile / Area / Mask / Step</td><td><kbd>V / H / P / A / M / T</kbd></td></tr><tr><td>Zoom / Fit</td><td><kbd>Scroll or + / − / F</kbd></td></tr><tr><td>Temporarily pan</td><td><kbd>Space + drag or middle drag</kbd></td></tr><tr><td>Draw contrast rectangle</td><td><kbd>C</kbd></td></tr><tr><td>Leave drawing tool</td><td><kbd>Esc</kbd></td></tr></table>`),
 'tool':el=>selectTool(el.dataset.tool,el.dataset.panel)
};
document.addEventListener('click',async e=>{const el=e.target.closest('[data-action]');if(!el||el.disabled)return;const fn=actions[el.dataset.action];if(!fn||state.loading)return;try{await fn(el,e);}catch(error){const field=document.getElementById('form-error');if(field)field.textContent=error.message;else toast(error.message,true);setBusy(null);}});
document.addEventListener('change',async e=>{try{if(e.target.matches('[data-select]')){const id=e.target.dataset.select;if(e.target.checked){if(state.selected.size>=4){e.target.checked=false;toast('Compare up to four images at a time.');return;}state.selected.add(id);}else state.selected.delete(id);e.target.closest('.scan-card').classList.toggle('selected',e.target.checked);renderTray();return;}const id=e.target.id;if(id==='auto-prepare-on-open'){state.autoPrepare=e.target.checked;try{localStorage.setItem('afm-auto-prepare',String(state.autoPrepare));}catch{}return;}if(id==='auto-line-correction'){state.autoLineCorrection=e.target.checked;return;}else if(id==='processing-axis'){state.processingAxis=e.target.value;return;}
else if(id==='line-method'){state.lineMethod=e.target.value;renderContent();return;}
else if(id==='polynomial-mode'){state.polynomialMode=e.target.value;renderContent();return;}
else if(id==='reference-mode'){state.referenceMode=e.target.value;renderContent();document.getElementById('reference-mode')?.focus();return;}
else if(['line-degree','line-trim','polynomial-degree','polynomial-degree-x','polynomial-degree-y','profile-width'].includes(id)){
  const limits={'line-degree':['lineDegree',0,5],'line-trim':['lineTrim',0,50],'polynomial-degree':['polynomialDegree',0,11],'polynomial-degree-x':['polynomialDegreeX',0,11],'polynomial-degree-y':['polynomialDegreeY',0,11],'profile-width':['profileWidth',1,128]};
  const [key,minimum,maximum]=limits[id],value=Number(e.target.value);
  if(e.target.value===''||!Number.isInteger(value)||value<minimum||value>maximum){e.target.value=state[key];throw new Error(`Enter a whole number from ${minimum} to ${maximum}.`);}
  state[key]=value;
  if(['line-degree','line-trim'].includes(id)){const ls=lineState();if(ls.kind==='method'&&(id==='line-degree'?ls.method==='polynomial':ls.method.startsWith('trimmed')))await applyLine(ls.method);return;}
  if(id==='profile-width'&&state.profile?.selection){setBusy('Updating profile…');try{await measureProfile(state.profile.selection.start,state.profile.selection.end);renderContent();}finally{setBusy(null);}}
  return;
}else if(id==='profile-interpolation'){state.profileInterpolation=e.target.value;if(state.profile?.selection){setBusy('Updating profile…');try{await measureProfile(state.profile.selection.start,state.profile.selection.end);renderContent();}finally{setBusy(null);}}return;}
else if(id==='channel-filter')state.channel=e.target.value;else if(id==='direction-filter')state.direction=e.target.value;else if(id==='acquisition-filter')state.acquisition=e.target.value;else if(id==='related-scan'){await openScan(e.target.value);return;}else return;renderContent();}catch(error){toast(error.message,true);}});
document.addEventListener('input',e=>{if(e.target.id==='map-opacity'){state.mapOpacity=Math.min(100,Math.max(10,Number(e.target.value)||75));document.querySelectorAll('.map-image').forEach(image=>image.setAttribute('opacity',state.mapOpacity/100));document.querySelector('.map-opacity output').textContent=`${state.mapOpacity}%`;try{localStorage.setItem('afm-map-opacity',String(state.mapOpacity));}catch{}return;}if(e.target.id==='global-search'){clearTimeout(searchTimer);state.query=e.target.value;searchTimer=setTimeout(()=>{if(['library','session','starred','folders'].includes(state.view))renderContent();},150);}});
document.addEventListener('keydown',e=>{
  if(state.loading)return;
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();document.getElementById('global-search')?.focus();return;}
  if(e.key==='Escape'){
    if(document.querySelector('.modal'))closeModal();
    else if(state.view==='session'&&state.tab==='map'&&state.mapSelected){clearMapFocus();document.querySelector('[data-action="map-mode"][data-value="all"]')?.focus();}
    else if(state.view==='detail'&&AFMCanvas.cancel()){e.preventDefault();return;}
    else if(state.view==='detail'&&state.tool!=='inspect'){selectTool('inspect');document.getElementById('height-canvas')?.focus();}
    else if(['detail','compare'].includes(state.view))actions.back().catch(error=>toast(error.message,true));
    return;
  }
  if(e.target.closest('input,textarea,select,[contenteditable="true"]')){
    if(e.key==='Enter'&&e.target.id==='folder-path')actions['import-confirm']().catch(error=>document.getElementById('form-error').textContent=error.message);
    return;
  }
  if(state.view==='detail'&&!document.querySelector('.modal')&&(e.metaKey||e.ctrlKey)&&!e.shiftKey&&e.key.toLowerCase()==='z'){e.preventDefault();if(state.scan?.operations?.length&&!state.raw)actions.undo().catch(error=>toast(error.message,true));else toast(state.raw?'Switch to Result to undo corrections.':'No saved correction to undo.');return;}
  if(document.querySelector('.modal')||e.metaKey||e.ctrlKey||e.altKey)return;
  if(e.target.matches('[role="tab"]')&&['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){
    e.preventDefault();const ids=inspectorTabs.map(([id])=>id),index=ids.indexOf(state.inspectorTab);
    showInspector(e.key==='Home'?ids[0]:e.key==='End'?ids.at(-1):ids[(index+(e.key==='ArrowRight'?1:-1)+ids.length)%ids.length],true);return;
  }
  if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-action][role="button"]')){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
  if(state.view!=='detail')return;
  const key=e.key.toLowerCase(),tool={v:'inspect',h:'pan',c:'contrast',p:'profile',a:'area',m:'mask',t:'step'}[key];
  if(tool){e.preventDefault();selectTool(tool);return;}
  if(['1','2','3','4'].includes(key)){e.preventDefault();showInspector(key==='c'?'view':inspectorTabs[Number(key)-1][0],true);return;}
  if(key==='s')star(state.scan.id).catch(error=>toast(error.message,true));
  if(key==='b'){const other=counterpart(state.scan,state.session.scans.filter(x=>acquisitionKey(x)===acquisitionKey(state.scan)));if(other){e.preventDefault();openScan(other.id).catch(error=>toast(error.message,true));}return;}
  if(['ArrowRight','ArrowLeft'].includes(e.key)&&!e.target.closest('button,[role="button"]')){
    const scans=heightOverview()?sorted(state.session.scans.filter(s=>s.channel===state.scan.channel&&s.direction===state.scan.direction)):filtered(state.session.scans),i=scans.findIndex(s=>s.id===state.scan.id),next=scans[i+(e.key==='ArrowRight'?1:-1)];
    if(next)openScan(next.id).catch(error=>toast(error.message,true));
  }
});
async function boot(){try{const result=await api('bootstrap');state.sessions=result.sessions;if(state.sessions.length){const id=result.active_session_id||state.sessions[0].id;state.session=await api('session',{id});state.view='session';}else state.view='library';state.importJob=result.import_job;renderShell();if(state.importJob?.status==='running')pollImport();}catch(error){document.getElementById('app').innerHTML=`<div class="empty-state"><h2>The workspace could not open.</h2><p>${esc(error.message)}</p><button class="button" onclick="location.reload()">Try again</button></div>`;}}
AFMDisplay.attach({state,api,paintCanvas:()=>paintCanvas(),toast,selectTool,restoreDrawing});
AFMCanvas.attach({state,restoreDrawing,inspect:inspectPoint,draft:draftDrawing,complete:completeDrawing,
  cancelMask:()=>AFMMask.cancel(),beginMask:p=>AFMMask.begin(p),moveMask:p=>AFMMask.move(p),
  canDraw:()=>{if(state.inspectorHidden)return false;if((state.raw||state.pending)&&state.tool!=='contrast'){toast('Select Result before measuring or leveling.');return false;}return true;},
  level:async p=>{if(state.levelPoints.length===3)state.levelPoints=[];state.levelPoints.push(p);restoreDrawing();if(state.levelPoints.length===3){try{await runOperation('three_point');}catch(error){toast(error.message,true);}}else{const count=document.getElementById('level-point-count');if(count)count.textContent=state.levelPoints.length;}}
});
AFMMask.attach({state,api,setBusy,renderContent,toast,selectTool});
boot();
