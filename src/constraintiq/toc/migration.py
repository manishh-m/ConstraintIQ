"""Predict constraint migration — the headline capability of ConstraintIQ.

Takes per-zone demand forecasts, projects each hub's future utilization against its elastic
capacity ceiling, and detects when the binding constraint changes identity within the forecast
horizon. Answers: "which hub becomes the bottleneck next, on roughly which day, and — critically
— by when must surge mobilisation begin to avoid a hard breach?"

This is the predictive front-end to Goldratt's Five Focusing Steps: we anticipate the next
"Identify the constraint" step before the constraint actually binds, and give operations the
lead-time window they need to act before the soft constraint hardens.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from constraintiq.toc.constraint import compute_utilization, identify_binding_constraint, smooth_utilization


@dataclass(frozen=True)
class MigrationEvent:
    day: pd.Timestamp        # first day the new resource becomes the binding constraint
    from_resource: str
    to_resource: str
    projected_utilization: float   # utilization of the new constraint on that day
    act_by_date: pd.Timestamp      # day - to_resource.surge_lead_time_days; latest date
                                   # to begin surge mobilisation to avoid a hard breach

    def __str__(self) -> str:
        status = "hard breach" if self.projected_utilization > 1.0 else "soft breach"
        return (
            f"{self.day.date()}  constraint migrates  "
            f"{self.from_resource} → {self.to_resource}  "
            f"(projected utilisation {self.projected_utilization:.1%}, {status})  "
            f"— act by {self.act_by_date.date()} to mobilise surge"
        )

    # TODO: detect soft→hard escalation within the same resource (surge buffer running out
    # without a resource identity change). This is arguably the more urgent signal for a
    # crowdsourced fleet — the binding constraint isn't migrating, but the safety net is
    # disappearing. Would need a separate EscalationEvent dataclass and a parallel detection
    # pass over the utilization timeline. Deferred to keep detect_migration() focused.


def project_future_utilization(forecasts: pd.DataFrame, network: dict) -> pd.DataFrame:
    """Roll per-zone demand forecasts up to per-hub projected utilization over the horizon.

    Structurally identical to compute_utilization() — reuses it directly since forecasts
    carry the same [date, zone_id, hub_id, forecast_demand] shape, just renamed.

    Args:
        forecasts: DataFrame [date, zone_id, hub_id, forecast_demand].
        network:   Topology dict from build_network().

    Returns:
        DataFrame [date, resource_id, resource_type, load, base_capacity,
                   max_surge_capacity, surge_lead_time_days, effective_capacity,
                   utilization, is_soft, is_hard].
    """
    forecast_as_demand = forecasts.rename(columns={"forecast_demand": "demand"})
    return compute_utilization(forecast_as_demand, network)


def detect_migration(projected_utilization: pd.DataFrame) -> list[MigrationEvent]:
    """Walk the horizon day by day; emit a MigrationEvent whenever the binding constraint
    changes identity (i.e. a different hub becomes the top-priority resource).

    The act_by_date on each event is the migration day minus the incoming resource's
    surge_lead_time_days — the latest point at which surge mobilisation must start to
    avoid the incoming constraint becoming a hard breach on arrival.

    Args:
        projected_utilization: Output of project_future_utilization() or
                                smooth_utilization(), sorted by date.

    Returns:
        List of MigrationEvent in chronological order. Empty if no migration occurs
        within the horizon.
    """
    dates = sorted(projected_utilization["date"].unique())
    if not dates:
        return []

    events: list[MigrationEvent] = []
    prev_constraint = identify_binding_constraint(
        projected_utilization[projected_utilization["date"] == dates[0]]
    ).resource_id

    for date in dates[1:]:
        day_slice = projected_utilization[projected_utilization["date"] == date]
        current = identify_binding_constraint(day_slice)
        if current.resource_id != prev_constraint:
            act_by = pd.Timestamp(date) - pd.Timedelta(days=current.surge_lead_time_days)
            events.append(MigrationEvent(
                day=pd.Timestamp(date),
                from_resource=prev_constraint,
                to_resource=current.resource_id,
                projected_utilization=current.utilization,
                act_by_date=act_by,
            ))
            prev_constraint = current.resource_id

    return events


def migration_summary(events: list[MigrationEvent], label: str = "forecast horizon") -> str:
    """Human-readable summary — used in pipeline output and the dashboard."""
    if not events:
        return f"No constraint migration detected within the {label}."
    lines = [f"Constraint migration ({label}):"]
    for e in events:
        lines.append(f"  {e}")
    return "\n".join(lines)


def detect_historical_migration(utilization: pd.DataFrame, smooth: bool = True) -> list[MigrationEvent]:
    """Detect constraint migration in the historical utilization record.

    Args:
        utilization: Output of compute_utilization().
        smooth:      If True (default), apply 7-day rolling smoothing before detection to
                     suppress day-of-week noise. Only trend-driven shifts are surfaced.
    """
    u = smooth_utilization(utilization) if smooth else utilization
    return detect_migration(u)
