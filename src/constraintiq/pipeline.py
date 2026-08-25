"""End-to-end pipeline: datagen -> forecast -> ToC constraint migration.

    uv run python -m constraintiq.pipeline

Single orchestration point — ties the three layers together and returns all results the
dashboard needs in one dict.
"""

from __future__ import annotations

from constraintiq.config import load_config
from constraintiq.datagen.capacity import generate_surge_availability
from constraintiq.datagen.demand import generate_demand
from constraintiq.datagen.network import build_network
from constraintiq.forecasting.models import forecast_all_zones
from constraintiq.toc.capacity import CapacityState
from constraintiq.toc.constraint import (
    binding_constraint_history,
    compute_utilization,
    identify_binding_constraint,
)
from constraintiq.toc.migration import (
    detect_historical_migration,
    detect_migration,
    migration_summary,
    project_future_utilization,
)


def run(config_path=None) -> dict:
    """Run the full pipeline and return a results dict.

    Keys:
        config                   NetworkConfig
        network                  topology dict
        demand                   historical demand DataFrame [date, zone_id, hub_id, demand]
        forecasts                per-zone forecast DataFrame [date, zone_id, hub_id, forecast_demand]
        utilization              historical hub utilization DataFrame
        constraint_history       binding constraint per day over history [date, resource_id, utilization]
        historical_migrations    list[MigrationEvent] detected in the history window
        current_constraint       ResourceUtilization for the most recent day
        projected_utilization    forecast-period hub utilization DataFrame
        migration_events         list[MigrationEvent] detected in forecast horizon
        summary                  human-readable full summary string
    """
    config = load_config(*([config_path] if config_path else []))
    network = build_network(config)
    demand = generate_demand(config)
    surge_availability = generate_surge_availability(config)
    forecasts = forecast_all_zones(demand, horizon=config.forecast_horizon)

    utilization = compute_utilization(demand, network, surge_availability=surge_availability)
    constraint_hist = binding_constraint_history(utilization)
    historical_migrations = detect_historical_migration(utilization)

    last_day = utilization["date"].max()
    last_day_util = utilization[utilization["date"] == last_day]
    current_constraint = identify_binding_constraint(last_day_util)

    projected = project_future_utilization(forecasts, network)
    migration_events = detect_migration(projected)

    # Per-hub surge cost multiplier on the last day of history (worst-case notice = 0).
    hub_cost_multipliers: dict[str, float] = {}
    for _, row in last_day_util.iterrows():
        state = CapacityState(
            resource_id=row["resource_id"],
            base_capacity=float(row["base_capacity"]),
            max_surge_capacity=float(row["surge_available"]),
            surge_lead_time_days=int(row["surge_lead_time_days"]),
            load=float(row["load"]),
        )
        hub_cost_multipliers[row["resource_id"]] = round(state.surge_cost_multiplier, 4)

    summary_lines = [
        migration_summary(historical_migrations, label="history window"),
        migration_summary(migration_events, label="forecast horizon"),
    ]

    return {
        "config": config,
        "network": network,
        "demand": demand,
        "surge_availability": surge_availability,
        "forecasts": forecasts,
        "utilization": utilization,
        "constraint_history": constraint_hist,
        "historical_migrations": historical_migrations,
        "current_constraint": current_constraint,
        "projected_utilization": projected,
        "migration_events": migration_events,
        "hub_cost_multipliers": hub_cost_multipliers,
        "summary": "\n\n".join(summary_lines),
    }


if __name__ == "__main__":
    results = run()
    config = results["config"]

    print("\n=== ConstraintIQ — Pipeline Output ===\n")

    print("--- Historical utilisation (last 7 days) ---")
    tail = results["utilization"].tail(len(results["network"]["hubs"]) * 7)
    print(tail.to_string(index=False))

    print(f"\n--- Current binding constraint (day {config.days}) ---")
    cc = results["current_constraint"]
    if cc.is_hard:
        status = "HARD — surge exhausted, genuine throughput breach"
    elif cc.is_soft:
        status = "SOFT — surge deployed, buffer shrinking"
    else:
        status = "normal — within base capacity"
    cost_mult = results["hub_cost_multipliers"].get(cc.resource_id, 1.0)
    print(f"  {cc.resource_id}  load={cc.load:,.0f}  base={cc.base_capacity:,.0f}  "
          f"effective={cc.effective_capacity:,.0f}  utilisation={cc.utilization:.1%}  "
          f"surge_cost_multiplier={cost_mult:.2f}×  [{status}]")

    print("\n--- Surge cost multipliers (all hubs, worst-case notice) ---")
    for hub_id, mult in results["hub_cost_multipliers"].items():
        print(f"  {hub_id}: {mult:.2f}×")

    print(f"\n--- {results['summary']} ---")

    if results["historical_migrations"]:
        print("\nHistorical migration events:")
        for e in results["historical_migrations"]:
            print(f"  {e}")

    if results["migration_events"]:
        print("\nForecast migration events:")
        for e in results["migration_events"]:
            print(f"  {e}")
