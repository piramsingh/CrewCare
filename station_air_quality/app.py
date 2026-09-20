"""NYC subway station conditions dashboard.

Pick a station; get four things:

    location  ·  platform PM2.5  ·  platform temperature  ·  platform humidity

The three platform figures are MODELLED, not measured. Live outdoor readings
come from Open-Meteo; `indoor.py` adds the PM2.5 the trains generate and
`thermal.py` solves the heat and moisture balances. Ventilation and service
level come from the station's own `structure` and `route_count` in
`datasets/nyc_subway_station_spine.csv`.

Run with:
    streamlit run station_air_quality/app.py
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pydeck as pdk
import streamlit as st

import charts
import indoor
import openmeteo as om
import thermal

REFRESH_CHOICES = {"1 hour": 1.0, "3 hours": 3.0, "6 hours": 6.0, "12 hours": 12.0}
DEFAULT_REFRESH = "3 hours"

WHO_PM25_GUIDELINE = 15.0   # ug/m3, 24-hour


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60 * 60 * 24, show_spinner="Loading station spine...")
def load_stations() -> pd.DataFrame:
    return om.load_stations()


@st.cache_data(show_spinner="Fetching conditions from Open-Meteo...")
def load_snapshot(ttl_hours: float, cache_buster: int) -> om.Snapshot:
    return om.fetch_snapshot(load_stations(), ttl_hours=ttl_hours, force=cache_buster > 0)


def theme_mode() -> str:
    try:
        return st.context.theme.type or "light"
    except Exception:
        return st.get_option("theme.base") or "light"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar(stations: pd.DataFrame) -> tuple[pd.Series, float]:
    with st.sidebar:
        st.subheader("Location")

        boroughs = ["All boroughs", *sorted(stations["borough"].dropna().unique())]
        borough = st.selectbox("Borough", boroughs, index=0)
        pool = stations if borough == "All boroughs" else stations[stations["borough"] == borough]

        previous = st.session_state.get("station_label")
        default = list(pool["label"]).index(previous) if previous in list(pool["label"]) else 0
        label = st.selectbox(
            "Subway station", list(pool["label"]), index=default,
            help="Type to search. Labels carry routes and borough because 117 stop "
                 "names repeat across lines.",
        )
        st.session_state["station_label"] = label
        station = pool[pool["label"] == label].iloc[0]

        st.divider()
        ttl_label = st.select_slider(
            "Re-fetch no more often than", options=list(REFRESH_CHOICES),
            value=DEFAULT_REFRESH,
            help="Between refreshes everything is served from cache, with no API calls.",
        )
        if st.button("Refresh now", width="stretch"):
            om.clear_cache()
            st.cache_data.clear()
            st.session_state["cache_buster"] = st.session_state.get("cache_buster", 0) + 1
            st.rerun()

    return station, REFRESH_CHOICES[ttl_label]


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------


def render_location(station: pd.Series, mode: str) -> None:
    ink = charts.palette(mode)
    st.title(station["stop_name"])
    st.caption(
        f"{station['daytime_routes']}  ·  {station['borough']}  ·  "
        f"{station['structure']}  ·  {station['ada_status']}  ·  "
        f"{station['lat']:.4f}, {station['lon']:.4f}"
    )
    st.pydeck_chart(
        pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(
                latitude=float(station["lat"]), longitude=float(station["lon"]),
                zoom=14, pitch=0,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=pd.DataFrame([{
                        "lat": float(station["lat"]), "lon": float(station["lon"]),
                        "name": station["stop_name"],
                    }]),
                    get_position=["lon", "lat"],
                    get_fill_color=[42, 120, 214, 210],
                    get_line_color=[17, 17, 17, 255] if mode == "light" else [255, 255, 255, 255],
                    stroked=True, line_width_min_pixels=2,
                    get_radius=60, radius_min_pixels=9, pickable=True,
                )
            ],
            tooltip={"html": "<b>{name}</b>"},
        ),
        height=260,
    )


def _card(column, *, title: str, value: str, unit: str, caption: str, accent: str,
          ink: dict) -> None:
    with column:
        st.markdown(
            f"""
            <div style="border-left:6px solid {accent};
                        background:{ink['forecast_band']};
                        border-radius:10px; padding:18px 20px;
                        min-height:150px;">
              <div style="font-size:12px; text-transform:uppercase; letter-spacing:.04em;
                          color:{ink['text_secondary']};">{title}</div>
              <div style="font-size:42px; font-weight:650; line-height:1.15;
                          color:{ink['text_primary']}; margin-top:6px;">
                {value}<span style="font-size:17px; font-weight:500;
                                    color:{ink['text_secondary']};"> {unit}</span>
              </div>
              <div style="font-size:12.5px; color:{ink['text_secondary']}; margin-top:8px;">
                {caption}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_conditions(
    station: pd.Series, values: dict, daily_means: list[float], mode: str
) -> None:
    ink = charts.palette(mode)
    source = indoor.subway_delta_c(station)
    climate = thermal.station_climate(
        station,
        t_out_f=values.get("temperature_2m"),
        rh_out=values.get("relative_humidity_2m"),
        dewpoint_out_f=values.get("dew_point_2m"),
        pressure_hpa=values.get("surface_pressure"),
        daily_means_f=daily_means,
    )

    outdoor_pm25 = values.get(indoor.PM25_KEY)
    platform_pm25 = indoor.platform_pm25(outdoor_pm25, source.delta_c)

    air, temp, humid = st.columns(3)

    if platform_pm25 is None:
        pm_value, pm_caption = "n/a", "No outdoor PM2.5 returned for this grid cell."
    else:
        pm_value = f"{platform_pm25:,.1f}"
        pm_caption = (
            f"Street {outdoor_pm25:,.1f} + {source.delta_c:,.1f} from the trains"
            f" · {platform_pm25 / WHO_PM25_GUIDELINE:.1f}× the WHO "
            f"24-hour guideline of {WHO_PM25_GUIDELINE:g}"
            if source.delta_c > 0
            else f"Open-air station — platform air is the street's, "
                 f"{platform_pm25 / WHO_PM25_GUIDELINE:.1f}× the WHO guideline"
        )
    _card(air, title="Air quality · PM2.5", value=pm_value, unit="µg/m³",
          caption=pm_caption, accent=ink["series"][0], ink=ink)

    _card(
        temp, title="Temperature", value=f"{climate.t_in_f:,.1f}", unit="°F",
        caption=(
            f"Street {climate.t_out_f:,.1f}°F · "
            f"{climate.delta_t_f:+,.1f}°F underground · "
            f"feels like {climate.heat_index_in_f:,.1f}°F"
            if climate.enclosed
            else f"Open-air station — same as the street, {climate.t_out_f:,.1f}°F"
        ),
        accent=ink["series"][1], ink=ink,
    )

    _card(
        humid, title="Humidity",
        value=f"{climate.rh_in:,.0f}", unit="%",
        caption=(
            f"{thermal.dewpoint_band(climate.dewpoint_in_f)} · dew point "
            f"{climate.dewpoint_in_f:,.0f}°F, carried down from the street "
            f"unchanged · feels like {climate.heat_index_in_f:,.0f}°F"
            if climate.enclosed
            else f"{thermal.dewpoint_band(climate.dewpoint_out_f)} · open-air "
                 f"station, same as the street"
        ),
        accent=ink["series"][2], ink=ink,
    )

    if climate.enclosed:
        st.caption(
            f"Modelled for an enclosed station at {climate.air_changes:g} air changes "
            f"per hour with {source.trains_per_hour:g} trains an hour, from this "
            f"station's `structure` and `route_count`. **Dew point is the "
            f"transferable quantity**: nothing underground dehumidifies the air, so "
            f"absolute moisture carries through from the street while relative "
            f"humidity falls out of the warmer platform temperature. Using outdoor RH "
            f"directly would overstate humidity down here by about "
            f"{climate.rh_out - climate.rh_in:.0f} points — the percentage above is "
            f"computed for the platform's own temperature, not copied from the "
            f"street. Wet-bulb "
            f"{climate.wet_bulb_in_f:.1f}°F, WBGT {climate.wbgt_in_c:.1f}°C — an "
            f"underestimate on a still platform, where the natural wet bulb runs "
            f"above the ventilated one."
        )


def render_footer(snapshot: om.Snapshot, ttl_hours: float, station: pd.Series) -> None:
    age = snapshot.age_seconds()
    fetched = snapshot.fetched_at.astimezone()
    remaining = max(0.0, ttl_hours * 3600 - age)
    st.divider()
    st.caption(
        f"Outdoor readings from [Open-Meteo](https://open-meteo.com) — fetched "
        f"{fetched:%b %-d, %-I:%M %p} ({_humanize(age)} ago), "
        f"{'from cache' if snapshot.from_cache else f'{snapshot.requests_made} live request(s)'}, "
        f"next refresh in {_humanize(remaining)}."
    )
    st.caption(
        "**The three platform figures are modelled estimates, not measurements.** "
        "No public per-station feed exists for the NYC subway. Outdoor air quality "
        "resolves to a ~11 km grid, and the platform models apply assumed emission "
        "factors, a standard platform volume and a ventilation rate inferred from "
        f"`structure` (here: {station['structure']}). Treat them as a planning prior."
    )


def _humanize(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s"
    minutes = seconds / 60
    return f"{int(minutes)} min" if minutes < 90 else f"{minutes / 60:.1f} h"


# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="NYC Subway Station Conditions", page_icon="\U0001f687", layout="wide"
    )
    mode = theme_mode()
    stations = load_stations()
    station, ttl_hours = render_sidebar(stations)

    try:
        snapshot = load_snapshot(ttl_hours, st.session_state.get("cache_buster", 0))
    except Exception as error:  # noqa: BLE001 - surface any API/network failure
        st.error(f"Could not reach Open-Meteo: {error}")
        st.stop()

    values = om.station_current(snapshot, station)
    daily_means = om.station_daily_means(snapshot, station)

    render_location(station, mode)
    render_conditions(station, values, daily_means, mode)
    render_footer(snapshot, ttl_hours, station)


if __name__ == "__main__":
    main()
