"""Entry point: regenerate synthetic data into data/synthetic/.

    uv run python -m constraintiq.datagen
"""

from __future__ import annotations

import json
from pathlib import Path

from constraintiq.config import load_config
from constraintiq.datagen.demand import generate_demand
from constraintiq.datagen.network import build_network

OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def main() -> None:
    config = load_config()
    network = build_network(config)
    demand = generate_demand(config)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    network_path = OUT_DIR / "network.json"
    network_path.write_text(json.dumps(network, indent=2))

    demand_path = OUT_DIR / "demand.parquet"
    demand.to_parquet(demand_path, index=False)

    print(f"Written {len(demand):,} rows -> {demand_path}")
    print(f"Written network topology  -> {network_path}")
    print(f"\nDate range : {demand['date'].min().date()} to {demand['date'].max().date()}")
    print(f"Zones      : {demand['zone_id'].nunique()}")
    print(f"Hubs       : {demand['hub_id'].nunique()}")
    print(f"\nDaily demand by zone (mean ± std):")
    summary = demand.groupby("zone_id")["demand"].agg(["mean", "std"]).round(0)
    print(summary.to_string())


if __name__ == "__main__":
    main()
