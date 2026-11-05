/* GitHub Pages: browser-only Leaflet viewer of NOAA preprocessed annual-maximum GeoJSON. */
const map = L.map('map', {preferCanvas:true, zoomControl:true}).setView([44.1,-86.8], 7);

// Create separate rendering panes
map.createPane("icePane");
map.getPane("icePane").style.zIndex = 400;

map.createPane("spawningPane");
map.getPane("spawningPane").style.zIndex = 650;

L.tileLayer(
  "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  }
).addTo(map);
const $ = id => document.getElementById(id);
let years=[], iceLayer=null, spawnLayer=null, current=null, playing=null, reqId=0;
const mem = new Map(); // Cache last 4 years to reduce repeated data transfers.
const status = message => { $('status').textContent = message; };
const iceColors = ['#b8e2f7','#7dc1e7','#4695cf','#1667a6','#0b3771'];
function styleIce(feature){
  const v=Number(feature.properties?.concentration)||0;
  return {color:iceColors[Math.min(4,Math.max(0,Math.ceil(v/20)-1))],weight:0,fillOpacity:.85};
}
async function fetchJson(url){const response=await fetch(url);if(!response.ok)throw new Error(`${response.status} loading ${url}`);return response.json();}
async function showYear(year){
  const index=years.findIndex(item=>item.year===year);
  if(index<0)return;
  const info=years[index], request=++reqId;
  $('yearLabel').textContent=year;
  $('peakDate').textContent=new Date(info.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'});
  $('cover').textContent=`${info.cover.toFixed(1)}% maximum`;
  status('Loading ice cover…');
  try{
    let geo=mem.get(year);
    if(!geo){geo=await fetchJson(`data/${year}.geojson`);mem.set(year,geo);if(mem.size>4)mem.delete(mem.keys().next().value);}
    if(request!==reqId)return;
    const next=L.geoJSON(geo,{style:styleIce,onEachFeature:(f,layer)=>layer.bindPopup(`Ice concentration: ${f.properties?.concentration ?? '?'}%`)});
    if(iceLayer)map.removeLayer(iceLayer);
    iceLayer=next.addTo(map);status('');current=year;
  }catch(error){if(request===reqId)status(`Could not load ${year}: ${error.message}`);}
}
function stop(){if(playing){clearInterval(playing);playing=null;}$('play').textContent='▶';$('play').setAttribute('aria-label','Play timeline');}
function updateFromSlider(){const idx=Number($('year').value);showYear(years[idx].year);}
$('year').addEventListener('input',()=>{stop();updateFromSlider();});
$('play').addEventListener('click',()=>{
  if(playing){stop();return;}
  $('play').textContent='❚❚';$('play').setAttribute('aria-label','Pause timeline');
  playing=setInterval(()=>{let idx=Number($('year').value)+1;if(idx>=years.length)idx=0;$('year').value=idx;updateFromSlider();},1800);
});
$('spawning').addEventListener('change',()=>{if(spawnLayer){if($('spawning').checked)spawnLayer.addTo(map);else map.removeLayer(spawnLayer);}});
async function initSpawning() {
  try {
    const geo = await fetchJson('data/spawning.geojson');

    spawnLayer = L.geoJSON(geo, {
      pane: 'spawningPane',

      pointToLayer: (f, ll) => L.circleMarker(ll, {
        pane: 'spawningPane',
        radius: 4,
        color: '#ffffff',
        weight: 1,
        fillColor: '#f28c28',
        fillOpacity: 1,
        opacity: 1
      }),

      style: () => ({
        color: '#ffffff',
        weight: 1,
        fillColor: '#f28c28',
        fillOpacity: 1
      }),

      onEachFeature: (f, l) =>
        l.bindPopup('Historic whitefish spawning location')
    });

    if ($('spawning').checked) spawnLayer.addTo(map);

    try {
      $('spawningNote').textContent =
        await (await fetch('data/spawning_source.txt')).text();
    } catch {}

  } catch {
    $('spawning').checked = false;
    $('spawning').disabled = true;
    $('spawningNote').textContent =
      'Overlay not installed — see README';
  }
}
async function init(){
  try{
    years=await fetchJson('data/years.json');
    if(!years.length)throw new Error('No prepared years. Run python build_data.py --download.');
    years.sort((a,b)=>a.year-b.year);
    $('year').min=0;$('year').max=years.length-1;$('year').step=1;$('year').value=years.length-1;$('year').disabled=false;
    $('minYear').textContent=years[0].year;$('maxYear').textContent=years.at(-1).year;
    $('play').disabled=false;
    await showYear(years.at(-1).year);
    await initSpawning();
  }catch(error){status(`Map setup: ${error.message}`);$('play').disabled=true;}
}
$('play').disabled=true;
init();
