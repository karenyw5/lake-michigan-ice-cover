# Lake Michigan Historical Ice Cover — GitHub Pages

Static, browser-only interactive map with one NOAA GLERL Lake Michigan annual-maximum date per year, timeline slider, optional historic spawning sites overlay, zoom/pan, and ice-concentration popups. **No Streamlit server** and **no pre-rendered maps**.

## 1. One-time data preparation (on Windows PowerShell)

```powershell
cd "C:\Users\karen\Documents\lake_michigan_github_pages"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build_data.py --years 2014 2025 --download
```

The first run downloads the NOAA daily NetCDF for Lake Michigan's peak date, calculates geographic ice-cell polygons, and writes compact `docs/data/2014.geojson` etc. **Check two years visually before processing the full record**. To generate the full timeline:

```powershell
.\.venv\Scripts\python.exe build_data.py --download
```

You can also reuse processed files from the previous Streamlit project: copy its `cache/*.geojson.gz` into this project's `cache/`, then run `build_data.py` **without** `--download`. This is much faster than reprocessing NetCDFs. Alternatively, copy previously downloaded NetCDFs into `data/YEAR/YYYYMMDD.nc`.

If a download fails, that year will be omitted from `years.json`. Re-run the command later for missing years.

## 2. Optional historic whitefish spawning sites

Data Basin dataset: https://databasin.org/datasets/d89059c26cda4f3db8dc70b2a8a09200/

Download its ZIP archive after signing in, place it at `data/spawning_grounds.zip`, then run:

```powershell
.\.venv\Scripts\python.exe build_data.py --years 2014 2025 --spawning databasin
```

This adds `docs/data/spawning.geojson`. To use a related, **different** NOAA layer instead, use `--spawning noaa` (requires internet). The app labels that distinction. Confirm any dataset license/attribution requirements before public reuse.

## 3. Test locally

```powershell
.\.venv\Scripts\python.exe -m http.server 8000 --directory docs
```

Open http://localhost:8000/ (do not double-click `index.html` — browsers restrict local file loading).

## 4. Publish on GitHub Pages

Your prepared GeoJSON maps in `docs/data/` **will be committed by `git add .`**. Check their combined size before committing:

```powershell
(Get-ChildItem docs\data -File | Measure-Object Length -Sum).Sum / 1MB
```

Then create an empty GitHub repository and push:

```powershell
git init
git branch -M main
git add .
git commit -m "Build static Lake Michigan ice-cover map"
git remote add origin https://github.com/YOUR_USERNAME/lake-michigan-ice.git
git push -u origin main
```

In GitHub **Settings → Pages → Build and deployment**, select **Deploy from a branch**, branch `main`, folder `/docs`, then Save. GitHub Pages will serve `docs/index.html` automatically.

Your page URL will resemble `https://YOUR_USERNAME.github.io/lake-michigan-ice/`.

**Data notice:** Each ice map is an instantaneous grid on the date NOAA reports Lake Michigan's annual maximum coverage. It does not show cumulative ice duration, biological outcomes, or a continuous annual maximum map per cell.
