from __future__ import annotations

from itertools import product

from .optimizer import optimize_waves
from .schemas import ConstraintSet, ObjectiveWeights, Portfolio

MINIMIZE = (
    "capital_frontload_index",
    "execution_risk_early_exposure",
    "operational_risk_delay_index",
    "duration_waves",
)
MAXIMIZE = ("technical_debt_reduction_priority", "modernization_value_priority")


def _dominates(a: dict, b: dict) -> bool:
    no_worse = all(a[k] <= b[k] for k in MINIMIZE) and all(a[k] >= b[k] for k in MAXIMIZE)
    strictly_better = any(a[k] < b[k] for k in MINIMIZE) or any(a[k] > b[k] for k in MAXIMIZE)
    return no_worse and strictly_better


def _signature(plan: dict) -> tuple:
    return tuple((w["wave"], tuple(sorted(w["applications"]))) for w in plan.get("waves", []))


def _weight_sweep(limit: int = 30) -> list[ObjectiveWeights]:
    # Sparse simplex-like sweep: broad enough to create alternatives without a combinatorial grid.
    raw: list[ObjectiveWeights] = []
    levels = (0.0, 0.25, 0.5, 0.75, 1.0)
    for cost, execution, operational, debt in product(levels, repeat=4):
        used = cost + execution + operational + debt
        value = 1.0 - used
        if value < -1e-9 or value > 1.0:
            continue
        if abs(cost + execution + operational + debt + value - 1.0) > 1e-9:
            continue
        raw.append(
            ObjectiveWeights(
                cost=cost,
                execution_risk=execution,
                operational_risk_reduction=operational,
                technical_debt_reduction=debt,
                modernization_value=max(0.0, value),
            )
        )
    # Deterministic spread across the list plus balanced point.
    if len(raw) <= limit:
        return raw
    step = (len(raw) - 1) / (limit - 1)
    return [raw[round(i * step)] for i in range(limit)]


def pareto_frontier(
    portfolio: Portfolio,
    constraints: ConstraintSet | None = None,
    solver_mode: str = "auto",
    max_candidates: int = 30,
) -> dict:
    candidates: list[dict] = []
    seen: set[tuple] = set()
    attempted = 0
    presets = [
        ("Lowest execution risk", "minimize_execution_risk", None),
        ("Reduce operational risk", "reduce_operational_risk", None),
        ("Lowest cost exposure", "cost", None),
        ("Highest debt reduction priority", "debt", None),
        ("Highest modernization value", "value", None),
        ("Balanced", "balanced_risk", None),
    ]
    jobs = presets + [
        (f"Weighted {i + 1}", "weighted", w) for i, w in enumerate(_weight_sweep(max_candidates))
    ]
    for label, objective, weights in jobs:
        attempted += 1
        plan = optimize_waves(portfolio, constraints, objective, weights, solver_mode=solver_mode)
        if plan.get("status") != "FEASIBLE":
            continue
        sig = _signature(plan)
        if sig in seen:
            continue
        seen.add(sig)
        plan["candidate_label"] = label
        candidates.append(plan)
    frontier = [
        p
        for p in candidates
        if not any(
            _dominates(other["metrics"], p["metrics"]) for other in candidates if other is not p
        )
    ]
    return {
        "plans_attempted": attempted,
        "plans_considered": len(candidates),
        "unique_candidates": len(candidates),
        "duplicate_candidates_removed": attempted - len(candidates),
        "frontier_count": len(frontier),
        "frontier": frontier,
        "objective_directions": {
            **{k: "minimize" for k in MINIMIZE},
            **{k: "maximize" for k in MAXIMIZE},
        },
        "axes_note": "True non-dominance over cost-frontloading, execution-risk exposure, operational-risk delay, debt-reduction priority, modernization-value priority and duration. Input migration costs remain estimates.",
    }
