import io
import gzip
import json
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import shapefile
import numpy as np
import xarray as xr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ice_cache
from spawning_grounds import shapefile_zip_to_geojson, layer_data
from annual_max import annual_max_rows


def test_zip_input():
    with tempfile.TemporaryDirectory() as root:
        root=Path(root)
        stem=root/'spawning_sites'
        with shapefile.Writer(str(stem),shapeType=shapefile.POINT) as writer:
            writer.field('Place','C',size=50)
            writer.point(-86.8,45.1);writer.record('Northern Lake Michigan')
            writer.point(-120.1,45.1);writer.record('Not Lake Michigan')
        (root/'spawning_sites.prj').write_text('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]')
        zipped=root/'spawning_grounds.zip'
        with ZipFile(zipped,'w') as z:
            for extension in ['shp','shx','dbf','prj']:
                z.write(str(stem)+'.'+extension, 'subfolder/spawning_sites.'+extension)
        fc=shapefile_zip_to_geojson(zipped)
        assert len(fc['features'])==1
        pts,geo=layer_data(fc)
        assert len(pts)==1 and not geo['features']
        assert pts[0]['lon']==-86.8
        print('PASS Data Basin zipped shapefile and projection handling')


def test_cache():
    with tempfile.TemporaryDirectory() as root:
        root=Path(root)
        lat=np.linspace(42,46,15);lon=np.linspace(-88,-85,16)
        ds=xr.Dataset({'ice_concentration':(('latitude','longitude'),np.ones((15,16),dtype='f4')*40,{'units':'percent'})},
                      coords={'latitude':lat,'longitude':lon})
        nc=root/'20250221.nc'
        ds.to_netcdf(nc,engine='scipy')
        with patch('ice_cache.ensure_netcdf',return_value=nc):
            fc=ice_cache.cached_map(2025,'2025-02-21',cache_dir=root/'cache')
        assert len(fc['features'])>0
        p=root/'cache/2025.geojson.gz'
        assert p.exists()
        with patch('ice_cache.ensure_netcdf',side_effect=AssertionError('cache missed!')):
            fc2=ice_cache.cached_map(2025,'2025-02-21',cache_dir=root/'cache')
        assert fc==fc2
        print('PASS preprocessed map reused without NetCDF loading')

if __name__=='__main__':
    test_zip_input();test_cache();print('PASS metadata',len(annual_max_rows()),'years')
