"""Lake Michigan annual maximum ice concentration with historic spawning overlay."""
from datetime import date
import streamlit as st
import pydeck as pdk

from annual_max import annual_max_rows
from ice_cache import cached_map
from spawning_grounds import DATABASIN_URL, find_databasin_data, load_databasin, load_noaa, layer_data

peaks=annual_max_rows()
years=list(peaks)
# Pre-processing: each year is cached on disk for near-immediate re-opening.
year=st.select_slider('Year',options=years,value=2025 if 2025 in peaks else years[-1])
peak=peaks[year]
day=date.fromisoformat(peak['date'])
st.markdown(f"**Lake Michigan maximum:** {peak['cover']:.1f}% &nbsp;&nbsp; **Date:** {day:%B} {day.day}, {day.year}")

show_sites=st.toggle('Show historic lake whitefish spawning locations',value=True)

@st.cache_data(show_spinner=False,max_entries=18)
def ice_features(year, peak_date):
    return cached_map(year,peak_date)

@st.cache_data(show_spinner=False,ttl=86400)
def spawning_data(file_fingerprint):
    local=load_databasin()
    if local is not None:
        return layer_data(local),'Data Basin — historic lake whitefish spawning locations (1982 atlas)'
    # NOAA's related historical site layer is an alternative, not the identical Data Basin asset.
    return layer_data(load_noaa()),'NOAA / U-M / Michigan DNR — related historic spawning-site layer'

try:
    with st.spinner(f'Loading {year} maximum ice cover…'):
        ice=ice_features(year,peak['date'])
except Exception as exc:
    st.error(f"Couldn't load NOAA NetCDF for {peak['date']}. Try the offline cache command in README.md.")
    st.code(str(exc))
    st.stop()

layers=[pdk.Layer('GeoJsonLayer',data=ice,filled=True,stroked=False,
                  get_fill_color='properties.color',pickable=True,auto_highlight=True)]
spawning_source=''
if show_sites:
    data_file=find_databasin_data()
    fingerprint=(str(data_file),data_file.stat().st_mtime_ns) if data_file else ('noaa',)
    try:
        (points,shapes),spawning_source=spawning_data(fingerprint)
        if shapes['features']:
            layers.append(pdk.Layer('GeoJsonLayer',data=shapes,filled=True,
                                    get_fill_color=[244,126,55,60],stroked=True,
                                    get_line_color=[238,91,31,240],line_width_min_pixels=2,pickable=True))
        if points:
            layers.append(pdk.Layer('ScatterplotLayer',data=points,get_position='[lon,lat]',
                                    get_radius=1900,radius_min_pixels=4,radius_max_pixels=10,
                                    get_fill_color=[245,119,37,235],get_line_color=[255,255,255,240],
                                    stroked=True,line_width_min_pixels=1,pickable=True))
    except Exception as exc:
        st.warning('Spawning sites could not be loaded. Ice cover is still available. '+str(exc))

view=pdk.ViewState(latitude=43.95,longitude=-86.65,zoom=5.65,pitch=0)
deck=pdk.Deck(layers=layers,initial_view_state=view,
              map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
              tooltip={'html':'{label}', 'style':{'fontSize':'13px'}})
# Stable widget key instead of changing on every year; less client-side map recreation.
st.pydeck_chart(deck,height=650,use_container_width=True,key='ice-cover-map')
st.markdown("**Ice concentration:** "
            "<span style='color:#b8e2f7'>■</span> 1–20% &nbsp; "
            "<span style='color:#7dc1e7'>■</span> 21–40% &nbsp; "
            "<span style='color:#4695cf'>■</span> 41–60% &nbsp; "
            "<span style='color:#1667a6'>■</span> 61–80% &nbsp; "
            "<span style='color:#0b3771'>■</span> 81–100% &nbsp; "
            "<span style='color:#f57725'>●</span> Historic whitefish spawning sites",
            unsafe_allow_html=True)
if show_sites and spawning_source:
    st.caption('Spawning overlay: '+spawning_source+'. These are historical/approximate locations, not current verified habitat.')
    if find_databasin_data() is None:
        st.caption('For the exact Data Basin dataset, download its Zip Archive and save it as '
                   '`data/spawning_grounds.zip` in this project. The app will then use those features instead of the NOAA alternative.')
st.caption('Ice: NOAA GLERL annual maximum for Lake Michigan (each year shows the daily grid on that maximum date). '
           'Grid display is downsampled for speed. After a year is loaded once, its processed map is saved locally for faster reuse.')
