"""Diagnose a NOAA NetCDF's dimensions, variable names, and sample values."""
import sys
from pathlib import Path
import numpy as np
from netcdf_utils import open_nc, ice_variable, time_coord, read_day

if len(sys.argv) < 2:
    print('Usage: python inspect_netcdf.py data/20250221.nc')
    raise SystemExit(1)
file=Path(sys.argv[1])
with open_nc(file) as ds:
    print('FILE:', file.name)
    print('DIMENSIONS:', dict(ds.sizes))
    print('DATA VARIABLES:', {k:(str(v.dims),v.attrs.get('units','')) for k,v in ds.data_vars.items()})
    name=ice_variable(ds)
    print('DETECTED ICE VARIABLE:',name)
    print('DETECTED TIME DIMENSION:',time_coord(ds,name))
try:
    a,lon,lat=read_day(file,0)
    print('ICE GRID SHAPE:',a.shape,'VALID CELLS:',np.isfinite(a).sum())
    print('ICE RANGE:',f'{np.nanmin(a):.1f}–{np.nanmax(a):.1f}%' if np.isfinite(a).any() else 'no valid cells')
    print('LONGITUDE RANGE:',np.nanmin(lon),np.nanmax(lon))
    print('LATITUDE RANGE:',np.nanmin(lat),np.nanmax(lat))
    print('NetCDF decoded successfully.')
except Exception as e:
    print('Unable to map grid:',e)
    raise
