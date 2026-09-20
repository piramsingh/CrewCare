"""Altair chart builders and the palette they draw from.

Palette values are the validated defaults from the data-viz reference palette:
categorical slots in fixed order (never cycled), one hue per series, recessive
chrome, and dark-mode steps chosen for the dark surface rather than flipped.

Deliberately absent: any dual-axis chart. Metrics with different units get
their own chart -- PM2.5 and PM10 share one only because they share
micrograms per cubic metre.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from openmeteo import AQI_CATEGORIES, METRICS_BY_KEY, Metric

# Categorical slots, assigned in fixed order.
SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500"]

THEME = {
    "light": {
        "surface": "#fcfcfb",
        "text_primary": "#0b0b0b",
        "text_secondary": "#52514e",
        "text_muted": "#7a7973",
        "grid": "#e6e5e0",
        "series": SERIES_LIGHT,
        "forecast_band": "#f0efec",
    },
    "dark": {
        "surface": "#1a1a19",
        "text_primary": "#ffffff",
        "text_secondary": "#c3c2b7",
        "text_muted": "#8a8980",
        "grid": "#33332f",
        "series": SERIES_DARK,
        "forecast_band": "#242422",
    },
}


def palette(mode: str) -> dict:
    return THEME.get(mode, THEME["light"])


def _base_config(chart: alt.Chart, mode: str) -> alt.Chart:
    ink = palette(mode)
    return (
        chart.configure_view(stroke=None)
        .configure_axis(
            domain=False,
            tickColor=ink["grid"],
            gridColor=ink["grid"],
            gridOpacity=0.7,
            labelColor=ink["text_secondary"],
            titleColor=ink["text_secondary"],
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
            labelPadding=6,
        )
        .configure_legend(
            labelColor=ink["text_secondary"],
            titleColor=ink["text_secondary"],
            labelFontSize=11,
            titleFontSize=11,
            symbolStrokeWidth=3,
            orient="top",
            direction="horizontal",
            title=None,
        )
        .configure_title(color=ink["text_primary"], fontSize=13, anchor="start", dy=-4)
        .properties(background=ink["surface"])
    )


def _split_at_now(
    frame: pd.DataFrame, now: pd.Timestamp, group: list[str] | None = None
) -> pd.DataFrame:
    """Tag each point observed/forecast, duplicating the boundary so lines join."""
    group = group or ["metric"]
    frame = frame.copy()
    frame["phase"] = frame["time"].map(lambda t: "Observed" if t <= now else "Forecast")

    # Without this, the solid and dashed lines leave a one-hour gap at `now`.
    boundary = frame[frame["time"] <= now]
    if not boundary.empty:
        bridge = (
            boundary.sort_values("time")
            .groupby(group, as_index=False)
            .tail(1)
            .assign(phase="Forecast")
        )
        frame = pd.concat([frame, bridge], ignore_index=True)
    return frame.sort_values([*group, "phase", "time"])


def _now_rule(now: pd.Timestamp, mode: str) -> alt.Chart:
    ink = palette(mode)
    marker = pd.DataFrame({"time": [now]})
    rule = (
        alt.Chart(marker)
        .mark_rule(color=ink["text_muted"], strokeWidth=1, strokeDash=[3, 3])
        .encode(x="time:T")
    )
    label = (
        alt.Chart(marker)
        .mark_text(
            text="now", align="left", dx=4, dy=-4, baseline="top",
            color=ink["text_muted"], fontSize=10,
        )
        .encode(x="time:T", y=alt.value(0))
    )
    return rule + label


def hourly_chart(
    frame: pd.DataFrame,
    metric_keys: list[str],
    *,
    now: pd.Timestamp,
    mode: str = "light",
    height: int = 260,
    show_aqi_bands: bool = False,
) -> alt.Chart:
    """Hourly line chart for one or more metrics that share a unit.

    Observed hours are solid, forecast hours dashed. With two or more metrics a
    legend is always present, so identity never rests on color alone.
    """
    ink = palette(mode)
    data = frame[frame["metric"].isin(metric_keys)]
    if data.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()

    metrics = [METRICS_BY_KEY[k] for k in metric_keys]
    unit = metrics[0].unit
    axis_title = unit if unit else metrics[0].label

    data = _split_at_now(data, now)
    hover = alt.selection_point(
        fields=["time"], nearest=True, on="pointerover", empty=False, clear="pointerout"
    )

    color = (
        alt.Color(
            "label:N",
            scale=alt.Scale(
                domain=[m.label for m in metrics],
                range=ink["series"][: len(metrics)],
            ),
            legend=alt.Legend(title=None) if len(metrics) > 1 else None,
        )
        if len(metrics) > 1
        else alt.value(ink["series"][0])
    )

    x = alt.X(
        "time:T",
        title=None,
        axis=alt.Axis(grid=False, format="%a %-I%p", tickCount=7),
    )
    y = alt.Y(
        "value:Q",
        title=axis_title,
        scale=alt.Scale(zero=False, nice=True),
        axis=alt.Axis(grid=True, tickCount=5),
    )

    layers: list[alt.Chart] = []

    if show_aqi_bands:
        # AQI category ceilings, as reference lines under the data. Only the
        # ones the data actually approaches are drawn: an out-of-range rule
        # would stretch the y-scale and flatten the series it exists to
        # contextualise. Labelled in text, so the line never means by position
        # alone.
        ceiling = data["value"].max()
        thresholds = pd.DataFrame(
            [
                {"y": band.upper, "name": f"{band.upper} \u00b7 {band.name} ceiling"}
                for band in AQI_CATEGORIES[:-1]
                if band.upper <= ceiling * 1.15
            ]
        )
        if not thresholds.empty:
            layers.append(
                alt.Chart(thresholds)
                .mark_rule(color=ink["text_muted"], strokeWidth=1, strokeDash=[2, 4], opacity=0.8)
                .encode(y=alt.Y("y:Q", scale=alt.Scale(zero=False)))
            )
            layers.append(
                alt.Chart(thresholds)
                .mark_text(align="left", dx=4, dy=-5, fontSize=10, color=ink["text_muted"])
                .encode(y="y:Q", text="name:N", x=alt.value(2))
            )

    line = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, interpolate="monotone")
        .encode(
            x=x,
            y=y,
            color=color,
            strokeDash=alt.StrokeDash(
                "phase:N",
                scale=alt.Scale(domain=["Observed", "Forecast"], range=[[1, 0], [4, 3]]),
                legend=alt.Legend(title=None, symbolType="stroke"),
            ),
            detail="metric:N",
        )
    )
    layers.append(line)
    layers.append(_now_rule(now, mode))

    # Crosshair: an invisible full-height rule that snaps to the nearest hour,
    # plus a ringed marker per series so overlapping points stay separable.
    crosshair = (
        alt.Chart(data)
        .mark_rule(color=ink["text_muted"], strokeWidth=1)
        .encode(
            x=x,
            opacity=alt.condition(hover, alt.value(0.4), alt.value(0)),
            tooltip=[
                alt.Tooltip("time:T", title="Time", format="%a %b %-d, %-I:%M %p"),
                *[
                    alt.Tooltip(
                        f"{m.key}_value:Q",
                        title=f"{m.label}{f' ({m.unit})' if m.unit else ''}",
                        format=f".{m.decimals}f",
                    )
                    for m in metrics
                ],
            ],
        )
        .transform_pivot("metric", value="value", groupby=["time"], op="max")
        .transform_calculate(
            **{f"{m.key}_value": alt.datum[m.key] for m in metrics}
        )
        .add_params(hover)
    )
    points = (
        alt.Chart(data)
        .mark_point(size=90, filled=True, stroke=ink["surface"], strokeWidth=2)
        .encode(
            x=x,
            y=y,
            color=color,
            detail="metric:N",
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        )
    )
    layers.extend([crosshair, points])

    chart = alt.layer(*layers).resolve_scale(y="shared").properties(height=height)
    return _base_config(chart, mode)


def sparkline(frame: pd.DataFrame, metric_key: str, *, now: pd.Timestamp, mode: str = "light") -> alt.Chart:
    """A bare 24-hour trend line for a stat tile. No axes, no legend."""
    ink = palette(mode)
    window = frame[(frame["metric"] == metric_key) & (frame["time"] >= now - pd.Timedelta(hours=24))]
    if window.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()
    chart = (
        alt.Chart(window)
        .mark_line(strokeWidth=2, interpolate="monotone", color=ink["series"][0])
        .encode(
            x=alt.X("time:T", axis=None),
            y=alt.Y("value:Q", axis=None, scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("time:T", title="Time", format="%-I%p"),
                alt.Tooltip("value:Q", title=METRICS_BY_KEY[metric_key].label, format=".1f"),
            ],
        )
        .properties(height=44)
    )
    return _base_config(chart, mode)


def borough_chart(city: pd.DataFrame, *, mode: str = "light") -> alt.Chart:
    """Current mean AQI by borough.

    A dot plot, not bars. Citywide AQI usually spans three or four points, and
    on the zero baseline bars demand, every borough renders as the same
    full-width rectangle. Dots carry no area claim, so the axis is free to
    start where the data does and the spread becomes readable. Each dot is
    directly labelled, so the comparison survives without the axis.
    """
    ink = palette(mode)
    summary = (
        city.groupby("borough", as_index=False)
        .agg(us_aqi=("us_aqi", "mean"), pm2_5=("pm2_5", "mean"), stations=("stop_name", "size"))
        .sort_values("us_aqi", ascending=False)
    )
    order = list(summary["borough"])
    low, high = summary["us_aqi"].min(), summary["us_aqi"].max()
    pad = max(1.0, (high - low) * 0.35)

    scale = alt.Scale(domain=[low - pad, high + pad], nice=False)
    x = alt.X(
        "us_aqi:Q",
        title="Mean US AQI across the borough's stations",
        scale=scale,
        axis=alt.Axis(grid=True, tickCount=5),
    )
    y = alt.Y(
        "borough:N",
        title=None,
        sort=order,
        axis=alt.Axis(grid=False, labelOverlap=False, labelLimit=140),
    )
    tooltip = [
        alt.Tooltip("borough:N", title="Borough"),
        alt.Tooltip("us_aqi:Q", title="Mean US AQI", format=".1f"),
        alt.Tooltip("pm2_5:Q", title="Mean PM2.5", format=".1f"),
        alt.Tooltip("stations:Q", title="Stations"),
    ]

    # A faint stem from the axis floor gives the eye a row to track without
    # implying the magnitude a bar would.
    stems = (
        alt.Chart(summary)
        .mark_rule(color=ink["grid"], strokeWidth=1)
        .encode(x=alt.X("us_aqi:Q", scale=scale), x2=alt.datum(low - pad), y=y)
    )
    dots = (
        alt.Chart(summary)
        .mark_point(size=150, filled=True, color=ink["series"][0],
                    stroke=ink["surface"], strokeWidth=2)
        .encode(x=x, y=y, tooltip=tooltip)
    )
    labels = (
        alt.Chart(summary)
        .mark_text(align="left", dx=12, fontSize=11, color=ink["text_secondary"])
        .encode(x=x, y=y, text=alt.Text("us_aqi:Q", format=".1f"))
    )
    chart = alt.layer(stems, dots, labels).properties(height=34 * len(summary) + 30)
    return _base_config(chart, mode)


# ---------------------------------------------------------------------------
# Infiltration model
# ---------------------------------------------------------------------------


def exposure_chart(
    frame: pd.DataFrame,
    metric_key: str,
    *,
    now: pd.Timestamp,
    series: tuple[str, str],
    mode: str = "light",
    height: int = 240,
    zero: bool = True,
) -> alt.Chart:
    """Street-level vs modelled-underground concentration for one PM metric.

    Both series are the same quantity in the same unit, so they belong on one
    shared axis -- the one case where two lines on a single scale is the honest
    form rather than the dual-axis mistake.
    """
    ink = palette(mode)
    metric = METRICS_BY_KEY[metric_key]
    data = frame[frame["metric"] == metric_key]
    if data.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()

    data = _split_at_now(data, now, group=["metric", "exposure"])
    order = list(series)
    baseline, elevated = order
    hover = alt.selection_point(
        fields=["time"], nearest=True, on="pointerover", empty=False, clear="pointerout"
    )

    x = alt.X("time:T", title=None, axis=alt.Axis(grid=False, format="%a %-I%p", tickCount=7))
    y = alt.Y(
        "value:Q",
        title=metric.unit,
        # Concentrations belong on a zero baseline; temperatures do not --
        # anchoring degF at zero would squash the whole series into a band.
        scale=alt.Scale(zero=zero, nice=True),
        axis=alt.Axis(grid=True, tickCount=5),
    )
    color = alt.Color(
        "exposure:N",
        scale=alt.Scale(domain=order, range=ink["series"][:2]),
        legend=alt.Legend(title=None),
    )

    area = (
        alt.Chart(data)
        # op="max" is load-bearing: _split_at_now duplicates the boundary row so
        # the solid and dashed lines meet, and pivot's default `sum` would
        # double-count that one timestamp into a spike at `now`.
        .transform_pivot("exposure", value="value", groupby=["time"], op="max")
        .mark_area(color=ink["series"][0], opacity=0.10)
        .encode(
            x=x,
            y=alt.Y(f"{baseline}:Q", title=metric.unit),
            y2=alt.Y2(f"{elevated}:Q"),
        )
    )
    line = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, interpolate="monotone")
        .encode(
            x=x,
            y=y,
            color=color,
            strokeDash=alt.StrokeDash(
                "phase:N",
                scale=alt.Scale(domain=["Observed", "Forecast"], range=[[1, 0], [4, 3]]),
                legend=alt.Legend(title=None, symbolType="stroke"),
            ),
            detail="exposure:N",
        )
    )
    crosshair = (
        alt.Chart(data)
        .mark_rule(color=ink["text_muted"], strokeWidth=1)
        .encode(
            x=x,
            opacity=alt.condition(hover, alt.value(0.4), alt.value(0)),
            tooltip=[
                alt.Tooltip("time:T", title="Time", format="%a %b %-d, %-I:%M %p"),
                alt.Tooltip(f"{baseline}:Q", title=f"{baseline} ({metric.unit})", format=".1f"),
                alt.Tooltip(f"{elevated}:Q", title=f"{elevated} ({metric.unit})", format=".1f"),
            ],
        )
        .transform_pivot("exposure", value="value", groupby=["time"], op="max")
        .add_params(hover)
    )
    points = (
        alt.Chart(data)
        .mark_point(size=90, filled=True, stroke=ink["surface"], strokeWidth=2)
        .encode(
            x=x, y=y, color=color, detail="exposure:N",
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        )
    )
    chart = (
        alt.layer(area, line, _now_rule(now, mode), crosshair, points)
        .resolve_scale(y="shared")
        .properties(height=height)
    )
    return _base_config(chart, mode)


def infiltration_curve_chart(
    curve: pd.DataFrame,
    *,
    air_exchange: float,
    mode: str = "light",
    height: int = 230,
) -> alt.Chart:
    """Infiltration factor F against air exchange rate `a`.

    The point of the chart is to show where the answer stops depending on the
    guess: once a curve has flattened, refining `a` changes nothing.
    """
    ink = palette(mode)
    labelled = curve.assign(label=curve["metric"].map(lambda k: METRICS_BY_KEY[k].label))
    order = [METRICS_BY_KEY[k].label for k in curve["metric"].unique()]

    x = alt.X(
        "air_exchange:Q",
        title="Air exchange rate a (air changes per hour)",
        scale=alt.Scale(domain=[curve["air_exchange"].min(), curve["air_exchange"].max()],
                        nice=False),
        axis=alt.Axis(grid=False, tickCount=6),
    )
    y = alt.Y(
        "factor:Q",
        title="Infiltration factor F",
        scale=alt.Scale(domain=[0, 1]),
        axis=alt.Axis(grid=True, tickCount=5, format=".0%"),
    )
    color = alt.Color(
        "label:N",
        scale=alt.Scale(domain=order, range=ink["series"][: len(order)]),
        legend=alt.Legend(title=None),
    )

    lines = alt.Chart(labelled).mark_line(strokeWidth=2).encode(x=x, y=y, color=color)

    marker = pd.DataFrame({"air_exchange": [air_exchange]})
    rule = (
        alt.Chart(marker)
        .mark_rule(color=ink["text_muted"], strokeWidth=1, strokeDash=[3, 3])
        .encode(x="air_exchange:Q")
    )
    # The operating point: where the sliders currently sit on each curve.
    nearest = (
        labelled.assign(distance=(labelled["air_exchange"] - air_exchange).abs())
        .sort_values("distance")
        .groupby("label", as_index=False)
        .head(1)
    )
    dots = (
        alt.Chart(nearest)
        .mark_point(size=130, filled=True, stroke=ink["surface"], strokeWidth=2)
        .encode(
            x=x, y=y, color=color,
            tooltip=[
                alt.Tooltip("label:N", title="Pollutant"),
                alt.Tooltip("factor:Q", title="F at current a", format=".1%"),
            ],
        )
    )
    labels = (
        alt.Chart(nearest)
        .mark_text(align="left", dx=10, fontSize=11, color=ink["text_secondary"])
        .encode(x=x, y=y, text=alt.Text("factor:Q", format=".0%"))
    )
    chart = alt.layer(lines, rule, dots, labels).properties(height=height)
    return _base_config(chart, mode)


def structure_delta_c_chart(
    all_delta_c: pd.DataFrame,
    *,
    station_id: str,
    mode: str = "light",
) -> alt.Chart:
    """dC across all 496 stations, grouped by ventilation class.

    Rows are the enclosure classes the model actually distinguishes, not the six
    raw `structure` values: four of those six are open air and would otherwise
    occupy four separate rows all reading zero. A dot plot, because dC takes
    only a handful of distinct values -- it is fixed by (structure,
    route_count), so 496 stations collapse onto about a dozen points. Dot area
    is how many stations share each one; the selected station is ringed.
    """
    ink = palette(mode)

    grouped = (
        all_delta_c.groupby(["enclosure", "route_count", "delta_c"], as_index=False)
        .agg(stations=("stop_name", "size"))
    )
    order = list(
        all_delta_c.groupby("enclosure")["delta_c"].max().sort_values(ascending=False).index
    )

    # Pad the domain so the biggest dot at dC = 0 cannot sit on the axis labels.
    span = max(grouped["delta_c"].max(), 1.0)
    x = alt.X(
        "delta_c:Q",
        title="\u0394C \u2014 PM2.5 the trains add (\u00b5g/m\u00b3)",
        scale=alt.Scale(domain=[-span * 0.06, span * 1.08], nice=False),
        axis=alt.Axis(grid=True, tickCount=5),
    )
    y = alt.Y(
        "enclosure:N",
        title=None,
        sort=order,
        axis=alt.Axis(grid=False, labelOverlap=False, labelLimit=200),
    )

    stems = (
        alt.Chart(grouped)
        .mark_rule(color=ink["grid"], strokeWidth=1)
        # The typed field must drive `x`; a bare alt.datum() there emits an
        # encoding with no "type" and the Vega-Lite runtime throws on it.
        .encode(x=x, x2=alt.datum(0), y=y)
    )
    dots = (
        alt.Chart(grouped)
        .mark_point(filled=True, color=ink["series"][0],
                    stroke=ink["surface"], strokeWidth=2)
        .encode(
            x=x, y=y,
            size=alt.Size(
                "stations:Q",
                scale=alt.Scale(range=[70, 420]),
                legend=alt.Legend(
                    title="Stations", orient="top", direction="horizontal",
                    values=[25, 75, 150],
                ),
            ),
            tooltip=[
                alt.Tooltip("enclosure:N", title="Ventilation"),
                alt.Tooltip("route_count:Q", title="Routes"),
                alt.Tooltip("delta_c:Q", title="\u0394C", format=".1f"),
                alt.Tooltip("stations:Q", title="Stations"),
            ],
        )
    )

    selected = all_delta_c[all_delta_c["gtfs_stop_id"] == station_id]
    ring = (
        alt.Chart(selected)
        .mark_point(size=560, filled=False, strokeWidth=2, strokeDash=[3, 2],
                    color=ink["text_primary"])
        .encode(x=x, y=y)
    )
    ring_label = (
        alt.Chart(selected)
        .mark_text(align="left", dx=22, fontSize=11, fontWeight="bold",
                   color=ink["text_primary"])
        .encode(x=x, y=y, text=alt.Text("stop_name:N"))
    )

    # Generous row height: the largest dots run ~23 px across, so tighter
    # bands let neighbouring rows' marks collide.
    chart = alt.layer(stems, dots, ring, ring_label).properties(
        height=80 * len(order) + 60
    )
    return _base_config(chart, mode)


def heat_budget_chart(
    sources_w: dict[str, float], *, mode: str = "light"
) -> alt.Chart:
    """Where a platform's heat comes from. Magnitude across a few named
    categories on a meaningful zero, so bars are the right form here."""
    ink = palette(mode)
    frame = (
        pd.DataFrame(
            [{"source": k, "kw": v / 1000.0} for k, v in sources_w.items()]
        )
        .sort_values("kw", ascending=False)
    )
    bars = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                  height=20, color=ink["series"][0])
        .encode(
            x=alt.X("kw:Q", title="kW", axis=alt.Axis(grid=True, tickCount=4)),
            y=alt.Y("source:N", title=None, sort="-x",
                    axis=alt.Axis(grid=False, labelLimit=200)),
            tooltip=[
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("kw:Q", title="kW", format=".1f"),
            ],
        )
    )
    labels = (
        alt.Chart(frame)
        .mark_text(align="left", dx=6, fontSize=11, color=ink["text_secondary"])
        .encode(x="kw:Q", y=alt.Y("source:N", sort="-x"),
                text=alt.Text("kw:Q", format=".1f"))
    )
    return _base_config(alt.layer(bars, labels).properties(height=30 * len(frame) + 40), mode)
