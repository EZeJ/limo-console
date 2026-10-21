/* Local dataset browser. No driving or recording-lifecycle requests. */
const $ = (selector) => document.querySelector(selector);
let catalog = [], selected = null, detail = null, playbackTimer = null, exportTimer = null;
const size = (n) => n > 1024 ** 3 ? (n / 1024 ** 3).toFixed(2) + ' GB' : (n / 1024 ** 2).toFixed(1) + ' MB';
async function request(path, data) {
  const response = await fetch(path, {method: data ? 'POST' : 'GET', headers: {'X-Limo-Control':'1','Content-Type':'application/json'}, ...(data ? {body: JSON.stringify(data)} : {})});
  const result = await response.json(); if (!response.ok) throw Error(result.error || response.statusText); return result;
}
function fail(error) { $('#dataError').textContent = t(error.message); }
function query(extra = {}) { return new URLSearchParams({...selected, ...extra}).toString(); }
function node(tag, text, className) { const value = document.createElement(tag); if (text != null) value.textContent = text; if (className) value.className = className; return value; }
async function refresh() {
  try { catalog = (await request('/local/data')).sessions; $('#dataError').textContent = ''; renderCatalog(); }
  catch (error) { fail(error); }
}
function renderCatalog() {
  const search = $('#dataSearch').value.toLowerCase(); $('#sessionList').replaceChildren();
  for (const session of catalog) {
    const matches = session.instances.filter(i => (session.session_id + i.instance_id + (i.name || '')).toLowerCase().includes(search));
    if (!matches.length) continue;
    $('#sessionList').append(node('h3',session.session_id));
    for (const item of matches) {
      const button = node('button', null, 'dataset-item' + (selected?.instance === item.instance_id ? ' selected' : ''));
      button.append(node('strong', item.name || item.instance_id), node('small', `${t(item.status || 'unknown')} · ${(item.duration_s || 0).toFixed(1)} s · ${item.video_frames || 0} ${t('frames')}`));
      button.onclick = () => choose(session.session_id,item.instance_id); $('#sessionList').append(button);
    }
  }
  if (!catalog.length) $('#sessionList').append(node('p',t('No recordings yet. Start recording from the controls.')));
}
async function choose(session,instance) {
  clearInterval(playbackTimer); playbackTimer=null; clearTimeout(exportTimer);
  $('#recordedVideo').pause(); selected={session,instance}; renderCatalog();
  try {
    detail=await request('/local/data/detail?'+query()); $('#dataError').textContent='';
    $('#dataEmpty').hidden=true; $('#dataContent').hidden=false; renderDetail(); configurePlayback();
  } catch (error) { fail(error); }
}
function renderDetail() {
  if (!detail) return;
  const m=detail.manifest, p=m.camera_profile || {};
  $('#dataTitle').textContent=m.name || m.instance_id;
  $('#dataMeta').textContent=`${t(m.status || 'unknown')} · ${detail.duration_s.toFixed(1)} s · ${detail.frame_count} ${t('frames')} · ${p.width || '—'} × ${p.height || '—'} · ${p.fps || '—'} fps · ${(p.format || '').toUpperCase()}`;
  $('#sourcePath').textContent=detail.source_directory;
  const bundle=detail.bundle || {state:'not_bundled'};
  $('#packageData').disabled=!m.video_closed || ['queued','running'].includes(bundle.state);
  $('#packageDownload').hidden=bundle.state!=='done';
  if(bundle.state==='done') { $('#packageDownload').href='/local/data/bundle?'+query(); $('#packageDownload').download=bundle.filename; }
  $('#packageState').textContent=bundle.state==='done' ? size(bundle.bytes) : bundle.state==='running' ? t('Packaging…')+` ${bundle.files_done}/${bundle.files_total}` : bundle.state==='queued' ? t('Package queued') : bundle.error ? t(bundle.error) : '';
  $('#dataIncidents').textContent=(m.incidents || []).map(i=>t(i.reason)).join(' · ');
  $('#exportData').disabled=!m.video_closed || ['queued','running'].includes(detail.export.state);
  $('#exportState').textContent=t({queued:'Export queued',running:'Exporting and validating…',done:'CSV export available',error:'Export failed',not_exported:'Export CSV to inspect trajectory and metrics'}[detail.export.state] || 'Export CSV to inspect trajectory and metrics') + (detail.export.error ? ': '+t(detail.export.error) : '');
  $('#topicRows').replaceChildren(...Object.entries(detail.topics).sort().map(([name,count])=>{const row=node('tr');row.append(node('td',name),node('td',count.toLocaleString()));return row;}));
  $('#dataFiles').replaceChildren(...detail.files.map(file=>{const row=node('li');const link=node('a',file.name);link.href='/local/data/file?'+query({file:file.name});link.download=file.name.split('/').pop();row.append(link,node('span',size(file.bytes)));return row;}));
  $('#dataEvents').replaceChildren(node('pre',detail.events.map(e=>e.event_json).join('\n') || t('Export CSV to inspect recorded events')));
  $('#trajectoryHint').textContent=detail.trajectory.length ? t('Plots are sampled for display; CSV and MCAP preserve the recorded samples.') : t('Export CSV to inspect trajectory and metrics');
  drawPlots();
}
function configurePlayback() {
  const video=detail.files.find(f=>f.name==='camera.mp4') || detail.files.find(f=>f.name==='camera.mp4.partial');
  $('#recordedVideo').hidden=!video; $('#recordedFrame').hidden=!!video || !detail.frame_count; $('#framePlayback').hidden=!!video || !detail.frame_count;
  $('#playbackNote').textContent=video ? t('Video stays on this computer.') : t('Frame preview; original lossless files remain available for download.');
  if (video) { $('#recordedVideo').src='/local/data/file?'+query({file:video.name}); }
  else if (detail.frame_count) { $('#frameIndex').max=detail.frame_count-1; $('#frameIndex').value=0; showFrame(); }
}
function showFrame() {
  const index=Number($('#frameIndex').value); $('#recordedFrame').src='/local/data/frame?'+query({index}); $('#framePosition').textContent=`${index+1} / ${detail.frame_count}`;
}
$('#frameIndex').oninput=showFrame;
$('#playFrames').onclick=()=>{
  if (playbackTimer) {clearInterval(playbackTimer);playbackTimer=null;$('#playFrames').textContent=t('Play frames');return;}
  $('#playFrames').textContent=t('Pause playback');
  playbackTimer=setInterval(()=>{const input=$('#frameIndex');input.value=(Number(input.value)+1)%Math.max(1,detail.frame_count);showFrame();},250);
};
function drawPlots() {
  const rows=detail.trajectory, c=$('#trajectoryPlot'),g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);g.fillStyle='#f6f9f8';g.fillRect(0,0,c.width,c.height);
  if (rows.length) {
    const xs=rows.map(r=>r[1]),ys=rows.map(r=>r[2]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
    const scale=Math.min((c.width-100)/Math.max(.1,xmax-xmin),(c.height-100)/Math.max(.1,ymax-ymin));
    const point=r=>[c.width/2+(r[1]-(xmin+xmax)/2)*scale,c.height/2-(r[2]-(ymin+ymax)/2)*scale];
    g.strokeStyle='#278673';g.lineWidth=3;g.beginPath();rows.forEach((r,i)=>{const p=point(r);i?g.lineTo(...p):g.moveTo(...p);});g.stroke();
    for (const [r,color] of [[rows[0],'#647e7a'],[rows.at(-1),'#ce8c51']]) {g.fillStyle=color;g.beginPath();g.arc(...point(r),7,0,Math.PI*2);g.fill();}
    g.fillStyle='#69817b';g.font='16px sans-serif';g.fillText(`X ${xmin.toFixed(2)} … ${xmax.toFixed(2)} m`,25,c.height-20);g.fillText(`Y ${ymin.toFixed(2)} … ${ymax.toFixed(2)} m`,25,25);
  }
  const chart=$('#speedPlot'),ctx=chart.getContext('2d');ctx.clearRect(0,0,chart.width,chart.height); if (!rows.length)return;
  const maxT=Math.max(.1,rows.at(-1)[0]),values=rows.flatMap(r=>r.slice(3)).filter(v=>v!==null),bound=Math.max(.05,...values.map(Math.abs));
  ctx.strokeStyle='#e1e8e5';ctx.beginPath();ctx.moveTo(55,140);ctx.lineTo(1180,140);ctx.stroke();
  for (const [col,color] of [[3,'#20816e'],[4,'#537ab4'],[5,'#cf8b47']]) {ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();let started=false;for(const r of rows){if(r[col]===null)continue;const x=55+r[0]/maxT*1125,y=140-r[col]/bound*110;started?ctx.lineTo(x,y):ctx.moveTo(x,y);started=true;}ctx.stroke();}
  ctx.fillStyle='#789087';ctx.font='14px sans-serif';ctx.fillText(bound.toFixed(2),4,25);ctx.fillText('0',25,145);ctx.fillText((-bound).toFixed(2),4,255);ctx.fillText('0 s',55,275);ctx.fillText(maxT.toFixed(1)+' s',1100,275);
}
$('#exportData').onclick=async()=>{
  try { detail.export=await request('/local/data/export',selected);renderDetail();pollExport(); } catch(error){fail(error);}
};
async function pollExport() {
  const key=JSON.stringify(selected);
  try { const result=await request('/local/data/detail?'+query());if(key!==JSON.stringify(selected))return;detail=result;renderDetail();if(['queued','running'].includes(detail.export.state) || ['queued','running'].includes(detail.bundle?.state))exportTimer=setTimeout(pollExport,1200); }catch(error){fail(error);}
}
$('#dataSearch').oninput=renderCatalog;$('#refreshData').onclick=refresh;
window.addEventListener('languagechange',()=>{renderCatalog();renderDetail();});refresh();

$('#packageData').onclick=async()=>{try { detail.bundle=await request('/local/data/package',selected);renderDetail();pollExport(); }catch(error){fail(error);}};
$('#openSourceFolder').onclick=()=>request('/local/data/open-folder',selected).catch(fail);
