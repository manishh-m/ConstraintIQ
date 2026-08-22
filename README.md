# ConstraintIQ

**A proof-of-concept for predictive constraint-migration detection in last-mile logistics networks.**

ConstraintIQ combines **Theory of Constraints (ToC)** reasoning with **ML-based demand
forecasting**. Where a traditional bottleneck analysis tells you where the constraint is
*today*, ConstraintIQ aims to predict where the constraint will **migrate to next** as demand
shifts across hubs and zones — so capacity decisions can be made ahead of the bottleneck, not
after it.

> ⚠️ **This is a prototype built on synthetic data.** It is *not* a live or production system.
> There is no connection to any real logistics network. The data is generated (see
> [`data/README.md`](data/README.md)) because no real last-mile operational dataset was
> available — the synthetic generator is deliberately transparent about its assumptions so the
> ToC and forecasting logic can be evaluated on their own merits.

## The idea in one line

`forecast demand per zone` → `project each hub/zone toward its throughput ceiling` →
`flag which resource becomes the binding constraint next, and when`.

## Scope

- 2 hubs, 7 zones (configurable in [`config/network.yaml`](config/network.yaml))
- Synthetic demand with trend + weekly seasonality + noise
- Classical time-series forecasting (explainable by design)
- ToC constraint model + constraint-migration projection
- Streamlit dashboard for the demo

## Project layout

```
config/      network scenario (hubs, zones, capacities, demand params)
data/        generated synthetic data (regenerable, gitignored)
src/constraintiq/
  datagen/     synthetic network + demand generation
  forecasting/ demand forecasting models + backtesting
  toc/         Theory of Constraints: current bottleneck + migration projection
  pipeline.py  end-to-end run: datagen -> forecast -> ToC
app/         Streamlit dashboard
notebooks/   narrative walkthroughs
tests/       unit tests
docs/        methodology + PRD
```

## Getting started

Requires [`uv`](https://docs.astral.sh/uv/) (`brew install uv`).

```bash
uv sync --extra dev          # create .venv and install deps (uv fetches Python 3.12)
uv run python -m constraintiq.pipeline   # run the end-to-end pipeline (once implemented)
uv run streamlit run app/dashboard.py    # launch the demo dashboard
uv run pytest                # run tests
```

## Status

Early stage — scaffolding in place; core logic under active build. See
[`docs/methodology.md`](docs/methodology.md) for approach and [`docs/prd.md`](docs/prd.md) for
scope/requirements.
