# Methodology

> Living document. Captures *why* ConstraintIQ works the way it does, so the design choices
> hold up in conversation and interviews.

## Problem framing (Theory of Constraints)

Every network has, at any moment, exactly one binding constraint — the resource that governs
total throughput. In a last-mile network that constraint might be a hub's daily processing
capacity or a zone's delivery capacity. Standard analysis finds *today's* constraint.

ConstraintIQ's thesis: as demand shifts across zones over time, the binding constraint
**migrates**. If you can forecast demand, you can project each resource toward its capacity
ceiling and predict *which resource becomes the constraint next, and when* — enabling
proactive capacity decisions instead of reactive firefighting.

This maps to Goldratt's Five Focusing Steps: identify the constraint → exploit it → subordinate
to it → elevate it → repeat. ConstraintIQ adds a predictive front-end: *anticipate the next
"identify" step before the constraint actually binds.*

## Pipeline

1. **Synthetic data** — per-zone daily demand with trend + weekly seasonality + noise. Trends
   differ by zone so the constraint provably migrates over the window.
2. **Forecasting** — classical time-series (Holt-Winters / ARIMA) per zone. Chosen for
   explainability over black-box ML; every forecast must be defensible in plain terms and
   beat a naive seasonal baseline (see `forecasting/evaluate.py`).
3. **Constraint model** — aggregate zone demand to hub load; utilization = load / capacity;
   binding constraint = max utilization.
4. **Migration detection** — project forecasts onto utilization over the horizon; flag the
   day the binding constraint changes identity.

## Key assumptions & limitations (state these openly)

- **Synthetic data** — no real operational dataset; parameters are hand-set, not fitted to
  reality. Results demonstrate the *method*, not a validated forecast of any real network.
- **Additive demand → hub load** — assumes hub load is the simple sum of served-zone demand;
  ignores routing, shift scheduling, and inter-hub transfers.
- **Capacity as a fixed daily ceiling** — real capacity flexes (overtime, temp staff).
- **Independent zone forecasts** — no cross-zone demand correlation modelled yet.

## Open questions / next steps

- Add forecast uncertainty (prediction intervals) → migration *probability* and timing range,
  not a single date.
- Sensitivity analysis: how far ahead can migration be reliably called given forecast error?
