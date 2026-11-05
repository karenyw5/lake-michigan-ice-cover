"""Disk cache of downsampled NOAA grids for rapid repeat visualization."""
from __future__ import annotations
import gzip
import json
import os
from pathlib import Path
from annual_max import HERE, ensure_netcdf
from netcdf_utils import grid_to_geojson, read_day

CACHE_DIR = HERE / 'cache'
DISPLAY_GRID_SIZE = 76  # ~3–5K grid polygons, much cheaper to render than full-resolution grids.


def cached_map(year: int, peak_date: str, cache_dir: Path = CACHE_DIR):
    """Load preprocessed GeoJSON; otherwise fetch one NOAA daily NetCDF and preprocess ONCE."""
    cache_dir = Path(cache_dir)
    target = cache_dir / f'{int(year)}.geojson.gz'
    if target.is_file():
        with gzip.open(target, 'rt', encoding='utf-8') as f:
            return json.load(f)
    nc_path = ensure_netcdf(year, peak_date)
    ice, lon, lat = read_day(nc_path, None)
    data = grid_to_geojson(ice, lon, lat, max_cells_across=DISPLAY_GRID_SIZE)
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.gz.tmp')
    try:
        with gzip.open(temporary, 'wt', encoding='utf-8', compresslevel=4) as f:
            json.dump(data, f, separators=(',', ':'))
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return data
