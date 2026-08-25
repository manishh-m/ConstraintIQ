# ConstraintIQ — Project State Document

> **Purpose:** Single source of truth for ConstraintIQ's build context. Update the "Last updated" line and changelog at the end of every work session.

Last updated: **2026-08-25**
Current phase: **Complete prototype — demo-ready**

---

## 1. What This Project Is

**ConstraintIQ** is a predictive constraint-migration detection system for last-mile logistics networks, built as a capstone project to support an interview for a role at **Shadowfax Technologies** (Founder's Office / APM-type). A family contact holds a CXO position at Shadowfax — this raises the bar for demonstrated capability.

### The Core Insight
Theory of Constraints is inherently **reactive** — it identifies the current bottleneck only after it's already binding. ConstraintIQ's differentiator is combining ToC with **ML-based demand forecasting** to make constraint identification **predictive** — anticipating *where* a bottleneck will migrate to *before* it occurs.

### Framing for interviews
- Describe as a **"predictive analytics prototype"** or **"proof-of-concept for constraint-migration detection"** — never as a live/production system.
- Be **proactively transparent about synthetic data** — a credibility asset, not a weakness. Explain why (no access to real operational data) before anyone asks.

---

## 2. Current Build Status — Everything is Shipped

### ✅ Python pipeline (`src/constraintiq/`)
| Module | What it does |
|---|---|
| `config.py` | Loads `config/network.yaml` → `NetworkConfig` dataclass |
| `datagen/demand.py` | Synthetic demand: trend + weekly seasonality + noise (Holt-Winters-compatible) |
| `datagen/network.py` | Builds hub/zone topology dict from config |
| `forecasting/models.py` | Holt-Winters (`statsmodels`) per-zone 14-day forecast |
| `toc/constraint.py` | `compute_utilization()`, `identify_binding_constraint()`, `smooth_utilization()` (7-day rolling) |
| `toc/migration.py` | `detect_migration()`, `detect_historical_migration()`, `migration_summary()` |
| `pipeline.py` | Orchestrates everything → returns results dict used by both dashboards |

### ✅ Streamlit dashboard (`app/dashboard.py`)
Working fallback UI. Three sections: Network Snapshot, Demand & Forecast, Constraint Migration.
Run: `uv run streamlit run app/dashboard.py`

### ✅ FastAPI layer (`api/main.py`)
Three endpoints wrapping `pipeline.run()`. Pipeline cached at startup — no recomputation per request.

| Endpoint | Returns |
|---|---|
| `GET /api/summary` | Hub utilisation, binding constraint, zone breakdown, KPI counts |
| `GET /api/demand` | Historical demand + 14-day forecast per zone |
| `GET /api/migration` | Migration events + full utilisation timeline (smoothed history + projected) |

Run: `uv run uvicorn api.main:app --port 8000`

### ✅ Next.js dashboard (`web/`)
Primary demo surface. Next.js 16, React 19, Tailwind v4, recharts v3.
Page is an async Server Component — parallel-fetches all 3 FastAPI endpoints.
Three `'use client'` section components handle interactivity.

Run: `cd web && npm run dev` → http://localhost:3000

---

## 3. Network Topology (synthetic)

- **2 hubs:** HUB_NORTH (capacity 12,000/day), HUB_SOUTH (capacity 9,000/day)
- **7 zones:** Z1–Z4 → North Hub, Z5–Z7 → South Hub
- **180 days history + 14-day forecast horizon**
- Zone 3 (+20/day trend) and Zone 6 (+15/day trend) are the primary constraint drivers
- By end of history: North Hub ~135% utilised, South Hub ~119% — both over capacity

---

## 4. Environment & Stack

| Layer | Tech |
|---|---|
| Package manager | `uv` |
| Python | 3.12+ |
| Forecasting | `statsmodels` Holt-Winters (ExponentialSmoothing) |
| Data | `pandas`, `numpy` |
| Streamlit UI | `streamlit`, `plotly` |
| API | `fastapi`, `uvicorn` |
| Frontend | Next.js 16, React 19, Tailwind v4, recharts v3 |
| Config | `config/network.yaml` → `NetworkConfig` dataclass |
| Tests | `pytest` (4 test files covering all layers) |

**Project directory:** `/Users/Admin/constraintiq/`
**GitHub:** `github.com/manishh-m/ConstraintIQ`

---

## 5. Architecture Decisions

- **Synthetic data, proactively disclosed.** No access to real Shadowfax operational data. Data is parameterised (trend + seasonality + noise) — realistic enough to demonstrate the concept, not to be mistaken for real.
- **Holt-Winters for forecasting, not a heavy ML model.** Deliberate — keeps the prototype explainable. The forecasting layer is swappable; the ToC logic and migration detection are the differentiating piece.
- **FastAPI as the API boundary.** Pipeline runs once at startup; JSON responses feed the Next.js frontend. CORS is open to localhost:3000 only.
- **Dropped Tremor** (React ^18 peer dep conflict with React 19) — built UI directly with Tailwind + recharts. No functional difference.
- **Read-only overlay, not a system of record.** ConstraintIQ never writes back to operational systems. Its value is entirely in decision support.

---

## 6. Domain Terminology Reference

`ToC` (Theory of Constraints) · `constraint migration` · `binding constraint` · `NDR` (Non-Delivery Report) · `RTO` (Return to Origin) · `FADR` (First Attempt Delivery Rate) · `WMS/OMS/TMS` · `hub-and-spoke` · `VRP` (Vehicle Routing Problem) · `Little's Law (L = λW)` · `utilisation ceiling`

---

## 7. To Run

```bash
# FastAPI (Terminal 1)
uv run uvicorn api.main:app --port 8000

# Next.js dashboard (Terminal 2)
cd web && npm run dev
# → http://localhost:3000

# Streamlit fallback
uv run streamlit run app/dashboard.py

# Tests
uv run pytest
```

---

## 8. Changelog

- **2026-08-25** — Full prototype shipped: pipeline, Streamlit dashboard, FastAPI layer, Next.js dashboard. Pushed to GitHub.
- **2026-08-22** — Python pipeline built from scratch: datagen, Holt-Winters forecasting, ToC constraint + migration detection, Streamlit dashboard.
