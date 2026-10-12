from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any, Iterable

import networkx as nx

from .graph_engine import analyze_graph, build_graph
from .risk_model import current_operational_risk, migration_execution_risk
from .schemas import Application, ConstraintSet, ObjectiveWeights, Portfolio

cp_model: Any

try:
    from ortools.sat.python import cp_model as _cp_model
except ImportError:
    cp_model = None
else:
    cp_model = _cp_model


class OptimizationError(ValueError):
    pass


class CpSatIndeterminateError(RuntimeError):
    """CP-SAT stopped without proving feasibility or infeasibility."""

    def __init__(self, status_name: str):
        self.status_name = status_name
        super().__init__(f"CP-SAT returned {status_name} before finding a feasible solution")


@dataclass
class Group:
    gid: str
    members: list[Application]
    effort: float
    execution_risk: float
    risk_capacity: float
    operational_risk: float
    cost: float
    critical_count: int
    debt: float
    value: float


class DSU:
    def __init__(self, items: Iterable[str]):
        self.parent = {x: x for x in items}

    def find(self, x: str) -> str:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _build_groups(
    portfolio: Portfolio, c: ConstraintSet
) -> tuple[list[Group], list[tuple[str, str, bool]]]:
    ids = {a.application_id for a in portfolio.applications}
    dsu = DSU(ids)
    graph = build_graph(portfolio)
    analysis = analyze_graph(portfolio)
    gm = {m["application_id"]: m for m in analysis["metrics"]}
    for comp in nx.strongly_connected_components(graph):
        comp = list(comp)
        for item in comp[1:]:
            dsu.union(comp[0], item)
    for together in c.together:
        unknown = set(together) - ids
        if unknown:
            raise OptimizationError(f"unknown together references: {sorted(unknown)}")
        for item in together[1:]:
            dsu.union(together[0], item)
    by_root: dict[str, list[Application]] = defaultdict(list)
    for app in portfolio.applications:
        by_root[dsu.find(app.application_id)].append(app)
    groups: list[Group] = []
    app_group: dict[str, str] = {}
    for idx, (_, members) in enumerate(
        sorted(by_root.items(), key=lambda kv: min(a.application_id for a in kv[1]))
    ):
        gid = f"g{idx:04d}"
        for app in members:
            app_group[app.application_id] = gid
        groups.append(
            Group(
                gid=gid,
                members=sorted(members, key=lambda a: a.application_id),
                effort=sum(a.migration_effort for a in members),
                execution_risk=sum(
                    migration_execution_risk(a, gm.get(a.application_id)) for a in members
                ),
                risk_capacity=sum(a.migration_risk for a in members),
                operational_risk=sum(
                    current_operational_risk(a, gm.get(a.application_id)) for a in members
                ),
                cost=sum(a.migration_cost for a in members),
                critical_count=sum(a.business_criticality.value == "critical" for a in members),
                debt=sum(a.technical_debt_score for a in members),
                value=sum(a.business_value for a in members),
            )
        )
    precedence: set[tuple[str, str, bool]] = set()
    for before, after in c.precedence:
        if before not in ids or after not in ids:
            raise OptimizationError(f"unknown precedence reference: {(before, after)}")
        ga, gb = app_group[before], app_group[after]
        if ga == gb:
            raise OptimizationError(
                f"precedence conflicts with coupled group: {before} before {after}"
            )
        precedence.add((ga, gb, True))
    if c.enforce_dependencies:
        for source, target in graph.edges:
            gs, gt = app_group[source], app_group[target]
            if gs != gt:
                precedence.add((gt, gs, False))
    dag = nx.DiGraph()
    dag.add_nodes_from(g.gid for g in groups)
    dag.add_edges_from((a, b) for a, b, _ in precedence)
    if not nx.is_directed_acyclic_graph(dag):
        raise OptimizationError(f"precedence constraints contain a cycle: {nx.find_cycle(dag)[:5]}")
    return groups, sorted(precedence)


def _allowed_waves(group: Group, c: ConstraintSet) -> list[int]:
    allowed = set(range(1, c.max_waves + 1))
    for app in group.members:
        earliest = c.earliest_wave.get(app.application_id, 1)
        deadline = c.deadlines.get(app.application_id, c.max_waves)
        allowed &= set(range(max(1, earliest), min(c.max_waves, deadline) + 1))
        if app.residency_region and c.wave_regions:
            allowed &= {w for w, region in c.wave_regions.items() if region == app.residency_region}
        for tag in app.regulatory_tags:
            if tag in c.compliance_allowed_waves:
                allowed &= set(c.compliance_allowed_waves[tag])
        if app.maintenance_tag and app.maintenance_tag in c.maintenance_allowed_waves:
            allowed &= set(c.maintenance_allowed_waves[app.maintenance_tag])
    return sorted(w for w in allowed if 1 <= w <= c.max_waves)


def _validate_group_caps(groups: list[Group], c: ConstraintSet) -> None:
    for g in groups:
        failures = []
        if g.effort > c.max_effort_per_wave:
            failures.append(f"effort {g.effort:.2f}>{c.max_effort_per_wave}")
        if g.effort > c.team_capacity_per_wave:
            failures.append(f"team capacity {g.effort:.2f}>{c.team_capacity_per_wave}")
        if g.risk_capacity > c.max_risk_per_wave:
            failures.append(
                f"declared execution-risk capacity {g.risk_capacity:.2f}>{c.max_risk_per_wave}"
            )
        if g.cost > c.budget_per_wave:
            failures.append(f"budget {g.cost:.2f}>{c.budget_per_wave}")
        if g.critical_count > c.max_critical_apps_per_wave:
            failures.append(f"critical apps {g.critical_count}>{c.max_critical_apps_per_wave}")
        if not _allowed_waves(g, c):
            failures.append(
                "no wave satisfies earliest/deadline/region/compliance/maintenance restrictions"
            )
        if failures:
            names = ", ".join(a.application_id for a in g.members)
            raise OptimizationError(
                f"coupled group [{names}] cannot fit any wave: {'; '.join(failures)}"
            )


def _objective_name(name: str) -> str:
    return {"risk": "balanced_risk", "balanced": "balanced_risk"}.get(name, name)


def _priority(g: Group, objective: str, weights: ObjectiveWeights | None = None) -> float:
    objective = _objective_name(objective)
    if objective == "minimize_execution_risk":
        return 10.0 * len(g.members) - g.execution_risk
    if objective == "reduce_operational_risk":
        return g.operational_risk
    if objective == "cost":
        return -g.cost
    if objective == "debt":
        return g.debt
    if objective == "value":
        return g.value
    if objective == "weighted" and weights is not None:
        return (
            -weights.cost * g.cost / 10000.0
            - weights.execution_risk * g.execution_risk
            + weights.operational_risk_reduction * g.operational_risk
            + weights.technical_debt_reduction * g.debt
            + weights.modernization_value * g.value
        )
    return (
        0.42 * g.operational_risk
        + 0.33 * (10.0 * len(g.members) - g.execution_risk)
        + 0.15 * g.debt
        + 0.10 * g.value
    )


def _wave_metrics(assign: dict[str, int], groups: list[Group], max_waves: int) -> list[dict]:
    waves = []
    for w in range(1, max_waves + 1):
        selected = [g for g in groups if assign.get(g.gid) == w]
        if not selected:
            continue
        waves.append(
            {
                "wave": w,
                "applications": [a.application_id for g in selected for a in g.members],
                "groups": [g.gid for g in selected],
                "effort": round(sum(g.effort for g in selected), 2),
                "migration_execution_risk": round(sum(g.execution_risk for g in selected), 2),
                "risk_capacity_used": round(sum(g.risk_capacity for g in selected), 2),
                "current_operational_risk": round(sum(g.operational_risk for g in selected), 2),
                "risk": round(sum(g.risk_capacity for g in selected), 2),
                "budget": round(sum(g.cost for g in selected), 2),
                "critical_apps": sum(g.critical_count for g in selected),
            }
        )
    return waves


def _wave_explanations(
    waves: list[dict],
    assign: dict[str, int],
    groups: list[Group],
    precedence: list[tuple[str, str, bool]],
    c: ConstraintSet,
) -> None:
    by_gid = {g.gid: g for g in groups}
    incoming: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for before, after, strict in precedence:
        incoming[after].append((before, strict))
    for wave in waves:
        reasons: list[str] = []
        for gid in wave["groups"]:
            group = by_gid[gid]
            names = ", ".join(a.application_id for a in group.members)
            if len(group.members) > 1:
                reasons.append(
                    f"{names} move together because SCC and/or explicit coupling constraints merged them."
                )
            for before, strict in incoming[gid]:
                reasons.append(
                    f"{names} is {'strictly after' if strict else 'not before'} prerequisite group {before} in wave {assign[before]}."
                )
            for app in group.members:
                if c.earliest_wave.get(app.application_id) == wave["wave"]:
                    reasons.append(f"{app.application_id} reaches its earliest allowed wave here.")
                if c.deadlines.get(app.application_id) == wave["wave"]:
                    reasons.append(
                        f"{app.application_id} is placed by its latest permitted deadline wave."
                    )
                if (
                    app.residency_region
                    and c.wave_regions.get(wave["wave"]) == app.residency_region
                ):
                    reasons.append(
                        f"{app.application_id} matches residency region {app.residency_region}."
                    )
        reasons.append(
            f"Wave utilization: effort {wave['effort']}/{min(c.max_effort_per_wave, c.team_capacity_per_wave)}, execution risk {wave['risk_capacity_used']}/{c.max_risk_per_wave}, budget {wave['budget']}/{c.budget_per_wave}."
        )
        wave["why"] = list(dict.fromkeys(reasons))


def _plan_metrics(assign: dict[str, int], groups: list[Group], max_waves: int) -> dict:
    execution_early = sum(g.execution_risk * (max_waves + 1 - assign[g.gid]) for g in groups)
    operational_delay = sum(g.operational_risk * assign[g.gid] for g in groups)
    debt_delay = sum(g.debt * assign[g.gid] for g in groups)
    value_delay = sum(g.value * assign[g.gid] for g in groups)
    capital_frontload = sum(g.cost * (max_waves + 1 - assign[g.gid]) for g in groups)
    debt_total = sum(g.debt for g in groups)
    value_total = sum(g.value for g in groups)
    return {
        "execution_risk_early_exposure": round(execution_early, 2),
        "operational_risk_delay_index": round(operational_delay, 2),
        "technical_debt_delay_index": round(debt_delay, 2),
        "business_value_delay_index": round(value_delay, 2),
        "technical_debt_reduction_priority": round(debt_total * (max_waves + 1) - debt_delay, 2),
        "modernization_value_priority": round(value_total * (max_waves + 1) - value_delay, 2),
        "capital_frontload_index": round(capital_frontload, 2),
        "total_migration_cost_estimate": round(sum(g.cost for g in groups), 2),
        "duration_waves": max(assign.values(), default=0),
        "label": "Estimated planning indicators. Execution risk and current operational risk are intentionally separate; costs are input estimates, not provider pricing.",
    }


def _validate_assignment(
    assign: dict[str, int],
    groups: list[Group],
    precedence: list[tuple[str, str, bool]],
    c: ConstraintSet,
) -> list[str]:
    errors: list[str] = []
    by_gid = {g.gid: g for g in groups}
    for before, after, strict in precedence:
        if (strict and assign[before] >= assign[after]) or (
            not strict and assign[before] > assign[after]
        ):
            errors.append(f"precedence violated: {before}->{after}")
    for g in groups:
        if assign[g.gid] not in _allowed_waves(g, c):
            errors.append(f"{g.gid} assigned to disallowed wave {assign[g.gid]}")
    for w in range(1, c.max_waves + 1):
        selected = [by_gid[gid] for gid, wave in assign.items() if wave == w]
        if sum(g.effort for g in selected) > c.max_effort_per_wave + 1e-9:
            errors.append(f"wave {w} effort capacity exceeded")
        if sum(g.effort for g in selected) > c.team_capacity_per_wave + 1e-9:
            errors.append(f"wave {w} team capacity exceeded")
        if sum(g.risk_capacity for g in selected) > c.max_risk_per_wave + 1e-9:
            errors.append(f"wave {w} execution-risk capacity exceeded")
        if sum(g.cost for g in selected) > c.budget_per_wave + 1e-9:
            errors.append(f"wave {w} budget exceeded")
        if sum(g.critical_count for g in selected) > c.max_critical_apps_per_wave:
            errors.append(f"wave {w} critical-app cap exceeded")
    return errors


def _solve_fallback(
    groups: list[Group],
    precedence: list[tuple[str, str, bool]],
    c: ConstraintSet,
    objective: str,
    weights: ObjectiveWeights | None,
) -> dict[str, int]:
    dag = nx.DiGraph()
    dag.add_nodes_from(g.gid for g in groups)
    dag.add_edges_from((a, b) for a, b, _ in precedence)
    by_gid = {g.gid: g for g in groups}
    indeg = dict(dag.in_degree())
    ready = [g for g, degree in indeg.items() if degree == 0]
    order: list[str] = []
    while ready:
        ready.sort(key=lambda gid: (-_priority(by_gid[gid], objective, weights), gid))
        gid = ready.pop(0)
        order.append(gid)
        for nxt in dag.successors(gid):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    assign: dict[str, int] = {}
    used = {
        w: {"effort": 0.0, "risk": 0.0, "cost": 0.0, "critical": 0}
        for w in range(1, c.max_waves + 1)
    }
    preds: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for before, after, strict in precedence:
        preds[after].append((before, strict))
    for gid in order:
        g = by_gid[gid]
        min_wave = max((assign[p] + int(strict) for p, strict in preds[gid]), default=1)
        for w in (x for x in _allowed_waves(g, c) if x >= min_wave):
            u = used[w]
            if (
                u["effort"] + g.effort
                <= min(c.max_effort_per_wave, c.team_capacity_per_wave) + 1e-9
                and u["risk"] + g.risk_capacity <= c.max_risk_per_wave + 1e-9
                and u["cost"] + g.cost <= c.budget_per_wave + 1e-9
                and u["critical"] + g.critical_count <= c.max_critical_apps_per_wave
            ):
                assign[gid] = w
                u["effort"] += g.effort
                u["risk"] += g.risk_capacity
                u["cost"] += g.cost
                u["critical"] += g.critical_count
                break
        else:
            raise OptimizationError(
                f"no feasible wave for group [{', '.join(a.application_id for a in g.members)}] after applying precedence, capacity, region/compliance, maintenance and deadline constraints"
            )
    return assign


def _infeasibility_hints(
    groups: list[Group], precedence: list[tuple[str, str, bool]], c: ConstraintSet
) -> list[str]:
    hints: list[str] = []
    totals = {
        "effort": (
            sum(g.effort for g in groups),
            c.max_waves * min(c.max_effort_per_wave, c.team_capacity_per_wave),
        ),
        "execution risk capacity": (
            sum(g.risk_capacity for g in groups),
            c.max_waves * c.max_risk_per_wave,
        ),
        "budget": (sum(g.cost for g in groups), c.max_waves * c.budget_per_wave),
        "critical-app slots": (
            sum(g.critical_count for g in groups),
            c.max_waves * c.max_critical_apps_per_wave,
        ),
    }
    for name, (required, available) in totals.items():
        if required > available + 1e-9:
            hints.append(
                f"total {name} requires {required:.2f} but all waves provide only {available:.2f}"
            )
    for g in groups:
        if not _allowed_waves(g, c):
            hints.append(
                f"group {g.gid} has no wave satisfying earliest/deadline/region/compliance/maintenance rules"
            )
    dag = nx.DiGraph()
    dag.add_nodes_from(g.gid for g in groups)
    dag.add_edges_from((a, b) for a, b, _ in precedence)
    depth = {n: 0 for n in dag.nodes}
    strict_lookup = {(a, b): strict for a, b, strict in precedence}
    for node in nx.topological_sort(dag):
        for nxt in dag.successors(node):
            depth[nxt] = max(depth[nxt], depth[node] + int(strict_lookup.get((node, nxt), False)))
    required_waves = 1 + max(depth.values(), default=0)
    if required_waves > c.max_waves:
        hints.append(
            f"strict precedence chain requires at least {required_waves} waves but max_waves={c.max_waves}"
        )
    return hints


_RESOURCE_SCALE = 10_000


def _resource_units(value: float) -> int:
    scaled = Decimal(str(value)) * _RESOURCE_SCALE
    return int(scaled.to_integral_value(rounding=ROUND_CEILING))


def _resource_limit(value: float) -> int:
    scaled = Decimal(str(value)) * _RESOURCE_SCALE
    return int(scaled.to_integral_value(rounding=ROUND_FLOOR))


def _cp_objective_term(
    g: Group,
    wave_var: Any,
    c: ConstraintSet,
    objective: str,
    weights: ObjectiveWeights | None,
    scale: int,
) -> Any:
    objective = _objective_name(objective)
    if objective == "minimize_execution_risk":
        return int(g.execution_risk * scale) * (c.max_waves + 1 - wave_var)
    if objective == "reduce_operational_risk":
        return int(g.operational_risk * scale) * wave_var
    if objective == "cost":
        return int(g.cost) * (c.max_waves + 1 - wave_var)
    if objective == "debt":
        return int(g.debt * scale) * wave_var
    if objective == "value":
        return int(g.value * scale) * wave_var
    if objective == "weighted" and weights is not None:
        return (
            int(weights.cost * g.cost / 100) * (c.max_waves + 1 - wave_var)
            + int(weights.execution_risk * g.execution_risk * scale) * (c.max_waves + 1 - wave_var)
            + int(weights.operational_risk_reduction * g.operational_risk * scale) * wave_var
            + int(weights.technical_debt_reduction * g.debt * scale) * wave_var
            + int(weights.modernization_value * g.value * scale) * wave_var
        )
    return (
        int(0.45 * g.operational_risk * scale) * wave_var
        + int(0.35 * g.execution_risk * scale) * (c.max_waves + 1 - wave_var)
        + int(0.10 * g.debt * scale) * wave_var
        + int(0.10 * g.value * scale) * wave_var
    )


def _solve_ortools(
    groups: list[Group],
    precedence: list[tuple[str, str, bool]],
    c: ConstraintSet,
    objective: str,
    weights: ObjectiveWeights | None,
) -> dict[str, int]:
    if cp_model is None:
        raise RuntimeError("OR-Tools unavailable")
    model = cp_model.CpModel()
    scale = 100
    wave = {g.gid: model.NewIntVar(1, c.max_waves, f"wave_{g.gid}") for g in groups}
    indicator = {}
    for g in groups:
        allowed = _allowed_waves(g, c)
        if not allowed:
            raise OptimizationError(f"group {g.gid} has no allowed waves")
        model.AddAllowedAssignments([wave[g.gid]], [[w] for w in allowed])
        for w in range(1, c.max_waves + 1):
            b = model.NewBoolVar(f"is_{g.gid}_{w}")
            indicator[g.gid, w] = b
            model.Add(wave[g.gid] == w).OnlyEnforceIf(b)
            model.Add(wave[g.gid] != w).OnlyEnforceIf(b.Not())
    for before, after, strict in precedence:
        model.Add(wave[before] < wave[after] if strict else wave[before] <= wave[after])
    for w in range(1, c.max_waves + 1):
        model.Add(
            sum(_resource_units(g.effort) * indicator[g.gid, w] for g in groups)
            <= _resource_limit(c.max_effort_per_wave)
        )
        model.Add(
            sum(_resource_units(g.effort) * indicator[g.gid, w] for g in groups)
            <= _resource_limit(c.team_capacity_per_wave)
        )
        model.Add(
            sum(_resource_units(g.risk_capacity) * indicator[g.gid, w] for g in groups)
            <= _resource_limit(c.max_risk_per_wave)
        )
        model.Add(
            sum(_resource_units(g.cost) * indicator[g.gid, w] for g in groups)
            <= _resource_limit(c.budget_per_wave)
        )
        model.Add(
            sum(g.critical_count * indicator[g.gid, w] for g in groups)
            <= c.max_critical_apps_per_wave
        )
    model.Minimize(
        sum(_cp_objective_term(g, wave[g.gid], c, objective, weights, scale) for g in groups)
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 12.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status == cp_model.INFEASIBLE:
        hints = _infeasibility_hints(groups, precedence, c)
        detail = (
            "; ".join(hints)
            if hints
            else "joint constraints conflict; no formal unsat core was computed"
        )
        raise OptimizationError(f"CP-SAT proved the model infeasible: {detail}")

    if status == cp_model.MODEL_INVALID:
        raise RuntimeError("CP-SAT rejected the generated model as invalid")

    if status == cp_model.UNKNOWN:
        raise CpSatIndeterminateError(solver.StatusName(status))

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise CpSatIndeterminateError(solver.StatusName(status))

    return {g.gid: int(solver.Value(wave[g.gid])) for g in groups}


def optimize_waves(
    portfolio: Portfolio,
    constraints: ConstraintSet | None = None,
    objective: str = "balanced_risk",
    objective_weights: ObjectiveWeights | None = None,
    solver_mode: str = "auto",
) -> dict:
    c = constraints or ConstraintSet()
    objective = _objective_name(objective)

    allowed = {
        "minimize_execution_risk",
        "reduce_operational_risk",
        "cost",
        "debt",
        "value",
        "balanced_risk",
        "weighted",
    }

    if objective not in allowed:
        raise OptimizationError("unsupported objective")

    if objective == "weighted" and objective_weights is None:
        objective_weights = ObjectiveWeights()

    if solver_mode not in {"auto", "cp-sat", "fallback"}:
        raise OptimizationError("unsupported solver mode")

    if solver_mode == "cp-sat" and cp_model is None:
        return {
            "status": "SOLVER UNAVAILABLE",
            "solver_used": "cp-sat",
            "reason": (
                "OR-Tools is not installed; explicit CP-SAT mode never silently falls back."
            ),
        }

    groups: list[Group] = []
    precedence: list[tuple[str, str, bool]] = []
    solver_note: str | None = None

    try:
        groups, precedence = _build_groups(portfolio, c)
        _validate_group_caps(groups, c)

        if solver_mode == "fallback" or cp_model is None:
            assign = _solve_fallback(
                groups,
                precedence,
                c,
                objective,
                objective_weights,
            )
            solver_used = "deterministic_fallback"

        else:
            try:
                assign = _solve_ortools(
                    groups,
                    precedence,
                    c,
                    objective,
                    objective_weights,
                )
                solver_used = "cp-sat"

            except CpSatIndeterminateError as exc:
                if solver_mode == "cp-sat":
                    return {
                        "status": "SOLVER INDETERMINATE",
                        "solver_used": "cp-sat",
                        "reason": str(exc),
                        "conflict_hints": [],
                    }

                solver_note = f"{exc}; auto mode used the deterministic fallback."

                assign = _solve_fallback(
                    groups,
                    precedence,
                    c,
                    objective,
                    objective_weights,
                )
                solver_used = "deterministic_fallback"

    except OptimizationError as exc:
        hints = _infeasibility_hints(groups, precedence, c) if groups else []

        attempted_solver = (
            "cp-sat"
            if cp_model is not None and solver_mode != "fallback"
            else "deterministic_fallback"
        )

        return {
            "status": "NO FEASIBLE PLAN",
            "reason": str(exc),
            "conflict_hints": hints,
            "solver_used": attempted_solver,
        }

    errors = _validate_assignment(
        assign,
        groups,
        precedence,
        c,
    )

    if errors:
        return {
            "status": "NO FEASIBLE PLAN",
            "reason": ("independent plan validation rejected candidate"),
            "validation_errors": errors,
            "solver_used": solver_used,
        }

    waves = _wave_metrics(
        assign,
        groups,
        c.max_waves,
    )

    _wave_explanations(
        waves,
        assign,
        groups,
        precedence,
        c,
    )

    result = {
        "status": "FEASIBLE",
        "objective": objective,
        "objective_weights": (objective_weights.model_dump() if objective_weights else None),
        "solver_used": solver_used,
        "solver": solver_used,
        "waves": waves,
        "metrics": _plan_metrics(
            assign,
            groups,
            c.max_waves,
        ),
        "coupled_groups": [
            [a.application_id for a in g.members] for g in groups if len(g.members) > 1
        ],
        "precedence_group_edges": [
            {
                "before": before,
                "after": after,
                "strict": strict,
            }
            for before, after, strict in precedence
        ],
        "validation_errors": [],
        "why": (
            "Assignment respects dependencies/SCC coupling, "
            "capacity, execution-risk, budget, criticality, "
            "residency/compliance, maintenance, earliest-wave "
            "and deadline constraints and is independently "
            "revalidated."
        ),
    }

    if solver_note is not None:
        result["solver_note"] = solver_note

    return result
