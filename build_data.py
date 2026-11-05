"""Offline preprocessing: NOAA Lake Michigan annual maximum NetCDF -> GitHub Pages GeoJSON.

No processing happens in visitors' browsers; data are generated once locally.
Existing gzip cache is reused before any NetCDF download.
"""
from __future__ import annotations
import argparse, csv, gzip, json, shutil, sys
from pathlib import Path
from annual_max import annual_max_rows, ensure_netcdf
from netcdf_utils import read_day, grid_to_geojson
from spawning_grounds import load_databasin, load_noaa

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'docs' / 'data'
CACHE = ROOT / 'cache'

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj, separators=(',',':')), encoding='utf8')
    tmp.replace(path)

def build_year(year, meta, grid=76, allow_download=False, force=False):
    target=OUT/f'{year}.geojson'
    if target.exists() and not force:
        return 'already built'
    cached=CACHE/f'{year}.geojson.gz'
    if cached.exists() and not force:
        with gzip.open(cached,'rt',encoding='utf8') as f: geo=json.load(f)
        source='existing cache'
    else:
        from annual_max import find_local
        nc=find_local(year,meta['date'])
        if nc is None:
            if not allow_download:
                raise FileNotFoundError(f'No cache or NetCDF for {year}. Run with --download to retrieve from NOAA.')
            nc=ensure_netcdf(year,meta['date'])
        ice,lon,lat=read_day(nc,None)
        geo=grid_to_geojson(ice,lon,lat,max_cells_across=grid)
        source='NetCDF'
    write_json(target,geo)
    return f'{source}; {len(geo["features"])} ice cells ({target.stat().st_size/1024:.0f} KB)'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download',action='store_true',help='Download missing daily NOAA NetCDF files')
    p.add_argument('--years',type=int,nargs='+',help='Specific year(s), e.g. --years 2014 2025')
    p.add_argument('--grid',type=int,default=76,help='Approximate max cells across lake (default 76)')
    p.add_argument('--force',action='store_true',help='Rebuild all selected outputs')
    p.add_argument('--spawning', choices=['databasin','noaa','none'], default='none',help='Add spawning dataset. Data Basin: put ZIP in data/spawning_grounds.zip; NOAA: alternative layer.')
    args=p.parse_args()
    rows=annual_max_rows()
    selection=args.years if args.years else list(rows)
    available=[]; failed=[]
    for year in selection:
        if year not in rows:
            print(f'Unknown year {year}');failed.append(year);continue
        try:
            result=build_year(year,rows[year],args.grid,args.download,args.force)
            print(f'{year}: {result}')
            available.append(year)
        except Exception as exc:
            print(f'{year}: SKIPPED - {exc}')
            failed.append(year)
    # metadata includes only years actually present on disk, not just years processed this invocation
    years=sorted(int(f.stem) for f in OUT.glob('????.geojson'))
    write_json(OUT/'years.json',[{'year':y,'date':rows[y]['date'],'cover':rows[y]['cover']} for y in years if y in rows])
    if args.spawning != 'none':
        try:
            if args.spawning=='databasin':
                geo=load_databasin(ROOT/'data')
                if geo is None: raise FileNotFoundError('Download Data Basin shapefile ZIP to data/spawning_grounds.zip first')
            else: geo=load_noaa(ROOT/'data'/'spawning_grounds_noaa.geojson')
            write_json(OUT/'spawning.geojson',geo)
            print(f'Spawning layer: {len(geo["features"])} features ({args.spawning})')
        except Exception as exc:
            print(f'Spawning layer FAILED: {exc}')
            failed.append('spawning')
    print(f'Website ready with {len(years)} years. Open docs/index.html with a local HTTP server.')
    if failed:
        print('Missing:',failed)
        sys.exit(1)

if __name__=='__main__':main()
