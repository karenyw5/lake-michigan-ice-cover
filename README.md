# Lake Michigan annual-maximum ice-cover map (fast version)

An interactive map/timeline only: select a year to see the NOAA NetCDF ice concentration on **Lake Michigan's** annual-maximum date. Toggle **historic whitefish spawning sites** on/off. No AGOL, GIS processing, or pre-rendered images.

## Run in Windows PowerShell

Unzip into a **new folder**. The ZIP has `app.py` right at its top level.

```powershell
cd "C:\Users\karen\Documents\lake_michigan_ice_fast"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Or use an existing Python environment and run `streamlit run app.py` from this folder.

## How to make year switching fast

A year's **first** visit may take longer because the app downloads its ~2.4 MB NOAA daily `.nc` and converts the grid into simplified map polygons. Then the app caches a small compressed `cache/<year>.geojson.gz`. When you return to that year, it loads the cached map.

To prepare years **before** opening Streamlit:

```powershell
.\.venv\Scripts\python.exe prepare_cache.py --years 2002 2014 2025
```

To prepare **all** years in the NOAA table:

```powershell
.\.venv\Scripts\python.exe prepare_cache.py --all --workers 2
```

This is a one-time preprocessing command. It runs on your own computer, downloads one NOAA NetCDF per year, and prepares small local GeoJSON caches. The NOAA daily file and the processed map are retained on disk. You'll need internet and enough disk space; NOAA may throttle downloads. If any year fails, re-run the command—it skips years that are already cached. The app itself only downloads a year when first selected if you haven't pre-cached it.

## Historic whitefish spawning sites

The app attempts to show a related public NOAA GIS service by default (originally derived from the Great Lakes spawning atlas, with some 2011 updates). **It is not the exact Data Basin layer requested.** NOAA's service data will be cached locally if reachable.

To display the **exact historic Data Basin layer**:

1. Sign in to [Data Basin](https://databasin.org/datasets/d89059c26cda4f3db8dc70b2a8a09200/) and download the dataset as a **Zip Archive** (not an `.lpk` layer package).
2. Place the ZIP inside this app's `data/` directory and rename it to `spawning_grounds.zip`.
3. Refresh Streamlit. The app automatically reads geographic shapefile geometries from inside the ZIP (no ArcGIS Pro conversion).

Alternative: export that layer as GeoJSON, save to `data/spawning_grounds.geojson`.

Historical sites in either layer should not be interpreted as precise, currently confirmed spawning areas. NOAA's related locations are described as approximate (at best one arcminute).

## Sources

- NOAA GLERL annual peak dates: https://www.glerl.noaa.gov/data/ice/glicd/dates_AMIC.txt
- NOAA GLERL daily NetCDFs: https://www.glerl.noaa.gov/data/ice/glicd/netcdf/daily_data/
- Data Basin historic Lake Michigan whitefish spawning sites (2011 upload, Goodyear Atlas 1982): https://databasin.org/datasets/d89059c26cda4f3db8dc70b2a8a09200/
- NOAA's related historical spawning and nursery points (NOAA/U-M/Michigan DNR): https://gis.ngdc.noaa.gov/arcgis/rest/services/nccos/BiogeographicAssessments_NCCOS_LakeMichigan/MapServer/32

## Testing caveat

This app's core NetCDF pipeline was previously tested using synthetic NetCDF fixtures only. The environment used to package this version could not download live NOAA or Data Basin files; live-file compatibility and NOAA service retrieval should be verified when you run it locally.
