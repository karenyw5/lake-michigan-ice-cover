/* Leaflet viewer: NOAA annual maximum vs GLAHF Dec-May annual mean. */
const map = L.map('map', {preferCanvas:true, zoomControl:true}).setView([44.1,-86.8], 7);
map.createPane('icePane'); map.getPane('icePane').style.zIndex=400;
map.createPane('spawningPane'); map.getPane('spawningPane').style.zIndex=650;
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'&copy; OpenStreetMap contributors',maxZoom:19}).addTo(map);
const $=id=>document.getElementById(id);
let maxYears=[], meanYears=[], years=[], iceLayer=null, spawnLayer=null, playing=null, reqId=0;
const mem=new Map();
const status=message=>{$('status').textContent=message;};
const iceColors=['#b8e2f7','#7dc1e7','#4695cf','#1667a6','#0b3771'];
const mode=()=>$('metric').value;
function styleIce(feature){
  const v=Number(feature.properties?.concentration)||0;
  return {color:iceColors[Math.min(4,Math.max(0,Math.ceil(v/20)-1))],weight:0,fillOpacity:.85};
}
async function fetchJson(url){const response=await fetch(url);if(!response.ok)throw new Error(`${response.status} loading ${url}`);return response.json();}
function availableYears(){return mode()==='mean'?meanYears:maxYears.map(x=>x.year);}
function maxInfo(year){return maxYears.find(item=>item.year===year);}
async function showYear(year){
  if(!years.includes(year))return;
  const chosen=mode(), request=++reqId;
  $('yearLabel').textContent=year;
  if(chosen==='max'){
    const info=maxInfo(year);
    $('peakDate').textContent=new Date(info.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'});
    $('cover').textContent=`${Number(info.cover).toFixed(1)}% maximum`;
  } else {
    $('peakDate').textContent='December–May';
    $('cover').textContent='Winter-season mean';
  }
  status('Loading ice cover…');
  try{
    const key=`${chosen}:${year}`;
    let geo=mem.get(key);
    if(!geo){
      const url=chosen==='max'?`data/${year}.geojson`:`data/mean/${year}.geojson`;
      geo=await fetchJson(url);mem.set(key,geo);
      if(mem.size>5)mem.delete(mem.keys().next().value);
    }
    if(request!==reqId)return;
    const next=L.geoJSON(geo,{
      pane:'icePane',style:styleIce,
      onEachFeature:(f,layer)=>layer.bindPopup(`${chosen==='max'?'Ice concentration':'Mean ice concentration'}: ${f.properties?.concentration ?? '?'}%`)
    });
    if(iceLayer)map.removeLayer(iceLayer);
    iceLayer=next.addTo(map);
    status('');
  }catch(error){if(request===reqId)status(`Could not load ${chosen} ${year}: ${error.message}`);}
}
function stop(){if(playing){clearInterval(playing);playing=null;}$('play').textContent='▶';$('play').setAttribute('aria-label','Play timeline');}
function updateFromSlider(){const idx=Number($('year').value);if(years[idx]!==undefined)showYear(years[idx]);}
function refreshMetric(){
  stop();reqId++;
  const previous=Number($('yearLabel').textContent);
  years=availableYears();
  if(!years.length){
    $('year').disabled=true;$('play').disabled=true;
    if(iceLayer){map.removeLayer(iceLayer);iceLayer=null;}
    $('yearLabel').textContent='—';$('peakDate').textContent='—';$('cover').textContent='—';
    $('minYear').textContent='—';$('maxYear').textContent='—';
    status('No GLAHF mean layers prepared. Run convert_glahf.py locally.');return;
  }
  let idx=years.indexOf(previous);
  if(idx<0)idx=years.length-1;
  $('year').min=0;$('year').max=years.length-1;$('year').step=1;$('year').value=idx;$('year').disabled=false;
  $('minYear').textContent=years[0];$('maxYear').textContent=years.at(-1);
  $('play').disabled=false;
  showYear(years[idx]);
}
$('metric').addEventListener('change',refreshMetric);
$('year').addEventListener('input',()=>{stop();updateFromSlider();});
$('play').addEventListener('click',()=>{
  if(playing){stop();return;}
  if(!years.length)return;
  $('play').textContent='❚❚';$('play').setAttribute('aria-label','Pause timeline');
  playing=setInterval(()=>{
    let idx=Number($('year').value)+1;if(idx>=years.length)idx=0;
    $('year').value=idx;updateFromSlider();
  },1800);
});
$('spawning').addEventListener('change',()=>{
  if(spawnLayer){if($('spawning').checked)spawnLayer.addTo(map);else map.removeLayer(spawnLayer);}
});
async function initSpawning(){
  try{
    const geo=await fetchJson('data/spawning.geojson');
    spawnLayer=L.geoJSON(geo,{
      pane:'spawningPane',
      pointToLayer:(f,ll)=>L.circleMarker(ll,{pane:'spawningPane',radius:4,color:'#ffffff',weight:1,fillColor:'#f28c28',fillOpacity:1,opacity:1}),
      style:()=>({color:'#ffffff',weight:1,fillColor:'#f28c28',fillOpacity:1}),
      onEachFeature:(f,l)=>l.bindPopup('Historic whitefish spawning location')
    });
    if($('spawning').checked)spawnLayer.addTo(map);
    try{$('spawningNote').textContent=await(await fetch('data/spawning_source.txt')).text();}catch{}
  }catch{
    $('spawning').checked=false;$('spawning').disabled=true;$('spawningNote').textContent='Overlay not installed — see README';
  }
}
async function init(){
  try{
    maxYears=await fetchJson('data/years.json');maxYears.sort((a,b)=>a.year-b.year);
    if(!maxYears.length)throw new Error('No NOAA years. Run python build_data.py --download.');
    try{meanYears=await fetchJson('data/mean/years.json');meanYears=meanYears.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);}catch{meanYears=[];}
    if(!meanYears.length)$('meanOption').textContent='December–May mean (GLAHF — data not installed)';
    refreshMetric();await initSpawning();
  }catch(error){status(`Map setup: ${error.message}`);$('play').disabled=true;}
}
$('play').disabled=true;init();
