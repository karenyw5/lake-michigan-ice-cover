"""NOAA GLERL Lake Michigan annual-maximum metadata and daily NetCDF retrieval.

Data metadata: https://www.glerl.noaa.gov/data/ice/glicd/dates_AMIC.txt
Daily NetCDF: https://www.glerl.noaa.gov/data/ice/glicd/netcdf/daily_data/YYYY/
"""
from __future__ import annotations

import csv
from datetime import datetime, date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://www.glerl.noaa.gov/data/ice/glicd/netcdf/daily_data"
HERE = Path(__file__).resolve().parent
CSV_FILE = HERE / "annual_max_michigan.csv"


def annual_max_rows(csv_file=CSV_FILE):
    """Year => {date, maximum_cover_percent}, strictly one Michigan peak per year."""
    with open(csv_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    output = {}
    for row in rows:
        year = int(row['year'])
        peak = date.fromisoformat(row['date'])
        coverage = float(row['maximum_cover_percent'])
        if year in output or peak.year != year or not 0 <= coverage <= 100:
            raise ValueError(f"Invalid Michigan annual maximum entry for {year}")
        output[year] = {'date':peak.isoformat(), 'cover':coverage}
    return dict(sorted(output.items()))


def parse_noaa_amics(text):
    """Read NOAA's original whitespace-separated dates_AMIC.txt, Michigan columns ONLY.

    The first numeric column is Superior; Michigan is tokens 3 (cover) and 4 (date).
    """
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6 or len(parts[0]) != 4 or not parts[0].isdigit():
            continue
        year = int(parts[0])
        try:
            coverage = float(parts[3])
            peak = datetime.strptime(f"{parts[4]}-{year}", "%b-%d-%Y").date()
        except (ValueError, IndexError) as e:
            raise ValueError(f"Unrecognized NOAA row for {year}: {line}") from e
        result[year] = {"date":peak.isoformat(), "cover":coverage}
    return result


def source_urls(year, date_iso):
    day = date_iso.replace('-', '')
    base = f'{BASE_URL}/{year}/{day}'
    return [base+'.nc', base+'i.nc']


def find_local(year, date_iso, folder=None):
    root = Path(folder) if folder is not None else HERE / 'data'
    for name in [date_iso.replace('-', '')+'.nc', date_iso.replace('-', '')+'i.nc']:
        for p in (root / str(year) / name, root / name):
            if p.is_file() and p.stat().st_size:
                return p
    return None


def ensure_netcdf(year, date_iso, folder=None, timeout=35):
    """Get ONLY the one daily NetCDF corresponding to Michigan's NOAA peak date.

    Returns path. Tries observed daily file, then temporal-interpolated version.
    File downloads are atomic and cached. Raises informative error if neither exists.
    """
    root = Path(folder) if folder is not None else HERE / 'data'
    existing = find_local(year, date_iso, root)
    if existing:
        return existing
    destination = root / str(year)
    destination.mkdir(parents=True, exist_ok=True)
    failures = []
    for url in source_urls(year, date_iso):
        target = destination / url.rsplit('/',1)[-1]
        temporary = target.with_suffix('.part')
        try:
            req = Request(url, headers={'User-Agent':'Whitefish-Ice-Timeline/1.1 (academic use)'})
            with urlopen(req, timeout=timeout) as response, open(temporary, 'wb') as out:
                # ASCII classic NetCDF or NetCDF4/HDF5; reject HTML/error pages.
                first = response.read(8)
                if not (first.startswith(b'CDF') or first.startswith(b'\x89HDF\r\n\x1a\n')):
                    raise ValueError('NOAA response did not contain a NetCDF file')
                out.write(first)
                while True:
                    chunk = response.read(1024*1024)
                    if not chunk: break
                    out.write(chunk)
            temporary.replace(target)
            return target
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
            failures.append(f'{url}: {exc}')
            temporary.unlink(missing_ok=True)
    raise RuntimeError('NOAA NetCDF unavailable for '+date_iso+'\n'+'\n'.join(failures))
