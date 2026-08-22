# ConstraintIQ — PRD (draft)

> Draft product requirements. Doubles as a PRD-writing artifact for the Shadowfax APM /
> Founder's Office transition.

## 1. Problem

Last-mile logistics networks manage capacity reactively: they respond to bottlenecks after
they bind, when demand has already shifted. There's no cheap way to see *where the constraint
is heading* before it gets there.

## 2. Goal

A proof-of-concept that predicts **constraint migration** — where and when a network's binding
constraint will shift next — by combining Theory of Constraints reasoning with demand
forecasting.

Non-goal: a production system, real-time integration, or a validated forecast of any specific
real network. This is a method demonstration on synthetic data.

## 3. Users (hypothetical)

- **Network / capacity planner** — wants early warning to reposition capacity proactively.
- **Ops leadership** — wants a defensible, explainable signal, not a black box.

## 4. Requirements

| # | Requirement | Priority |
|---|-------------|----------|
| R1 | Generate reproducible synthetic demand for 2 hubs / 7 zones | Must |
| R2 | Forecast per-zone demand with an explainable model that beats a naive baseline | Must |
| R3 | Identify the current binding constraint (ToC) | Must |
| R4 | Detect & report constraint migration over the forecast horizon | Must |
| R5 | Streamlit dashboard: network view, forecasts, migration timeline | Must |
| R6 | Transparent synthetic-data disclosure throughout | Must |
| R7 | Forecast uncertainty → migration probability / timing range | Should |
| R8 | What-if scenarios via config edits (no code change) | Should |

## 5. Success criteria

- The prototype correctly flags a *known* constraint migration built into the synthetic data.
- Every design choice is explainable in ToC terms in an interview setting.
- The write-up and demo are clean enough to show a Shadowfax audience.

## 6. Out of scope

Routing optimization, real-time data, driver-level modelling, multi-network generalization.
