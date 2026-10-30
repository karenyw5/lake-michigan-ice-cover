"""Read gridded NOAA GLERL ice-concentration NetCDFs and prepare map vector cells.

Accepts single-day files (YYYYMMDD.nc, YYYYMMDDi.nc) and multi-day yearly files.
Uses xarray for lazy opening and reads one day at a time.
"""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import math
import re

import numpy as np
import pandas as pd
import xarray as xr

# Approximate rectangular cutout. Spatial data, not a boundary or lake mask.
BBOX = (-88.6, 41.45, -84.6, 46.30)  # left lon, bottom lat, right lon, top lat
PREFERRED = ("ice_concentration", "ice_conc", "iceconc", "concentration",
             "ice_coverage", "ice_cover", "ice", "sic", "icec")
LAT_NAMES = ("latitude", "lat", "nav_lat", "xlat", "gridlat")
LON_NAMES = ("longitude", "lon", "nav_lon", "xlong", "gridlon")
TIME_NAMES = ("time", "date", "day", "valid_time")


def open_nc(path):
    # Engines in requirements: h5netcdf/netcdf4 cover NetCDF4 and classic files.
    # Explicitly disabling decoded mask scaling isn't needed with CF-compliant files.
    return xr.open_dataset(path, decode_times=True, mask_and_scale=True)


def ice_variable(ds):
    for name in PREFERRED:
        match = next((k for k in ds.data_vars if k.lower() == name), None)
        if match is not None and ds[match].ndim >= 2:
            return match
    matches = [k for k, v in ds.data_vars.items()
               if v.ndim >= 2 and np.issubdtype(v.dtype, np.number)
               and ('ice' in k.lower() or 'concen' in k.lower())]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return matches[0]
    raise ValueError(f"Ice concentration variable not recognized. Available variables: {list(ds.data_vars)}")


def time_coord(ds, var):
    for dim in ds[var].dims:
        if dim.lower() in TIME_NAMES:
            return dim
        if dim in ds.coords:
            coord = ds.coords[dim]
            if coord.ndim == 1 and ('since' in str(coord.attrs.get('units', '')).lower()
                                     or np.issubdtype(coord.dtype, np.datetime64)):
                return dim
    return None


def filename_date(path):
    name = Path(path).stem
    match = re.search(r'(?:^|\D)((?:19|20)\d{6})(?:i)?(?:\D|$)', name)
    if match:
        return pd.Timestamp(match.group(1)).date().isoformat()
    return None


def entries_for_file(path):
    path = Path(path)
    with open_nc(path) as ds:
        var = ice_variable(ds)
        td = time_coord(ds, var)
        if td is None:
            found = filename_date(path)
            if not found:
                raise ValueError(f"No time coordinate or YYYYMMDD filename: {path.name}")
            return [(found, str(path), None)]
        if td not in ds.coords:
            raise ValueError(f"Temporal dimension {td} has no coordinate in {path.name}")
        timestamps = pd.to_datetime(ds[td].values, errors='raise')
        dates = [pd.Timestamp(ts).date().isoformat() for ts in np.atleast_1d(timestamps)]
        return [(d, str(path), i) for i, d in enumerate(dates)]


def catalog(folder):
    paths = sorted(Path(folder).rglob('*.nc'))
    entries, errors = [], []
    for p in paths:
        try:
            entries.extend(entries_for_file(p))
        except Exception as e:
            errors.append(f"{p.name}: {e}")
    # Resolve duplicate date from overlapping daily and annual files: prefer daily.
    by_day = {}
    for x in entries:
        old = by_day.get(x[0])
        if old is None or (x[2] is None and old[2] is not None):
            by_day[x[0]] = x
    return sorted(by_day.values()), errors


def _coordinate(ds, names):
    for n in names:
        found = next((key for key in ds.variables if key.lower() == n), None)
        if found is not None:
            return ds[found]
    return None


def _coords(ds, da):
    spatial_dims = da.dims[-2:]
    ny, nx = da.shape[-2:]
    lat = _coordinate(ds, LAT_NAMES)
    lon = _coordinate(ds, LON_NAMES)
    if lat is not None and lon is not None:
        if lat.ndim == lon.ndim == 1:
            a, b = np.asarray(lat.values, float), np.asarray(lon.values, float)
            if len(a) == ny and len(b) == nx:
                return np.meshgrid(((b+180)%360)-180, a)
            if len(b) == ny and len(a) == nx:
                # Grid axes are swapped: lon indexed rows, lat columns.
                # Fallback makes properly shaped arrays.
                return np.broadcast_to(((b[:, None]+180)%360)-180, (ny, nx)), np.broadcast_to(a[None, :], (ny, nx))
        if lat.ndim == lon.ndim == 2:
            a, b = lat.transpose(*spatial_dims).values, lon.transpose(*spatial_dims).values
            if a.shape == (ny, nx):
                return ((np.asarray(b, float)+180)%360)-180, np.asarray(a, float)
    # CF projected coordinates. Need discover CRS from grid_mapping variable.
    crs_attrs = {}
    mapping = da.attrs.get('grid_mapping')
    if mapping and mapping in ds:
        crs_attrs = ds[mapping].attrs
    if not crs_attrs and 'spatial_ref' in ds:
        crs_attrs = ds['spatial_ref'].attrs
    if not crs_attrs:
        raise ValueError("Latitude/longitude coordinates not found; CF grid_mapping CRS also unavailable")
    from pyproj import CRS, Transformer
    crs = (CRS.from_wkt(crs_attrs['spatial_ref']) if crs_attrs.get('spatial_ref')
           else CRS.from_cf(crs_attrs))
    xx = np.asarray(ds[spatial_dims[-1]].values, float)
    yy = np.asarray(ds[spatial_dims[-2]].values, float)
    x2, y2 = np.meshgrid(xx, yy)
    lon2, lat2 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(x2, y2)
    return ((lon2 + 180) % 360) - 180, lat2


def read_day(path, index):
    """Return 2-D ice percentages and lon/lat grid arrays for one time slice."""
    with open_nc(path) as ds:
        name = ice_variable(ds)
        da = ds[name]
        td = time_coord(ds, name)
        if td is not None:
            da = da.isel({td: int(index) if index is not None else 0})
        # Remove singleton non-spatial dims; avoid silently flattening multiple levels.
        da = da.squeeze(drop=True)
        if da.ndim != 2:
            raise ValueError(f"Expected 2-D ice grid after selecting time, got {da.dims}")
        lon, lat = _coords(ds, da)
        arr = np.asarray(da.values, np.float32)
        units = str(da.attrs.get('units','')).lower().strip()
        valid = np.isfinite(arr) & (arr >= 0)
        vmax = float(np.max(arr[valid])) if valid.any() else 0
        # Only convert 0–1 when explicitly documented as fractional/1.
        if units in ('1', 'fraction', 'proportion', '0-1', '0 to 1'):
            arr = arr * 100
        elif vmax > 0 and vmax <= 1 and units not in ('%', 'percent', 'percentage'):
            raise ValueError("Ice values only range 0–1 and units are missing; cannot infer percent versus fraction")
        arr[~np.isfinite(arr) | (arr < 0) | (arr > 100)] = np.nan
        return arr, lon, lat


def ice_rgba(value):
    # Pale blues to navy. Transparent for 0 / missing; underlying basemap indicates water.
    colors = [(0, 0, 0, 0), (184, 226, 247, 217), (125, 193, 231, 225),
              (70, 149, 207, 235), (22, 103, 166, 240), (11, 55, 113, 247)]
    if value <= 0:
        return colors[0]
    return colors[min(5, math.ceil(value / 20))]


def _bilinear(a, r, c):
    nr, nc = a.shape
    r = np.clip(r, 0, nr - 1)
    c = np.clip(c, 0, nc - 1)
    r0, c0 = int(math.floor(r)), int(math.floor(c))
    r1, c1 = min(r0+1,nr-1), min(c0+1,nc-1)
    dr, dc = r-r0, c-c0
    return (a[r0,c0]*(1-dr)*(1-dc)+a[r1,c0]*dr*(1-dc)
            +a[r0,c1]*(1-dr)*dc+a[r1,c1]*dr*dc)


def grid_to_geojson(arr, lon, lat, max_cells_across=92):
    """Aggregate numeric cells into clickable colored geographic polygons.

    Does NOT generate or use NOAA map images, shapefiles, or interpolated maps.
    Weighted block means may smooth fine detail: display labeled as downsampled.
    """
    if arr.shape != lon.shape or arr.shape != lat.shape:
        raise ValueError('Coordinate grid and ice grid must have matching dimensions')
    west, south, east, north = BBOX
    spatial = np.isfinite(lon) & np.isfinite(lat) & (lon>=west) & (lon<=east) & (lat>=south) & (lat<=north)
    if not spatial.any():
        raise ValueError('No coordinate cells found near Lake Michigan: check grid projection')
    rows, cols = np.where(spatial)
    rmin, rmax = rows.min(), rows.max() + 1
    cmin, cmax = cols.min(), cols.max() + 1
    # Use about 92 across the longest spatial axis, keeping geometry manageable.
    step = max(1, math.ceil(max(rmax-rmin, cmax-cmin)/max_cells_across))
    feats=[]
    for r in range(rmin, rmax, step):
        r2 = min(r+step, rmax)
        for c in range(cmin,cmax,step):
            c2 = min(c+step,cmax)
            values = arr[r:r2,c:c2]
            inside = spatial[r:r2,c:c2]
            good = inside & np.isfinite(values)
            if not good.any():
                continue  # land and missing cells
            v = float(values[good].mean())
            if v < 0.5:
                continue  # zero/trace ice: transparent, not mistaken for land
            # Corners in grid space with half-cell offsets to avoid point-like polygons.
            corner_index = [(r-0.5,c-0.5),(r-0.5,c2-0.5),(r2-0.5,c2-0.5),(r2-0.5,c-0.5)]
            ring = [[float(_bilinear(lon, ri, ci)), float(_bilinear(lat, ri, ci))]
                    for ri, ci in corner_index]
            ring.append(ring[0])
            if not np.isfinite(np.asarray(ring)).all():
                continue
            feats.append({"type":"Feature","properties":{"concentration":round(v,1),
                      "color":list(ice_rgba(v)),"label":f"{v:.1f}% ice"},
                      "geometry":{"type":"Polygon","coordinates":[ring]}})
    return {"type":"FeatureCollection","features":feats}
