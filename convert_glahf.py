"""Convert GLAHF winter (Dec-May) annual mean ice rasters from a file geodatabase
into simplified GeoJSON for the existing Leaflet / GitHub Pages site.

Run with ArcGIS Pro's Python environment, e.g.:
  python convert_glahf.py "C:/path/to/GLAHF_ICE.gdb"

Requires arcpy, numpy, pyproj. Never uploads the source geodatabase.
"""
from __future__ import annotations
import argparse, json, re, math
from pathlib import Path
import arcpy
import numpy as np
from pyproj import CRS, Transformer

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'docs'/'data'/'mean'
BBOX=(-88.6,41.45,-84.6,46.3)

def convert(path, max_cells=90, force=False, scale=1.0):
    from netcdf_utils import grid_to_geojson
    arcpy.env.workspace=str(path)
    rasters=arcpy.ListRasters() or []
    if not rasters:
        raise RuntimeError('No rasters found in geodatabase. Verify the .gdb path and ArcGIS Pro access.')
    OUT.mkdir(parents=True,exist_ok=True)
    result=[]
    for name in rasters:
        match=re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', name)
        if not match:
            print(f'SKIP {name}: no four-digit year in name')
            continue
        year=int(match.group(1))
        target=OUT/f'{year}.geojson'
        if target.exists() and not force:
            print(f'{year}: already built')
            result.append(year)
            continue
        raster=arcpy.Raster(str(path / name))
        sr=raster.spatialReference
        if not sr or sr.name=='Unknown':
            raise ValueError(f'{name}: raster has no known CRS')
        arr=np.asarray(arcpy.RasterToNumPyArray(raster, nodata_to_value=-9999),dtype=np.float32)
        if arr.ndim!=2: raise ValueError(f'{name}: expected 2D raster, got {arr.shape}')
        arr[(arr==-9999)|~np.isfinite(arr)]=np.nan
        # Source may encode percentages as 0-100 or fractions as 0-1. Verify before using --scale 100.
        arr *= scale
        if scale == 1.0 and np.isfinite(arr).any() and float(np.nanmax(arr)) <= 1.0:
            print(f"CHECK {name}: all values <= 1. Confirm whether data are fractions; if so run --scale 100.")
        plausible=arr[np.isfinite(arr)]
        if plausible.size and (plausible.min()<0 or plausible.max()>100):
            print(f'WARNING {name}: outside expected 0-100%: {plausible.min()} to {plausible.max()} (clipping invalid values)')
        arr[(arr<0)|(arr>100)]=np.nan
        # Avoid allocating a huge coordinate grid: downsample first via block means.
        h,w=arr.shape
        step=max(1, math.ceil(max(h,w)/max_cells))
        H=math.ceil(h/step);W=math.ceil(w/step)
        reduced=np.full((H,W),np.nan,np.float32)
        for i in range(H):
            for j in range(W):
                a=arr[i*step:min((i+1)*step,h), j*step:min((j+1)*step,w)]
                if np.isfinite(a).any(): reduced[i,j]=np.nanmean(a)
        # RasterToNumPyArray rows run from north to south; centers calculated accordingly.
        extent=raster.extent
        xs=extent.XMin+(np.arange(W)*step+step/2)*raster.meanCellWidth
        ys=extent.YMax-(np.arange(H)*step+step/2)*raster.meanCellHeight
        xg,yg=np.meshgrid(xs,ys)
        crs=CRS.from_wkt(sr.exportToString())
        lon,lat=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform(xg,yg)
        geo=grid_to_geojson(reduced,lon,lat,max_cells_across=max_cells)
        # Keep original statistic meaningful at popup scale; zero values are transparent.
        target.write_text(json.dumps(geo,separators=(',',':')),encoding='utf-8')
        print(f'{year}: {len(geo["features"])} features, {target.stat().st_size/1024:.0f} KiB')
        result.append(year)
    (OUT/'years.json').write_text(json.dumps(sorted(set(result))),encoding='utf-8')
    print(f'GLAHF dataset: {len(set(result))} years -> {OUT}')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('geodatabase',type=Path,help='Full path to GLAHF file geodatabase (.gdb)')
    p.add_argument('--grid',type=int,default=90,help='Resolution target (default 90 cells across)')
    p.add_argument('--force',action='store_true')
    p.add_argument('--scale',type=float,choices=[1.0,100.0],default=1.0,help='Multiply values by 100 if source rasters store fractions (0-1)')
    a=p.parse_args()
    if not a.geodatabase.exists():p.error(f'Not found: {a.geodatabase}')
    convert(a.geodatabase,a.grid,a.force,a.scale)
