"""ConstraintIQ — FastAPI layer.

Three endpoints power the Next.js dashboard:
  GET /api/summary   — current hub utilisation, binding constraint, KPI counts
  GET /api/demand    — historical demand + 14-day Holt-Winters forecast per zone
  GET /api/migration — historical + forecast migration events + utilisation timeline

Pipeline runs once at startup and results are held in-process. The data is synthetic
and deterministic, so there's no reason to re-run on every request.

    uv run uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── pipeline cache ────────────────────────────────────────────────────────────

_RESULTS: dict | None = None


def _get_results() -> dict:
    global _RESULTS
    if _RESULTS is None:
        from constraintiq.pipeline import run
        _RESULTS = run()
    return _RESULTS


@asynccontextmanager
async def lifespan(app: FastAPI):
    _get_results()  # warm the cache at startup
    yield


# ── app ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ConstraintIQ API",
    description="Predictive constraint-migration detection — last-mile logistics proof-of-concept.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── serialisation helpers ─────────────────────────────────────────────────────

def _df_to_records(df, date_col: str = "date") -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records (Timestamps → ISO strings)."""
    out = df.copy()
    if date_col in out.columns:
        out[date_col] = out[date_col].astype(str)
    return out.to_dict(orient="records")


def _migration_event_to_dict(e) -> dict[str, Any]:
    return {
        "day": str(e.day.date()),
        "from_resource": e.from_resource,
        "to_resource": e.to_resource,
        "projected_utilization": round(e.projected_utilization, 4),
    }


# ── GET /api/summary ──────────────────────────────────────────────────────────

@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    """Current network snapshot: hub utilisation, binding constraint, KPI counts."""
    r = _get_results()

    config  = r["config"]
    util    = r["utilization"]
    demand  = r["demand"]
    bc      = r["current_constraint"]

    last_day = util["date"].max()
    today    = util[util["date"] == last_day]
    last_demand = demand[demand["date"] == last_day]

    hubs = []
    for hub in config.hubs:
        row  = today[today["resource_id"] == hub.id].iloc[0]
        u    = float(row["utilization"])
        load = float(row["load"])
        cap  = float(row["effective_capacity"])

        hub_zones = [z for z in config.zones if z.hub == hub.id]
        zones = []
        for z in hub_zones:
            d = last_demand[last_demand["zone_id"] == z.id]["demand"].values
            zones.append({
                "id": z.id,
                "name": z.name,
                "demand": round(float(d[0]), 1) if len(d) else None,
                "trend_per_day": z.trend_per_day,
            })

        hubs.append({
            "id": hub.id,
            "name": hub.name,
            "load": round(load, 1),
            "capacity": cap,
            "utilization": round(u, 4),
            "zones": zones,
        })

    return {
        "last_date": str(last_day.date()),
        "hubs": hubs,
        "binding_constraint": {
            "resource_id": bc.resource_id,
            "utilization": round(bc.utilization, 4),
        },
        "historical_migration_count": len(r["historical_migrations"]),
        "forecast_horizon_days": config.forecast_horizon,
    }


# ── GET /api/demand ───────────────────────────────────────────────────────────

@app.get("/api/demand")
def get_demand() -> dict[str, Any]:
    """Historical demand and 14-day Holt-Winters forecast, per zone."""
    r = _get_results()

    config    = r["config"]
    demand    = r["demand"][["date", "zone_id", "hub_id", "demand"]].copy()
    forecasts = r["forecasts"][["date", "zone_id", "hub_id", "forecast_demand"]].copy()

    # Round floats for wire size
    demand["demand"]              = demand["demand"].round(1)
    forecasts["forecast_demand"]  = forecasts["forecast_demand"].round(1)

    zones = [
        {
            "id": z.id,
            "name": z.name,
            "hub": z.hub,
            "base_demand": z.base_demand,
            "trend_per_day": z.trend_per_day,
            "weekly_seasonality": z.weekly_seasonality,
        }
        for z in config.zones
    ]

    return {
        "history": _df_to_records(demand),
        "forecasts": _df_to_records(forecasts),
        "zones": zones,
    }


# ── GET /api/migration ────────────────────────────────────────────────────────

@app.get("/api/migration")
def get_migration() -> dict[str, Any]:
    """Historical + forecast migration events, plus hub utilisation timeline."""
    r = _get_results()

    from constraintiq.toc.constraint import smooth_utilization

    util_smooth = smooth_utilization(r["utilization"])
    proj        = r["projected_utilization"]

    # Keep only hub-level rows with the columns the dashboard needs
    cols = ["date", "resource_id", "load", "effective_capacity", "utilization"]
    # Rename effective_capacity → capacity to keep the wire format stable for the frontend.
    util_records = _df_to_records(
        util_smooth[cols].rename(columns={"effective_capacity": "capacity"})
        .round({"load": 1, "utilization": 4})
    )
    proj_records = _df_to_records(
        proj[cols].rename(columns={"effective_capacity": "capacity"})
        .round({"load": 1, "utilization": 4})
    )

    return {
        "historical_events": [_migration_event_to_dict(e) for e in r["historical_migrations"]],
        "forecast_events":   [_migration_event_to_dict(e) for e in r["migration_events"]],
        "utilization_history":    util_records,
        "projected_utilization":  proj_records,
        "summary": r["summary"],
    }
