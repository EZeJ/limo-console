/* Local dataset browser. No driving or recording-lifecycle requests. */
const $ = (selector) => document.querySelector(selector);
let catalog=[],selected=null,detail=null,activeSegment=0,playbackTimer=null,playingFrames=false,exportTimer=null,mapLayer=false,mapImage=null,mapImageKey='';
const colors=['#278673','#537ab4','#ce8c51','#956ab1','#9b6363','#6e8d48'];
const size=n=>n>1024**3?(n/1024**3).toFixed(2)+' GB':(n/1024**2).toFixed(1)+' MB';
const isSession=()=>detail?.scope==='session';
const segments=()=>detail?DatasetView.segments(detail):[];
const active=()=>segments()[activeSegment];
const currentSelection=()=>JSON.stringify(selected);
const query=(extra={})=>new URLSearchParams(Object.entries({...selected,...extra}).filter(([,value])=>value!=null)).toString();
const mediaQuery=(extra={})=>query({instance:active()?.instance_id || selected.instance,...extra});
const detailURL=()=>'/local/data/'+(selected.instance?'detail':'session')+'?'+query();
async function request(path,data) {
  const response=await fetch(path,{method:data?'POST':'GET',headers:{'X-Limo-Control':'1','Content-Type':'application/json'},...(data?{body:JSON.stringify(data)}:{})});
  const result=await response.json();if(!response.ok)throw Error(result.error || response.statusText);return result;
}
function fail(error){$('#dataError').textContent=t(error.message);}
function node(tag,text,className){const value=document.createElement(tag);if(text!=null)value.textContent=text;if(className)value.className=className;return value;}
async function refresh(){try{catalog=(await request('/local/data')).sessions;$('#dataError').textContent='';renderCatalog();if(selected)await pollExport();}catch(error){fail(error);}}
function renderCatalog(){
  const search=$('#dataSearch').value.toLowerCase();$('#sessionList').replaceChildren();
  for(const session of catalog){
    const matches=session.instances.filter(i=>(session.session_id+i.instance_id+(i.name||'')).toLowerCase().includes(search));if(!matches.length)continue;
    const button=node('button',null,'dataset-session'+(selected?.session===session.session_id&&!selected.instance?' selected':''));
    button.append(node('strong',t('Entire recording')),node('small',session.session_id),node('span',`${session.instances.length} ${t('segments')} · ${session.instances.reduce((sum,i)=>sum+(i.video_frames||0),0).toLocaleString()} ${t('frames')}`));
    button.onclick=()=>choose(session.session_id);$('#sessionList').append(button);
    const list=node('details',null,'catalog-segments');list.append(node('summary',t('Individual segments')));
    if(search || selected?.session===session.session_id && selected.instance)list.open=true;
    for(const item of matches){
      const entry=node('button',null,'dataset-item'+(selected?.session===session.session_id&&selected.instance===item.instance_id?' selected':''));
      entry.append(node('strong',item.name||item.instance_id),node('small',`${t(item.status||'unknown')} · ${(item.duration_s||0).toFixed(1)} s · ${item.video_frames||0} ${t('frames')}`));
      entry.onclick=()=>choose(session.session_id,item.instance_id);list.append(entry);
    }
    $('#sessionList').append(list);
  }
  if(!catalog.length)$('#sessionList').append(node('p',t('No recordings yet. Start recording from the controls.')));
}
function stopPlayback(){clearTimeout(playbackTimer);playbackTimer=null;playingFrames=false;$('#recordedVideo').pause();$('#playFrames').textContent=t('Play frames');}
async function choose(session,instance){
  stopPlayback();clearTimeout(exportTimer);selected=instance?{session,instance}:{session};const key=currentSelection();
  activeSegment=0;mapLayer=false;mapImage=null;mapImageKey='';detail=null;$('#dataContent').hidden=true;renderCatalog();
  try{
    const result=await request(detailURL());if(key!==currentSelection())return;detail=result;$('#dataError').textContent='';
    $('#dataEmpty').hidden=true;$('#dataContent').hidden=false;renderDetail();configurePlayback();pollIfWorking();
  }catch(error){if(key===currentSelection())fail(error);}
}
function renderDetail(){
  if(!detail)return;
  const session=isSession(),segment=active(),m=segment.manifest,p=m.camera_profile||{},closed=session?detail.closed:m.video_closed;
  $('#dataTitle').textContent=session?t('Entire recording')+' · '+detail.session_id:m.name||m.instance_id;
  $('#dataMeta').textContent=session?`${segments().length} ${t('segments')} · ${detail.duration_s.toFixed(1)} s · ${detail.frame_count.toLocaleString()} ${t('frames')}`:
    `${t(m.status||'unknown')} · ${detail.duration_s.toFixed(1)} s · ${detail.frame_count.toLocaleString()} ${t('frames')} · ${p.width||'—'} × ${p.height||'—'} · ${p.fps||'—'} fps · ${(p.format||'').toUpperCase()}`;
  $('#sourcePath').textContent=detail.source_directory;
  const bundle=detail.bundle||{state:'not_bundled'};
  $('#packageData').textContent=t(session?'Package entire recording ZIP':'Package instance ZIP');
  $('#packageData').disabled=!closed||['queued','running'].includes(bundle.state);
  $('#packageDownload').hidden=bundle.state!=='done';
  if(bundle.state==='done'){$('#packageDownload').href='/local/data/bundle?'+query();$('#packageDownload').download=bundle.filename;}
  $('#packageState').textContent=bundle.state==='done'?size(bundle.bytes):bundle.state==='running'?t('Packaging…')+` ${bundle.files_done||0}/${bundle.files_total||0}`:bundle.state==='queued'?t('Package queued'):bundle.error?t(bundle.error):'';
  $('#dataIncidents').textContent=segments().flatMap(s=>(s.manifest.incidents||[]).map(i=>(session?(s.manifest.name||s.instance_id)+': ':'')+t(i.reason))).join(' · ');
  $('#exportData').textContent=t(session?'Export all segments & validate':'Export CSV & validate');
  $('#exportData').disabled=!closed||['queued','running'].includes(detail.export.state);
  const labels={queued:'Export queued',running:'Exporting and validating…',done:'CSV export available',partial:'Some segments failed; successful exports are available',error:'Export failed',not_exported:'Export CSV to inspect trajectory and metrics'};
  $('#exportState').textContent=t(labels[detail.export.state]||labels.not_exported)+(detail.export.instances_total?` ${detail.export.instances_done}/${detail.export.instances_total}`:'')+(detail.export.error?': '+t(detail.export.error):'')+(!closed?' · '+t('End this recording before processing the whole session'):'');
  $('#exportResults').replaceChildren(...(detail.export.results||[]).map(result=>node('p',`${result.instance_id} · ${t(result.state==='error'?'Export failed':result.report?.complete_received_stream?'Received stream verified':'Received stream has gaps')}${result.error?': '+result.error:''}`,result.state==='error'?'error':'setting-note')));
  $('#topicRows').replaceChildren(...Object.entries(detail.topics).sort().map(([name,count])=>{const row=node('tr');row.append(node('td',name),node('td',count.toLocaleString()));return row;}));
  $('#dataFiles').replaceChildren(...detail.files.map(file=>{const row=node('li'),name=(session&&file.instance?file.instance+'/':'')+file.name,link=node('a',name);link.href='/local/data/file?'+query({instance:session?file.instance:selected.instance,file:file.name});link.download=file.name.split('/').pop();row.append(link,node('span',size(file.bytes)));return row;}));
  $('#dataEvents').replaceChildren(node('pre',detail.events.map(e=>(e.instance_id?e.instance_id+' · ':'')+e.event_json).join('\n')||t('Export CSV to inspect recorded events')));
  $('#trajectoryHint').textContent=segments().some(s=>s.trajectory.length)?t('Plots are sampled for display; CSV and MCAP preserve the recorded samples.'):t('Export CSV to inspect trajectory and metrics');
  $('#toggleMapLayer').disabled=!segment.map?.alignment_available;
  if(!segment.map?.alignment_available)mapLayer=false;
  $('#toggleMapLayer').textContent=t(mapLayer?'Hide map background':'Show map background');$('#toggleMapLayer').setAttribute('aria-pressed',String(mapLayer));
  $('#mapLayerHint').textContent=segment.map?.alignment_available?t(session?'Map background shows the selected segment; hide it to compare all segments.':'Aligned using the map transform recorded with this instance.'):t('Export an instance containing a map and localization to enable this layer.');
  const imageKey=mediaQuery({file:'map.png',stamp:segment.map?.source_stamp_ns});
  if(segment.map&&imageKey!==mapImageKey){mapImageKey=imageKey;mapImage=new Image();mapImage.onload=drawPlots;mapImage.src='/local/data/file?'+imageKey;}
  renderPlaylist();drawPlots();
}
function renderPlaylist(){
  $('#sessionOverview').hidden=!isSession();$('#playingSegment').textContent=isSession()?`${activeSegment+1} / ${segments().length} · ${active().manifest.name||active().instance_id}`:'';
  if(!isSession())return;
  $('#segmentPlaylist').replaceChildren(...segments().map((segment,index)=>{
    const button=node('button',null,'playlist-item'+(index===activeSegment?' selected':''));button.style.setProperty('--segment-color',colors[index%colors.length]);button.setAttribute('aria-pressed',String(index===activeSegment));
    button.append(node('strong',`${index+1}. ${segment.manifest.name||segment.instance_id}`),node('small',`${t(segment.manifest.status||'unknown')} · ${segment.duration_s.toFixed(1)} s · ${segment.frame_count} ${t('frames')}`));
    button.onclick=()=>selectSegment(index,playingFrames||!$('#recordedVideo').paused);return button;
  }));
  $('#segmentPosition').textContent=`${activeSegment+1} / ${segments().length}`;$('#previousSegment').disabled=activeSegment===0;$('#nextSegment').disabled=activeSegment===segments().length-1;
}
function selectSegment(index,autoplay=false){stopPlayback();activeSegment=index;mapImage=null;mapImageKey='';renderDetail();configurePlayback(autoplay);}
function advancePlayback(){
  const next=DatasetView.nextPlayable(segments(),activeSegment);
  if(isSession()&&$('#continuousPlayback').checked&&next>=0)selectSegment(next,true);else stopPlayback();
}
function configurePlayback(autoplay=false){
  const segment=active(),video=segment.files.find(f=>f.name==='camera.mp4')||segment.files.find(f=>f.name==='camera.mp4.partial');
  $('#recordedVideo').hidden=!video;$('#recordedFrame').hidden=!!video||!segment.frame_count;$('#framePlayback').hidden=!!video||!segment.frame_count;
  $('#playbackNote').textContent=t(!segment.frame_count?'No camera frames in this segment':video?'Video stays on this computer.':'Frame preview; original lossless files remain available for download.');
  if(video){$('#recordedVideo').src='/local/data/file?'+mediaQuery({file:video.name});if(autoplay)$('#recordedVideo').play().catch(()=>{$('#playbackNote').textContent=t('Press play to continue playback');});}
  else if(segment.frame_count){$('#frameIndex').max=segment.frame_count-1;$('#frameIndex').value=0;playingFrames=autoplay;showFrame();$('#playFrames').textContent=t(playingFrames?'Pause playback':'Play frames');}
  else if(autoplay)advancePlayback();
}
function showFrame(){const index=Number($('#frameIndex').value);$('#recordedFrame').src='/local/data/frame?'+mediaQuery({index});$('#framePosition').textContent=`${index+1} / ${active().frame_count}`;}
$('#recordedFrame').onload=()=>{if(!playingFrames)return;clearTimeout(playbackTimer);playbackTimer=setTimeout(()=>{const input=$('#frameIndex');if(Number(input.value)>=active().frame_count-1)return advancePlayback();input.value=Number(input.value)+1;showFrame();},1000/(active().manifest.camera_profile?.fps||5));};
$('#recordedFrame').onerror=()=>{if(playingFrames)stopPlayback();$('#playbackNote').textContent=t('Frame is not available yet');};
$('#recordedVideo').onended=advancePlayback;
$('#recordedVideo').onerror=()=>{$('#playbackNote').textContent=t('Video preview unavailable; download the original file.');};
$('#frameIndex').oninput=()=>{clearTimeout(playbackTimer);showFrame();};
$('#playFrames').onclick=()=>{if(playingFrames){stopPlayback();return;}playingFrames=true;$('#playFrames').textContent=t('Pause playback');if(Number($('#frameIndex').value)>=active().frame_count-1)$('#frameIndex').value=0;showFrame();};
$('#previousSegment').onclick=()=>selectSegment(Math.max(0,activeSegment-1));
$('#nextSegment').onclick=()=>selectSegment(Math.min(segments().length-1,activeSegment+1));
function drawPlots(){
  if(!detail)return;
  const series=DatasetView.series(detail),segment=active(),c=$('#trajectoryPlot'),g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);g.fillStyle='#f6f9f8';g.fillRect(0,0,c.width,c.height);
  const map=mapLayer&&segment.map?.alignment_available?segment.map:null,tf=map?.odom_to_map;
  const tracks=(map?[{id:segment.instance_id,rows:segment.trajectory}]:series).filter(s=>s.rows.length).map(s=>({...s,rows:s.rows.map(r=>tf?[r[0],tf[0]+Math.cos(tf[2])*r[1]-Math.sin(tf[2])*r[2],tf[1]+Math.sin(tf[2])*r[1]+Math.cos(tf[2])*r[2]]:r)}));
  const xs=tracks.flatMap(s=>s.rows.map(r=>r[1])),ys=tracks.flatMap(s=>s.rows.map(r=>r[2]));
  if(map)for(const x of [0,map.width*map.resolution])for(const y of [0,map.height*map.resolution]){xs.push(map.origin[0]+Math.cos(map.origin[2])*x-Math.sin(map.origin[2])*y);ys.push(map.origin[1]+Math.sin(map.origin[2])*x+Math.cos(map.origin[2])*y);}
  if(xs.length){
    const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys),scale=Math.min((c.width-100)/Math.max(.1,xmax-xmin),(c.height-100)/Math.max(.1,ymax-ymin));
    const point=r=>[c.width/2+(r[1]-(xmin+xmax)/2)*scale,c.height/2-(r[2]-(ymin+ymax)/2)*scale];
    if(map&&mapImage?.complete&&mapImage.naturalWidth){g.save();g.translate(...point([0,map.origin[0],map.origin[1]]));g.rotate(-map.origin[2]);g.scale(scale*map.resolution,scale*map.resolution);g.imageSmoothingEnabled=false;g.drawImage(mapImage,0,-map.height,map.width,map.height);g.restore();}
    tracks.forEach((track,index)=>{g.strokeStyle=colors[index%colors.length];g.lineWidth=3;g.beginPath();track.rows.forEach((r,i)=>{const p=point(r);i?g.lineTo(...p):g.moveTo(...p);});g.stroke();for(const r of [track.rows[0],track.rows.at(-1)]){g.fillStyle=g.strokeStyle;g.beginPath();g.arc(...point(r),5,0,Math.PI*2);g.fill();}});
    g.fillStyle='#69817b';g.font='16px sans-serif';g.fillText(`X ${xmin.toFixed(2)} … ${xmax.toFixed(2)} m`,25,c.height-20);g.fillText(`Y ${ymin.toFixed(2)} … ${ymax.toFixed(2)} m`,25,25);
  }
  const chart=$('#speedPlot'),ctx=chart.getContext('2d');ctx.clearRect(0,0,chart.width,chart.height);const rows=series.flatMap(s=>s.rows);if(!rows.length)return;
  const maxT=Math.max(.1,...rows.map(r=>r[0])),values=rows.flatMap(r=>r.slice(3)).filter(v=>v!==null),bound=Math.max(.05,...values.map(Math.abs));
  ctx.strokeStyle='#e1e8e5';ctx.beginPath();ctx.moveTo(55,140);ctx.lineTo(1180,140);ctx.stroke();
  for(const [col,color] of [[3,'#20816e'],[4,'#537ab4'],[5,'#cf8b47']]){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();for(const s of series){let started=false;for(const r of s.rows){if(r[col]===null){started=false;continue;}const x=55+r[0]/maxT*1125,y=140-r[col]/bound*110;started?ctx.lineTo(x,y):ctx.moveTo(x,y);started=true;}}ctx.stroke();}
  ctx.fillStyle='#789087';ctx.font='14px sans-serif';ctx.fillText(bound.toFixed(2),4,25);ctx.fillText('0',25,145);ctx.fillText((-bound).toFixed(2),4,255);ctx.fillText('0 s',55,275);ctx.fillText(maxT.toFixed(1)+' s',1100,275);
}
function pollIfWorking(){clearTimeout(exportTimer);if(detail&&(['queued','running'].includes(detail.export.state)||['queued','running'].includes(detail.bundle?.state)))exportTimer=setTimeout(pollExport,1200);}
async function pollExport(){const key=currentSelection();try{const result=await request(detailURL());if(key!==currentSelection())return;detail=result;activeSegment=Math.min(activeSegment,segments().length-1);renderDetail();pollIfWorking();}catch(error){if(key===currentSelection())fail(error);}}
async function startJob(kind){const key=currentSelection();try{const result=await request('/local/data/'+(isSession()?'session/':'')+kind,selected);if(key!==currentSelection())return;detail[kind==='export'?'export':'bundle']=result;renderDetail();pollIfWorking();}catch(error){fail(error);}}
$('#exportData').onclick=()=>startJob('export');$('#packageData').onclick=()=>startJob('package');
$('#openSourceFolder').onclick=()=>request('/local/data/open-folder',selected).catch(fail);
$('#toggleMapLayer').onclick=()=>{mapLayer=!mapLayer;renderDetail();};
$('#dataSearch').oninput=renderCatalog;$('#refreshData').onclick=refresh;
window.addEventListener('languagechange',()=>{renderCatalog();renderDetail();$('#playFrames').textContent=t(playingFrames?'Pause playback':'Play frames');});refresh();
