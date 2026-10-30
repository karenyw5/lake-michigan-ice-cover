"""Spawning site overlays.

Preferred: user's exact Data Basin ZIP Archive (shapefile), downloaded after signing in.
Alternative: NOAA/UMich/Michigan DNR spawning & nursery sites service (related, not identical).
"""
from __future__ import annotations
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZipFile
import requests
import shapefile
from pyproj import CRS, Transformer

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / 'data'
DATABASIN_URL = 'https://databasin.org/datasets/d89059c26cda4f3db8dc70b2a8a09200/'
NOAA_URL = ('https://gis.ngdc.noaa.gov/arcgis/rest/services/nccos/'
            'BiogeographicAssessments_NCCOS_LakeMichigan/MapServer/32/query')
NOAA_CACHE = DATA_DIR / 'spawning_grounds_noaa.geojson'


def _is_michigan_coord(coords):
    """Ignore features far outside the Lake Michigan basin."""
    # Bounding coordinate test for simple point; polygon/line vertices handled elsewhere.
    return -89.4 <= coords[0] <= -84.2 and 41.1 <= coords[1] <= 46.8


def _transform_coords(geometry, transformer):
    if transformer is None:
        return geometry
    def walk(items):
        if items and isinstance(items[0], (int, float)):
            x, y = transformer.transform(float(items[0]), float(items[1]))
            return [x,y] + list(items[2:])
        return [walk(c) for c in items]
    return {**geometry, 'coordinates': walk(geometry['coordinates'])}


def _approx_location(geometry):
    coords = geometry.get('coordinates', [])
    while coords and isinstance(coords[0], (list, tuple)):
        coords = coords[0]
    return coords if len(coords) >= 2 else None


def shapefile_zip_to_geojson(zip_path: Path):
    """Read .shp/.shx/.dbf directly out of a zipped shapefile with no GIS conversion."""
    features=[]
    with ZipFile(zip_path) as z:
        shp_candidates=[p for p in z.namelist() if p.lower().endswith('.shp') and not '__macosx' in p.lower()]
        if not shp_candidates:
            raise ValueError('No shapefile (.shp) inside ZIP. In Data Basin select Zip Archive, not ArcGIS Layer Package.')
        for shp_name in shp_candidates:
            base = shp_name[:-4]
            names = {p.lower():p for p in z.namelist()}
            if base.lower()+'.dbf' not in names:
                continue
            with shapefile.Reader(
                shp=io.BytesIO(z.read(shp_name)),
                shx=io.BytesIO(z.read(names[base.lower()+'.shx'])) if base.lower()+'.shx' in names else None,
                dbf=io.BytesIO(z.read(names[base.lower()+'.dbf'])),
                encoding='latin1') as reader:
                transformer=None
                prj_name=names.get(base.lower()+'.prj')
                if prj_name:
                    crs = CRS.from_wkt(z.read(prj_name).decode('utf-8-sig', errors='replace'))
                    if crs.to_epsg() != 4326:
                        transformer = Transformer.from_crs(crs,'EPSG:4326',always_xy=True)
                for record in reader.iterShapeRecords():
                    geom=record.shape.__geo_interface__
                    if not geom or geom['type']=='Null':
                        continue
                    geom=_transform_coords(geom,transformer)
                    xy=_approx_location(geom)
                    if not xy or not _is_michigan_coord(xy):
                        continue
                    props={k: v for k,v in zip([f[0] for f in reader.fields[1:]],record.record) if isinstance(v,(int,float,str,bool))}
                    features.append({'type':'Feature','geometry':geom,'properties':props})
    if not features:
        raise ValueError('No Lake Michigan features found in ZIP. Check that you downloaded the spawning sites ZIP Archive.')
    return {'type':'FeatureCollection','features':features}


def find_databasin_data(folder=DATA_DIR):
    folder=Path(folder)
    # Exact, user-provided Data Basin dataset takes priority over the NOAA alternative.
    for pattern in ('spawning_grounds.geojson','spawning_grounds.zip','spawning_grounds.json'):
        file=folder/pattern
        if file.is_file():
            return file
    return None


def load_databasin(folder=DATA_DIR):
    path=find_databasin_data(folder)
    if path is None:
        return None
    if path.suffix.lower()=='.zip':
        return shapefile_zip_to_geojson(path)
    with open(path,encoding='utf-8') as f:
        data=json.load(f)
    if data.get('type')!='FeatureCollection':
        raise ValueError('Expected a GeoJSON FeatureCollection')
    return data


def load_noaa(cache_path=NOAA_CACHE):
    """NOAA related lake whitefish sites; source is not the exact Data Basin layer."""
    cache_path=Path(cache_path)
    if cache_path.exists():
        with open(cache_path,encoding='utf-8') as f: return json.load(f)
    params={'where': "Species='Lake whitefish'",'outFields':'*',
            'outSR':4326,'returnGeometry':'true','f':'geojson'}
    r=requests.get(NOAA_URL,params=params,timeout=25,
                   headers={'User-Agent':'LakeMichiganWhitefish-EducationalMap/2.0'})
    r.raise_for_status()
    data=r.json()
    if data.get('type')!='FeatureCollection':
        raise ValueError(f"NOAA GIS response is not GeoJSON: {str(data)[:250]}")
    feats=[f for f in data.get('features',[]) if f.get('geometry')]
    if not feats: raise ValueError('NOAA returned no lake whitefish spawning sites')
    data={'type':'FeatureCollection','features':feats}
    cache_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=cache_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data),encoding='utf-8')
    tmp.replace(cache_path)
    return data


def layer_data(geo):
    """Separate points from lines/polygons, for appropriately styled PyDeck layers."""
    pts=[]; shapes=[]
    for f in geo.get('features',[]):
        geom=f.get('geometry') or {}; kind=geom.get('type')
        if kind=='Point':
            lon,lat=geom['coordinates'][:2]
            if _is_michigan_coord((lon,lat)):
                pts.append({'lon':float(lon),'lat':float(lat),
                            'label':str(f.get('properties',{}).get('Place', 'Historic whitefish spawning site'))})
        elif kind=='MultiPoint':
            for lon,lat,*_ in geom['coordinates']:
                if _is_michigan_coord((lon,lat)):
                    pts.append({'lon':float(lon),'lat':float(lat),'label':'Historic whitefish spawning site'})
        elif kind in ('Polygon','MultiPolygon','LineString','MultiLineString'):
            shapes.append(f)
    return pts, {'type':'FeatureCollection','features':shapes}
