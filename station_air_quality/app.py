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
import complaints
import flood
import indoor
import openmeteo as om
import risk as risk_model
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


@st.cache_resource
def _seed_complaints_once() -> int:
    """Write the illustrative reports on first run of a fresh checkout.

    The store is deliberately untracked, so a clone starts empty; this gives it
    something to show. It is a no-op the moment any record exists, so a real
    submission is never overwritten.
    """
    return complaints.seed_demo_complaints()


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


def render_sidebar(stations: pd.DataFrame) -> tuple[pd.Series, float, str]:
    with st.sidebar:
        st.subheader("Location")

        boroughs = ["All boroughs", *sorted(stations["borough"].dropna().unique())]
        borough = st.selectbox("Borough", boroughs, index=boroughs.index("Manhattan"))
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

    return station, REFRESH_CHOICES[ttl_label], borough


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Scoring stations...")
def score_borough(borough: str, ttl_hours: float, cache_buster: int) -> pd.DataFrame:
    """Risk level and the three metrics for every station in a borough.

    Cached because it runs the full climate model once per station, and the
    result only changes when the underlying snapshot does.
    """
    stations = load_stations()
    pool = stations if borough == "All boroughs" else stations[stations["borough"] == borough]
    snapshot = load_snapshot(ttl_hours, cache_buster)
    report_counts = complaints.counts_by_station()

    rows = []
    for _, station in pool.iterrows():
        values = om.station_current(snapshot, station)
        if values.get("temperature_2m") is None:
            continue
        source = indoor.subway_delta_c(station)
        climate = thermal.station_climate(
            station,
            t_out_f=values.get("temperature_2m"),
            rh_out=values.get("relative_humidity_2m"),
            dewpoint_out_f=values.get("dew_point_2m"),
            pressure_hpa=values.get("surface_pressure"),
            daily_means_f=om.station_daily_means(snapshot, station),
        )
        platform_pm25 = indoor.platform_pm25(values.get(indoor.PM25_KEY), source.delta_c)
        flood_climate = flood.station_flood_climate(
            om.station_precipitation_series(snapshot, station),
            om.station_flood_series(snapshot, station),
            rh_in=climate.rh_in,
            enclosed=indoor.enclosure_for(station["structure"]).is_enclosed(),
        )
        assessed = risk_model.station_risk(
            platform_pm25, climate.heat_index_in_f,
            flood_climate.mold.level, flood_climate.mold.description,
        )
        rows.append({
            "station_id": station["gtfs_stop_id"],
            "reports": report_counts.get(station["gtfs_stop_id"], 0),
            "label": station["label"],
            "stop_name": station["stop_name"],
            "routes": station["daytime_routes"],
            "structure": station["structure"],
            "lat": float(station["lat"]),
            "lon": float(station["lon"]),
            "level": assessed.level,
            "level_name": assessed.name,
            "driver": assessed.driver,
            "mould": flood_climate.mold.level,
            "mould_why": flood_climate.mold.description,
            "hours_since_flood": (
                round(flood_climate.hours_since_exceedance)
                if flood_climate.hours_since_exceedance is not None else None
            ),
            "latest_precip_mm": flood_climate.latest_precip_mm,
            "river_available": flood_climate.river.available,
            "river_anomaly": (
                round(flood_climate.river.anomaly_pct)
                if flood_climate.river.anomaly_pct is not None else None
            ),
            "river_elevated": flood_climate.river.elevated,
            "color": assessed.color,
            "pm25": round(platform_pm25, 1) if platform_pm25 is not None else None,
            "temp_f": round(climate.t_in_f, 1),
            "feels_f": round(climate.heat_index_in_f, 1),
            "rh": round(climate.rh_in),
        })
    return pd.DataFrame(rows)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _flood_line(picked: dict) -> str:
    """One sentence on flooding for the clicked station.

    Pluvial first, because rainfall over the sewers is what actually floods a
    station; river discharge follows as labelled context, never merged in.
    """
    hours = picked.get("hours_since_flood")
    if hours is None:
        pluvial = (
            f"<b>No rainfall exceedance</b> in the last {om.PAST_DAYS + om.FORECAST_DAYS} "
            f"days — no hour crossed NYC DEP's "
            f"{flood.SEWER_CAPACITY_IN_PER_HR:g} in/hr sewer capacity."
        )
    elif hours < 48:
        pluvial = (
            f"<b>Rainfall exceeded sewer capacity {hours:.0f} h ago</b> — inside the "
            f"{flood.DRY_WINDOW_HOURS:.0f} h window in which drying prevents mould."
        )
    else:
        pluvial = (
            f"<b>Rainfall exceeded sewer capacity {hours:.0f} h ago</b> — past the "
            f"{flood.DRY_WINDOW_HOURS:.0f} h drying window."
        )

    if picked.get("river_available") and picked.get("river_anomaly") is not None:
        flag = " (elevated)" if picked.get("river_elevated") else ""
        river = (
            f" Nearby river discharge {picked['river_anomaly']:+.0f}% vs its "
            f"{om.FLOOD_PAST_DAYS}-day median{flag} — context only, not scored."
        )
    else:
        river = " No river resolved nearby for discharge context."

    why = picked.get("mould_why") or ""
    return f"{pluvial}{river}<br/><span style='opacity:.85;'>{why}</span>"


def render_map(scored: pd.DataFrame, station: pd.Series, borough: str, mode: str) -> None:
    """Stations coloured 1-5, click one for its three metrics."""
    ink = charts.palette(mode)
    if scored.empty:
        st.warning("No scored stations to map.")
        return

    st.subheader(f"{borough} · {len(scored)} stations")

    present = sorted(scored["level"].unique())
    legend = " &nbsp;&nbsp;&nbsp; ".join(
        f"<span style='display:inline-block;width:11px;height:11px;border-radius:50%;"
        f"background:{risk_model.LEVEL_COLORS[lv]};margin-right:6px;'></span>"
        f"<b>{lv}</b> {risk_model.LEVEL_NAMES[lv]}"
        for lv in present
    )
    st.markdown(
        f"<div style='font-size:12.5px;color:{ink['text_secondary']};margin-bottom:8px;'>"
        f"{legend} &nbsp;&nbsp;·&nbsp;&nbsp; click a station for its readings</div>",
        unsafe_allow_html=True,
    )

    plot = scored.copy()
    plot[["r", "g", "b"]] = plot["color"].map(_hex_to_rgb).apply(pd.Series)
    plot["selected"] = plot["label"] == station["label"]

    event = st.pydeck_chart(
        pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(
                latitude=float(plot["lat"].mean()),
                longitude=float(plot["lon"].mean()),
                zoom=11.2 if borough != "All boroughs" else 9.8,
                pitch=0,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    id="stations",
                    data=plot,
                    get_position=["lon", "lat"],
                    get_fill_color=["r", "g", "b", 220],
                    get_radius=120,
                    radius_min_pixels=6,
                    radius_max_pixels=14,
                    pickable=True,
                    auto_highlight=True,
                ),
                pdk.Layer(
                    "ScatterplotLayer",
                    id="selected",
                    data=plot[plot["selected"]],
                    get_position=["lon", "lat"],
                    get_fill_color=[0, 0, 0, 0],
                    get_line_color=[17, 17, 17, 255] if mode == "light" else [255, 255, 255, 255],
                    stroked=True, filled=False,
                    line_width_min_pixels=2.5,
                    get_radius=300, radius_min_pixels=13,
                ),
            ],
            tooltip={
                "html": "<b>{stop_name}</b> &middot; {routes}<br/>"
                        "Level {level} &middot; {level_name}<br/>"
                        "PM2.5 {pm25} &micro;g/m&sup3; &middot; {temp_f}&deg;F &middot; {rh}%"
                        "<br/>Mould risk {mould} &middot; {reports} worker report(s)",
            },
        ),
        height=470,
        selection_mode="single-object",
        on_select="rerun",
        key="risk_map",
    )

    # Streamlit returns the selection as a plain mapping, so index it rather
    # than reaching for an attribute; the layer's own `id` is the key.
    selection = event["selection"] if "selection" in event else {}
    rows = (selection.get("objects") or {}).get("stations") or []
    picked = rows[0] if rows else None

    if picked is None:
        st.caption("Hover for a summary; click a station to pin its readings below.")
        return

    st.markdown(
        f"""
        <div style="border-left:6px solid {risk_model.LEVEL_COLORS[picked['level']]};
                    background:{ink['forecast_band']}; border-radius:10px;
                    padding:16px 20px; margin:10px 0 4px;">
          <div style="font-size:16px; font-weight:650; color:{ink['text_primary']};">
            {picked['stop_name']}
            <span style="font-weight:400; font-size:13px; color:{ink['text_secondary']};">
              · {picked['routes']} · {picked['structure']}</span>
          </div>
          <div style="font-size:13px; font-weight:650; margin-top:4px;
                      color:{risk_model.LEVEL_COLORS[picked['level']]};">
            Level {picked['level']} · {picked['level_name']}
            <span style="font-weight:400; color:{ink['text_secondary']};">
              · driven by {picked['driver'].lower()}</span>
          </div>
          <div style="display:flex; gap:38px; margin-top:12px;">
            <div><div style="font-size:11px; text-transform:uppercase;
                 letter-spacing:.04em; color:{ink['text_secondary']};">PM2.5</div>
              <div style="font-size:24px; font-weight:650;
                 color:{ink['text_primary']};">{picked['pm25']}
                 <span style="font-size:13px; font-weight:500;
                 color:{ink['text_secondary']};">µg/m³</span></div></div>
            <div><div style="font-size:11px; text-transform:uppercase;
                 letter-spacing:.04em; color:{ink['text_secondary']};">Temperature</div>
              <div style="font-size:24px; font-weight:650;
                 color:{ink['text_primary']};">{picked['temp_f']}
                 <span style="font-size:13px; font-weight:500;
                 color:{ink['text_secondary']};">°F</span></div></div>
            <div><div style="font-size:11px; text-transform:uppercase;
                 letter-spacing:.04em; color:{ink['text_secondary']};">Humidity</div>
              <div style="font-size:24px; font-weight:650;
                 color:{ink['text_primary']};">{picked['rh']}
                 <span style="font-size:13px; font-weight:500;
                 color:{ink['text_secondary']};">%</span></div></div>
            <div><div style="font-size:11px; text-transform:uppercase;
                 letter-spacing:.04em; color:{ink['text_secondary']};">Feels like</div>
              <div style="font-size:24px; font-weight:650;
                 color:{ink['text_primary']};">{picked['feels_f']}
                 <span style="font-size:13px; font-weight:500;
                 color:{ink['text_secondary']};">°F</span></div></div>
            <div><div style="font-size:11px; text-transform:uppercase;
                 letter-spacing:.04em; color:{ink['text_secondary']};">Mould risk</div>
              <div style="font-size:24px; font-weight:650;
                 color:{risk_model.LEVEL_COLORS[risk_model.mould_level(picked['mould'])]};">
                 {picked['mould']}</div></div>
          </div>
          <div style="font-size:12.5px; color:{ink['text_secondary']};
                      margin-top:12px; padding-top:10px;
                      border-top:1px solid {ink['grid']};">
            {_flood_line(picked)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_complaints(picked["station_id"], picked["stop_name"], mode)


def render_complaints(station_id: str, stop_name: str, mode: str) -> None:
    """Anonymous worker reports for one station, plus a form to add one."""
    ink = charts.palette(mode)
    reports = complaints.for_station(station_id)

    st.markdown(f"**Worker reports · {stop_name}**")

    if not reports:
        st.caption("No reports filed for this station yet.")
    else:
        summary = " &nbsp;·&nbsp; ".join(
            f"{name} <b>{count}</b>" for name, count in complaints.category_summary(reports)
        )
        st.markdown(
            f"<div style='font-size:12.5px;color:{ink['text_secondary']};"
            f"margin:2px 0 10px;'>{len(reports)} report(s) &nbsp;·&nbsp; {summary}</div>",
            unsafe_allow_html=True,
        )

        if len(reports) < complaints.SMALL_COUNT_THRESHOLD:
            st.caption(
                "⚠️ Few reports at this station — with so few, details in a single "
                "report can identify who filed it. Read with that in mind."
            )

        for report in reports:
            tag = (
                f"<span style='font-size:10.5px;padding:1px 6px;border-radius:9px;"
                f"background:{ink['grid']};color:{ink['text_secondary']};"
                f"margin-left:7px;'>demo</span>" if report.demo else ""
            )
            st.markdown(
                f"""
                <div style="border-left:3px solid {ink['grid']};
                            padding:8px 0 8px 12px; margin-bottom:9px;">
                  <div style="font-size:12px;color:{ink['text_secondary']};">
                    {report.reported_on} &nbsp;·&nbsp; <b>{report.category}</b>
                    &nbsp;·&nbsp; {report.severity}{tag}
                  </div>
                  <div style="font-size:13.5px;color:{ink['text_primary']};
                              margin-top:3px;">{report.text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("File an anonymous report for this station"):
        st.caption(
            "Nothing about you is recorded — no name, no employee number, no "
            "device or session id, and the date is stored without a time so it "
            "cannot be matched against a roster. **Please leave identifying "
            "details out of the description**, including your tour, your title or "
            "anything that would single you out at a small location."
        )
        left, right = st.columns(2)
        category = left.selectbox("Category", complaints.CATEGORIES, key=f"cat_{station_id}")
        severity = right.selectbox("How is it affecting you?", complaints.SEVERITIES,
                                   key=f"sev_{station_id}")
        text = st.text_area(
            "What are you seeing?", key=f"txt_{station_id}", height=90,
            placeholder="Describe the condition and where in the station it is.",
        )
        if st.button("Submit report", key=f"sub_{station_id}"):
            if not text.strip():
                st.warning("Add a short description before submitting.")
            else:
                complaints.add(station_id, category, severity, text)
                st.success("Report filed anonymously.")
                st.rerun()


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
                        height:210px; display:flex; flex-direction:column;
                        box-sizing:border-box;">
              <div style="font-size:12px; text-transform:uppercase; letter-spacing:.04em;
                          color:{ink['text_secondary']};">{title}</div>
              <div style="font-size:42px; font-weight:650; line-height:1.15;
                          color:{ink['text_primary']}; margin-top:6px;">
                {value}<span style="font-size:17px; font-weight:500;
                                    color:{ink['text_secondary']};"> {unit}</span>
              </div>
              <div style="font-size:12.5px; color:{ink['text_secondary']}; margin-top:8px;
                          flex:1; min-height:0; overflow-y:auto;">
                {caption}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_conditions(
    station: pd.Series,
    values: dict,
    daily_means: list[float],
    snapshot: om.Snapshot,
    mode: str,
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

    precip_hourly = om.station_precipitation_series(snapshot, station)
    flood_daily = om.station_flood_series(snapshot, station)
    flood_climate = flood.station_flood_climate(
        precip_hourly, flood_daily, rh_in=climate.rh_in,
        enclosed=indoor.enclosure_for(station["structure"]).is_enclosed(),
    )

    assessed = risk_model.station_risk(
        platform_pm25, climate.heat_index_in_f,
        flood_climate.mold.level, flood_climate.mold.description,
    )
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:18px;
                    border-left:6px solid {assessed.color};
                    background:{ink['forecast_band']};
                    border-radius:10px; padding:16px 20px; margin:0 0 16px;">
          <div style="font-size:40px; font-weight:650; line-height:1;
                      color:{assessed.color};">{assessed.level}</div>
          <div>
            <div style="font-size:15px; font-weight:650; color:{ink['text_primary']};">
              {assessed.name} &nbsp;<span style="font-weight:400;
              color:{ink['text_secondary']};">· level {assessed.level} of 5 ·
              driven by {assessed.driver.lower()}</span>
            </div>
            <div style="font-size:12.5px; color:{ink['text_secondary']}; margin-top:3px;">
              {' &nbsp;·&nbsp; '.join(assessed.reasons)}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    air, temp, humid, flood_col = st.columns(4)

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

    mold_caption = flood_climate.mold.description
    if flood_climate.river.available and flood_climate.river.anomaly_pct is not None:
        mold_caption += (
            f" · Nearby river discharge {flood_climate.river.anomaly_pct:+.0f}% vs its "
            f"{om.FLOOD_PAST_DAYS}-day median"
            f"{' (elevated)' if flood_climate.river.elevated else ''} — context only, "
            "not part of the score."
        )
    else:
        mold_caption += " · No nearby river resolved for discharge context."

    _card(
        flood_col, title="Flood & mould risk", value=flood_climate.mold.level, unit="",
        caption=mold_caption, accent=ink["series"][3], ink=ink,
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


def render_worker(station: pd.Series, values: dict, daily_means: list[float],
                  snapshot: om.Snapshot, mode: str) -> None:
    """Precautions for the worker assigned here, given a vulnerability profile."""
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
    flood_climate = flood.station_flood_climate(
        om.station_precipitation_series(snapshot, station),
        om.station_flood_series(snapshot, station),
        rh_in=climate.rh_in,
        enclosed=indoor.enclosure_for(station["structure"]).is_enclosed(),
    )
    assessed = risk_model.station_risk(
        indoor.platform_pm25(values.get(indoor.PM25_KEY), source.delta_c),
        climate.heat_index_in_f,
        flood_climate.mold.level, flood_climate.mold.description,
    )

    st.divider()
    st.subheader("Worker precautions")
    st.caption(
        "Tick what applies to the worker assigned here. These are workplace "
        "precautions of the kind a safety programme issues — not medical advice, "
        "and not a basis for clearing a station as safe."
    )

    one, two, three = st.columns(3)
    with one:
        respiratory = st.checkbox("Asthma, COPD or other obstructive condition")
        cardiovascular = st.checkbox("Cardiovascular condition")
    with two:
        medication = st.checkbox(
            "Takes heat-sensitising medication",
            help="Diuretics, beta blockers, anticholinergics and antipsychotics, "
                 "among others, impair the body's ability to shed heat.",
        )
        overnight = st.checkbox("Overnight tour")
    with three:
        shift_hours = st.number_input("Tour length (hours)", 1.0, 16.0, 8.0, step=0.5)

    profile = risk_model.WorkerProfile(
        respiratory_condition=respiratory,
        cardiovascular_condition=cardiovascular,
        heat_sensitising_medication=medication,
        shift_hours=shift_hours,
        overnight_tour=overnight,
    )
    result = risk_model.worker_risk(assessed, profile)

    uplift = (
        f" — raised from the station's level {assessed.level} for this worker"
        if result.uplift else ""
    )
    st.markdown(
        f"""
        <div style="border-left:6px solid {result.color};
                    background:{ink['forecast_band']};
                    border-radius:10px; padding:14px 18px; margin:8px 0 14px;">
          <span style="font-size:15px; font-weight:650; color:{result.color};">
            Level {result.level} · {result.name}</span>
          <span style="font-size:13px; color:{ink['text_secondary']};">{uplift}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


    for modifier in result.modifiers:
        st.caption(f"• {modifier}")

    st.markdown("**Precautions for this shift**")
    for item in result.precautions:
        st.markdown(f"- {item}")

    for note in result.notes:
        st.info(note, icon="🌙")


def render_footer(snapshot: om.Snapshot, ttl_hours: float, station: pd.Series) -> None:
    age = snapshot.age_seconds()
    fetched = snapshot.fetched_at.astimezone()
    remaining = max(0.0, ttl_hours * 3600 - age)
    st.divider()
    st.caption(
        f"Outdoor readings from [Open-Meteo](https://open-meteo.com) — fetched "
        f"{_format_fetched(fetched)} ({_humanize(age)} ago), "
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
    st.caption(
        "**Flood & mould risk is a threshold indicator, not a forecast.** Pluvial "
        f"risk flags hours precipitation exceeds NYC DEP's {flood.SEWER_CAPACITY_IN_PER_HR:g} "
        "in/hr storm-sewer design capacity; mould risk applies EPA/ASHRAE/CDC humidity "
        "and drying-window thresholds, not a subway-specific study. River discharge "
        "(GloFAS) is separate context only — a fluvial signal, largely uninformative "
        "for stations away from a mapped river."
    )


def _format_fetched(moment: datetime) -> str:
    """Cross-platform equivalent of '%b %-d, %-I:%M %p'.

    %-d and %-I (no leading zero) are glibc/BSD strftime extensions and raise
    ValueError on Windows' C runtime, so this is built by hand instead.
    """
    hour12 = moment.hour % 12 or 12
    return f"{moment:%b} {moment.day}, {hour12}:{moment:%M %p}"


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
    _seed_complaints_once()
    stations = load_stations()
    station, ttl_hours, borough = render_sidebar(stations)

    try:
        snapshot = load_snapshot(ttl_hours, st.session_state.get("cache_buster", 0))
    except Exception as error:  # noqa: BLE001 - surface any API/network failure
        st.error(f"Could not reach Open-Meteo: {error}")
        st.stop()

    values = om.station_current(snapshot, station)
    daily_means = om.station_daily_means(snapshot, station)

    scored = score_borough(borough, ttl_hours, st.session_state.get("cache_buster", 0))
    render_map(scored, station, borough, mode)
    st.divider()

    render_location(station, mode)
    render_conditions(station, values, daily_means, snapshot, mode)
    render_worker(station, values, daily_means, snapshot, mode)
    render_footer(snapshot, ttl_hours, station)


if __name__ == "__main__":
    main()
