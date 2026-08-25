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
- **Capacity now models elastic (crowdsourced) surge** — base capacity plus a bounded, lead-time-gated surge pool, not a fixed ceiling. Effective capacity on any given day is `base + min(surge_needed, surge_available)`, where `surge_available` varies day-to-day due to day-of-week effects (gig partners less available Fri–Sun), partner fatigue after consecutive heavy-surge days, and gaussian noise (CV = 10%). The surge pool availability is generated synthetically in `datagen/capacity.py`.
- **Surge incentive cost modelled as a relative index** — `surge_cost_multiplier = volume_premium × short_notice_hit`, where `volume_premium = 1 + 0.5 × fraction²` (convex: mobilising the full surge pool costs 1.5× baseline, not 1.0×) and `short_notice_hit = 1 + 0.5 × shortfall_days` (each day short of the required lead time adds 50%). This is a relative cost signal, not a rupee figure. Worst-case (zero-notice) multipliers are shown per hub in the dashboard and API.
- **Independent zone forecasts** — no cross-zone demand correlation modelled yet.

## Open questions / next steps

- Add forecast uncertainty (prediction intervals) → migration *probability* and timing range,
  not a single date.
- Sensitivity analysis: how far ahead can migration be reliably called given forecast error?
- Soft→hard escalation detection: the constraint identity doesn't change, but the surge buffer
  is draining. This is arguably the more urgent operational signal and warrants a separate
  `EscalationEvent` type (tracked as a TODO in `migration.py`).
- Convert `surge_cost_multiplier` from a relative index to an absolute rupee estimate once
  per-rider incentive rates are available.
