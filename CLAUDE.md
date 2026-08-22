# ConstraintIQ — Project Context

## What This Is

ConstraintIQ is a predictive constraint-migration detection system for last-mile logistics networks. It combines Theory of Constraints (ToC) thinking with ML-based demand forecasting: instead of just identifying where a network's current bottleneck is, it aims to predict where the constraint will *migrate to next* as demand shifts across hubs and zones.

Being built from scratch, currently early-stage — most of the actual implementation still remaining.

## Why This Exists

I'm Manish, currently a Delivery Manager at Leucine (an AI-for-pharma SaaS company), managing MES/DMS/LMS/QMS implementations for enterprise pharma clients (Ascent, Hetero Labs, and others). I'm executing a 50-day plan (July 12 – Aug 31, 2026) targeting a role switch into a Founder's Office / APM-type role at Shadowfax, an Indian last-mile logistics company, via a CXO-level referral through a family contact.

ConstraintIQ is the anchor project for that transition:
- It's meant to demonstrate applied domain knowledge in last-mile logistics + ToC + forecasting, not just claimed familiarity with the concepts.
- Adding it to my resume is estimated to raise my Shadowfax APM fit assessment from roughly 60–63% to 70–75%.
- It's built into the 45-day skill-prep track (domain knowledge, tech-tradeoff discussion ability, PRD drafting) rather than run as a separate parallel workstream.

## How to Frame It (important — carries through to resume, interviews, and any docs generated from this project)

- Describe it as a **"predictive analytics prototype"** or **"proof-of-concept for constraint-migration detection"** — never as a live/production application. It isn't one, and overclaiming here would backfire in interviews.
- Be **proactively transparent about synthetic data** — this is a credibility asset, not a weakness to hide. State clearly that the data is synthetic and explain why (no access to a real last-mile network's operational data), rather than letting it surface as a gotcha.

## Scope

- 2 hubs, 6–8 zones
- Synthetic data (no real operational data source)
- Core technical combination: Theory of Constraints logic (bottleneck identification / constraint modeling) + ML-based demand forecasting, aimed at predicting constraint migration ahead of time rather than reactively

## Current Status (as of Aug 2026)

Early stage. Most of the build — synthetic data generation, the ToC constraint-modeling logic, the forecasting layer, and tying them together into a working detection pipeline — is still ahead. Treat this as a from-scratch build, not a refactor of existing code.

## Background That Informs This Project

- Domain background comes from pharma MES/DMS/LMS/QMS delivery work, not logistics-native experience — ConstraintIQ is explicitly the vehicle for building last-mile logistics domain credibility, so don't assume prior logistics-specific implementation experience when making design decisions.
- Currently working through Goldratt's *The Goal* for ToC fundamentals, studying Shadowfax's IPO/investor materials, and going through an AI PM concepts reading list in parallel — decisions in this project should be explainable in ToC terms since that's the framing being actively learned and will need to hold up in conversation.
- Resume (LaTeX/Overleaf, Jake's Resume template) is being updated to target Founder's Office and APM roles, with additions covering the delivery role across DMS/LMS/QMS and a separate MES Duplication Tool (React + TypeScript) already built.

## Tooling Preferences

- Comfortable with JavaScript/TypeScript tooling; also works with MongoDB/JSON data structures and API development.
- No language/stack has been locked in specifically for ConstraintIQ yet — this should be an early decision to make explicitly (e.g., Python is the more conventional choice for the ML forecasting piece; confirm before assuming).
- Prefers polished, presentable outputs generally — worth keeping in mind for anything meant to eventually go in front of Shadowfax (e.g., a clean write-up or demo, not just raw scripts).

## Working Style Notes

- Prefers direct, honest feedback over cheerleading — flag real risks or weak spots in the approach rather than smoothing them over.
- Keep any drafted written material (emails, messages) short — 2-3 lines.
