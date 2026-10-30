"""Pre-generate map geometry for many winter years; no ArcGIS conversion required.

Examples:
    python prepare_cache.py --years 2002 2014 2025
    python prepare_cache.py --all --workers 2
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from annual_max import annual_max_rows
from ice_cache import cached_map


def prep_one(year, peaks):
    features=cached_map(year,peaks[year]['date'])
    return year,len(features['features'])


def main():
    p=argparse.ArgumentParser(description='Download and cache NOAA annual-maximum ice cover layers')
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--all',action='store_true',help='Precache all available years')
    mode.add_argument('--years',type=int,nargs='+',help='Precache specific years')
    p.add_argument('--workers',type=int,default=2,help='Concurrent downloads, default 2 (max 3)')
    args=p.parse_args()
    peaks=annual_max_rows()
    years=sorted(peaks) if args.all else args.years
    bad=[y for y in years if y not in peaks]
    if bad: p.error(f'Years not in NOAA table: {bad}')
    count=0
    with ThreadPoolExecutor(max_workers=max(1,min(3,args.workers))) as pool:
        tasks={pool.submit(prep_one,y,peaks):y for y in years}
        for future in as_completed(tasks):
            year=tasks[future]
            try:
                y,n=future.result()
                count+=1
                print(f'OK {y}: {n:,} map cells cached')
            except Exception as e:
                print(f'FAILED {year}: {e}')
    print(f'{count}/{len(years)} winters prepared. Reopen Streamlit to use cached layers.')

if __name__=='__main__': main()
