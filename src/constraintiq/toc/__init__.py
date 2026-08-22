"""Theory of Constraints layer — the core contribution of ConstraintIQ.

`constraint.py` identifies the current binding constraint (the resource whose utilization is
highest / first to hit its ceiling). `migration.py` takes demand forecasts and projects when
and where the binding constraint will shift next.
"""
