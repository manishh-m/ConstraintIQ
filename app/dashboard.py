"""ConstraintIQ — Streamlit dashboard.

    uv run streamlit run app/dashboard.py

Three sections:
  1. Network Snapshot    — current utilisation per hub, KPI tiles
  2. Demand & Forecast   — historical demand + 14-day Holt-Winters forecast per zone
  3. Constraint Migration — historical migration timeline + forecast projection
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── page config (must be first Streamlit call) ──────────────────────────────
st.set_page_config(
    page_title="ConstraintIQ",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── load pipeline (cached so re-renders don't re-run everything) ─────────────
@st.cache_data(show_spinner="Running pipeline…")
def load_results() -> dict:
    from constraintiq.pipeline import run
    return run()


# ── colour palette ────────────────────────────────────────────────────────────
HUB_COLOURS = {
    "HUB_NORTH": "#3B82F6",   # blue
    "HUB_SOUTH": "#F97316",   # orange
}
ZONE_COLOURS = {
    "Z1": "#60A5FA", "Z2": "#93C5FD", "Z3": "#1D4ED8", "Z4": "#BFDBFE",
    "Z5": "#FB923C", "Z6": "#EA580C", "Z7": "#FED7AA",
}
DANGER   = "#EF4444"
WARNING  = "#F59E0B"
OK_GREEN = "#10B981"

CAPACITY_LINE = dict(color="red", width=1.5, dash="dash")


def utilisation_colour(u: float) -> str:
    if u >= 1.0:
        return DANGER
    if u >= 0.80:
        return WARNING
    return OK_GREEN


# ── helpers ───────────────────────────────────────────────────────────────────
def kpi_tile(label: str, value: str, colour: str) -> None:
    st.markdown(
        f"""
        <div style="background:{colour}18;border-left:4px solid {colour};
                    padding:12px 16px;border-radius:6px;margin-bottom:4px">
            <div style="font-size:0.78rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:.05em">{label}</div>
            <div style="font-size:1.5rem;font-weight:700;color:{colour}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hub_utilisation_gauge(hub_id: str, load: float, capacity: float) -> go.Figure:
    u = load / capacity
    colour = utilisation_colour(u)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(u * 100, 1),
        number={"suffix": "%", "font": {"size": 28}},
        delta={"reference": 100, "relative": False,
               "increasing": {"color": DANGER}, "decreasing": {"color": OK_GREEN}},
        gauge={
            "axis": {"range": [0, 160], "ticksuffix": "%"},
            "bar": {"color": colour},
            "steps": [
                {"range": [0, 80],   "color": "#D1FAE5"},
                {"range": [80, 100], "color": "#FEF3C7"},
                {"range": [100, 160],"color": "#FEE2E2"},
            ],
            "threshold": {"line": {"color": "red", "width": 2}, "value": 100},
        },
        title={"text": hub_id.replace("_", " "), "font": {"size": 14}},
    ))
    fig.update_layout(height=200, margin=dict(t=40, b=0, l=20, r=20))
    return fig


# ── section 1: network snapshot ───────────────────────────────────────────────
def section_network(results: dict) -> None:
    st.subheader("Network Snapshot")
    st.caption(f"Last day of history — {results['demand']['date'].max().date()}")

    config  = results["config"]
    network = results["network"]
    util    = results["utilization"]
    last_day = util["date"].max()
    today   = util[util["date"] == last_day]

    # KPI row
    cols = st.columns(len(config.hubs) + 2)
    for i, hub in enumerate(config.hubs):
        row = today[today["resource_id"] == hub.id].iloc[0]
        u   = row["utilization"]
        with cols[i]:
            kpi_tile(
                hub.name,
                f"{u:.0%} utilised",
                utilisation_colour(u),
            )

    bc = results["current_constraint"]
    with cols[-2]:
        kpi_tile("Binding Constraint", bc.resource_id.replace("_", " "), DANGER if bc.utilization >= 1 else WARNING)
    with cols[-1]:
        n_events = len(results["historical_migrations"])
        kpi_tile("Historical Migration Events", str(n_events), "#7C3AED")

    st.markdown("---")

    # Gauge + zone breakdown
    gauge_cols = st.columns(len(config.hubs))
    for i, hub in enumerate(config.hubs):
        row = today[today["resource_id"] == hub.id].iloc[0]
        with gauge_cols[i]:
            st.plotly_chart(
                hub_utilisation_gauge(hub.id, row["load"], row["capacity"]),
                use_container_width=True,
            )
            # Zone breakdown table for this hub
            hub_zones = [z for z in config.zones if z.hub == hub.id]
            last_demand = results["demand"][results["demand"]["date"] == last_day]
            rows = []
            for z in hub_zones:
                d = last_demand[last_demand["zone_id"] == z.id]["demand"].values
                rows.append({"Zone": z.name, "Zone ID": z.id,
                              "Demand (parcels)": f"{d[0]:,.0f}" if len(d) else "—",
                              "Trend/day": f"+{z.trend_per_day:.0f}" if z.trend_per_day >= 0 else f"{z.trend_per_day:.0f}"})
            st.dataframe(pd.DataFrame(rows).set_index("Zone"), use_container_width=True, height=210)


# ── section 2: demand & forecast ─────────────────────────────────────────────
def section_demand(results: dict) -> None:
    st.subheader("Demand & Forecast")
    st.caption("Historical demand (solid) + 14-day Holt-Winters forecast (dashed) per zone")

    config    = results["config"]
    demand    = results["demand"].copy()
    forecasts = results["forecasts"].copy()
    demand["date"]    = pd.to_datetime(demand["date"])
    forecasts["date"] = pd.to_datetime(forecasts["date"])

    # Hub selector
    hub_options = {h.name: h.id for h in config.hubs}
    selected_hub_name = st.radio("Hub", list(hub_options.keys()), horizontal=True)
    selected_hub = hub_options[selected_hub_name]

    hub_zones = [z for z in config.zones if z.hub == selected_hub]
    zone_ids  = [z.id for z in hub_zones]
    zone_names = {z.id: z.name for z in hub_zones}

    fig = go.Figure()

    for zid in zone_ids:
        colour = ZONE_COLOURS.get(zid, "#6B7280")
        h = demand[demand["zone_id"] == zid].sort_values("date")
        f = forecasts[forecasts["zone_id"] == zid].sort_values("date")

        fig.add_trace(go.Scatter(
            x=h["date"], y=h["demand"],
            name=zone_names[zid],
            line=dict(color=colour, width=1.8),
            legendgroup=zid,
        ))
        fig.add_trace(go.Scatter(
            x=f["date"], y=f["forecast_demand"],
            name=f"{zone_names[zid]} (forecast)",
            line=dict(color=colour, width=2, dash="dot"),
            legendgroup=zid,
            showlegend=False,
        ))

    # Shaded forecast region
    hist_end = demand["date"].max()
    fig.add_vrect(
        x0=hist_end, x1=forecasts["date"].max(),
        fillcolor="#F3F4F6", opacity=0.5, layer="below", line_width=0,
        annotation_text="Forecast →", annotation_position="top left",
    )

    # Vertical divider
    fig.add_vline(x=hist_end, line_dash="dot", line_color="#9CA3AF", line_width=1)

    fig.update_layout(
        height=420,
        margin=dict(t=20, b=40, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        xaxis_title=None,
        yaxis_title="Parcels / day",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# ── section 3: constraint migration ──────────────────────────────────────────
def section_migration(results: dict) -> None:
    st.subheader("Constraint Migration")

    config     = results["config"]
    util       = results["utilization"].copy()
    proj       = results["projected_utilization"].copy()
    hist_migs  = results["historical_migrations"]
    fore_migs  = results["migration_events"]
    util["date"] = pd.to_datetime(util["date"])
    proj["date"] = pd.to_datetime(proj["date"])

    from constraintiq.toc.constraint import smooth_utilization
    util_smooth = smooth_utilization(util)

    # --- utilisation timeline chart ---
    st.caption("7-day smoothed hub utilisation (history + 14-day projection). Red line = 100% capacity.")
    fig = go.Figure()

    for hub in config.hubs:
        colour = HUB_COLOURS.get(hub.id, "#6B7280")

        h = util_smooth[util_smooth["resource_id"] == hub.id].sort_values("date")
        p = proj[proj["resource_id"] == hub.id].sort_values("date")

        fig.add_trace(go.Scatter(
            x=h["date"], y=(h["utilization"] * 100).round(1),
            name=hub.name,
            line=dict(color=colour, width=2),
            legendgroup=hub.id,
        ))
        fig.add_trace(go.Scatter(
            x=p["date"], y=(p["utilization"] * 100).round(1),
            name=f"{hub.name} (projected)",
            line=dict(color=colour, width=2, dash="dot"),
            legendgroup=hub.id,
            showlegend=False,
        ))

    hist_end = util["date"].max()
    fig.add_vrect(
        x0=hist_end, x1=proj["date"].max(),
        fillcolor="#F3F4F6", opacity=0.5, layer="below", line_width=0,
        annotation_text="Forecast →", annotation_position="top left",
    )
    fig.add_vline(x=hist_end, line_dash="dot", line_color="#9CA3AF", line_width=1)
    fig.add_hline(y=100, line=CAPACITY_LINE,
                  annotation_text="Capacity ceiling (100%)", annotation_position="bottom right")

    # Mark historical migration events on the chart
    for e in hist_migs:
        fig.add_vline(
            x=e.day, line_width=1, line_dash="dot", line_color="#7C3AED",
            annotation_text=f"→ {e.to_resource.replace('HUB_', '')}",
            annotation_font_size=9, annotation_font_color="#7C3AED",
        )

    fig.update_layout(
        height=420,
        margin=dict(t=20, b=40, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        xaxis_title=None,
        yaxis_title="Utilisation (%)",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- event tables side by side ---
    left, right = st.columns(2)

    with left:
        st.markdown("**Historical migration events** (smoothed)")
        if hist_migs:
            rows = [{"Date": str(e.day.date()), "From": e.from_resource.replace("HUB_", ""),
                     "To": e.to_resource.replace("HUB_", ""),
                     "Utilisation at migration": f"{e.projected_utilization:.1%}"} for e in hist_migs]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            last = hist_migs[-1]
            st.info(
                f"Constraint **permanently** settled at **{last.to_resource.replace('HUB_', 'Hub ')}** "
                f"after **{last.day.date()}** as Zone 3's demand trend became decisive.",
                icon="📌",
            )
        else:
            st.info("No migrations detected in history window.")

    with right:
        st.markdown("**Forecast migration events** (next 14 days)")
        if fore_migs:
            rows = [{"Date": str(e.day.date()), "From": e.from_resource.replace("HUB_", ""),
                     "To": e.to_resource.replace("HUB_", ""),
                     "Projected utilisation": f"{e.projected_utilization:.1%}"} for e in fore_migs]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.success(
                "No constraint migration expected in the next 14 days. "
                "North Hub remains the binding constraint — its utilisation continues to rise.",
                icon="✅",
            )
            # Show projected utilisation at horizon end
            proj_end = proj[proj["date"] == proj["date"].max()]
            for hub in config.hubs:
                row = proj_end[proj_end["resource_id"] == hub.id]
                if not row.empty:
                    u = row.iloc[0]["utilization"]
                    colour = utilisation_colour(u)
                    st.markdown(
                        f"<span style='color:{colour}'>**{hub.name}** — projected {u:.1%} utilisation at horizon</span>",
                        unsafe_allow_html=True,
                    )


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    # Header
    st.markdown(
        "<h1 style='margin-bottom:0'>📦 ConstraintIQ</h1>"
        "<p style='color:#6B7280;margin-top:4px'>Predictive constraint-migration detection · last-mile logistics · proof-of-concept</p>",
        unsafe_allow_html=True,
    )

    st.warning(
        "**Synthetic data prototype** — not connected to any live logistics network. "
        "Data is generated from parameterised demand models (trend + weekly seasonality + noise). "
        "See `data/README.md` for methodology.",
        icon="⚠️",
    )

    results = load_results()

    st.markdown("---")
    section_network(results)

    st.markdown("---")
    section_demand(results)

    st.markdown("---")
    section_migration(results)

    st.markdown("---")
    st.caption(
        "ConstraintIQ · proof-of-concept · synthetic data · "
        "Theory of Constraints + Holt-Winters demand forecasting"
    )


if __name__ == "__main__":
    main()
