import pytest
from app.architecture import generate_architecture
from app.assessment import assess_portfolio, dimensions
from app.cost_model import CostAssumptions, estimate_cost
from app.optimizer import cp_model, optimize_waves
from app.pareto import _dominates, pareto_frontier
from app.risk_model import (
    availability_complexity,
    current_operational_risk,
    migration_execution_risk,
)
from app.schemas import Application, ConstraintSet, Dependency, Portfolio, Strategy
from app.sensitivity import run_sensitivity
from app.simulation import simulate_plan


def assess(app: Application):
    return assess_portfolio(Portfolio(applications=[app]))[0]


def test_6r_archetypes_have_semantic_rankings():
    obsolete = Application(
        application_id="a",
        name="obsolete",
        business_value=1,
        business_criticality="low",
        technical_debt_score=9,
        usage_level=1,
        change_frequency=1,
        redundancy_score=9,
        commodity_fit=8,
        replacement_fit=8,
        test_coverage=20,
    )
    modern = Application(
        application_id="b",
        name="modern",
        business_value=5,
        technical_debt_score=1,
        usage_level=7,
        change_frequency=4,
        test_coverage=90,
        team_skill_level=9,
        deployment_model="container",
        migration_risk=2,
    )
    legacy = Application(
        application_id="c",
        name="legacy",
        business_value=10,
        business_criticality="high",
        technical_debt_score=9,
        usage_level=9,
        change_frequency=9,
        test_coverage=85,
        team_skill_level=8,
        scalability_requirement=9,
        runtime_version="legacy",
        migration_risk=5,
    )
    core = Application(
        application_id="d",
        name="core",
        business_value=9,
        business_criticality="critical",
        technical_debt_score=8,
        usage_level=10,
        change_frequency=3,
        test_coverage=10,
        team_skill_level=3,
        availability_requirement=99.99,
        integration_count=8,
        migration_risk=9,
    )
    commodity = Application(
        application_id="e",
        name="commodity",
        business_value=5,
        technical_debt_score=9,
        commodity_fit=10,
        replacement_fit=10,
        test_coverage=40,
        migration_risk=4,
    )
    platform = Application(
        application_id="f",
        name="platform",
        business_value=7,
        technical_debt_score=4,
        change_frequency=4,
        test_coverage=70,
        team_skill_level=7,
        scalability_requirement=8,
        migration_risk=3,
        deployment_model="vm",
    )
    assert assess(obsolete)["recommendation"] in {"Retire", "Replace"}
    assert assess(modern)["recommendation"] == "Rehost"
    assert assess(platform)["recommendation"] == "Replatform"
    assert assess(legacy)["scores"]["Refactor"] > assess(legacy)["scores"]["Rehost"]
    assert assess(core)["scores"]["Retain"] >= assess(core)["scores"]["Refactor"]
    assert assess(commodity)["recommendation"] == "Replace"


def test_availability_complexity_is_monotonic():
    values = [availability_complexity(x) for x in (99.0, 99.9, 99.99)]
    assert values == sorted(values)
    assert (
        dimensions(
            Application(application_id="x", name="x", availability_requirement=99.99)
        )["migration"]
        >= dimensions(
            Application(application_id="y", name="y", availability_requirement=99.0)
        )["migration"]
    )


def test_operational_and_execution_risk_are_distinct():
    unstable = Application(
        application_id="o",
        name="o",
        technical_debt_score=10,
        incident_frequency=10,
        migration_risk=1,
        test_coverage=90,
        team_skill_level=9,
    )
    hard_change = Application(
        application_id="m",
        name="m",
        technical_debt_score=2,
        incident_frequency=0,
        migration_risk=9,
        test_coverage=5,
        team_skill_level=2,
        availability_requirement=99.99,
        integration_count=6,
    )
    assert current_operational_risk(unstable) > current_operational_risk(hard_change)
    assert migration_execution_risk(hard_change) > migration_execution_risk(unstable)


def test_minimize_execution_risk_does_not_put_high_risk_before_low_when_capacity_separates():
    p = Portfolio(
        applications=[
            Application(
                application_id="high", name="high", migration_risk=9, migration_effort=1
            ),
            Application(
                application_id="low", name="low", migration_risk=1, migration_effort=1
            ),
        ]
    )
    c = ConstraintSet(
        max_waves=2,
        max_effort_per_wave=1,
        team_capacity_per_wave=1,
        max_risk_per_wave=10,
        budget_per_wave=100000,
        max_critical_apps_per_wave=2,
    )
    plan = optimize_waves(p, c, "minimize_execution_risk", solver_mode="fallback")
    waves = {a: w["wave"] for w in plan["waves"] for a in w["applications"]}
    assert waves["low"] <= waves["high"]


def test_scc_cannot_be_split():
    p = Portfolio(
        applications=[
            Application(
                application_id="a",
                name="a",
                dependencies=[Dependency(target="b")],
                migration_risk=1,
            ),
            Application(
                application_id="b",
                name="b",
                dependencies=[Dependency(target="c")],
                migration_risk=1,
            ),
            Application(
                application_id="c",
                name="c",
                dependencies=[Dependency(target="a")],
                migration_risk=1,
            ),
        ]
    )
    c = ConstraintSet(
        max_waves=3,
        max_effort_per_wave=30,
        team_capacity_per_wave=30,
        max_risk_per_wave=10,
        budget_per_wave=100000,
        max_critical_apps_per_wave=3,
    )
    plan = optimize_waves(p, c, solver_mode="fallback")
    assert {"a", "b", "c"} in [set(g) for g in plan["coupled_groups"]]
    wave = {a: w["wave"] for w in plan["waves"] for a in w["applications"]}
    assert len({wave["a"], wave["b"], wave["c"]}) == 1


def test_infeasible_explanation_contains_capacity_hint():
    p = Portfolio(
        applications=[
            Application(
                application_id="a", name="a", migration_effort=20, migration_risk=1
            )
        ]
    )
    c = ConstraintSet(
        max_waves=1,
        max_effort_per_wave=5,
        team_capacity_per_wave=5,
        max_risk_per_wave=10,
        budget_per_wave=100000,
        max_critical_apps_per_wave=2,
    )
    plan = optimize_waves(p, c, solver_mode="fallback")
    assert plan["status"] == "NO FEASIBLE PLAN" and "effort" in plan["reason"]


def test_pareto_dominance_directions_and_deduplication():
    a = {
        "capital_frontload_index": 1,
        "execution_risk_early_exposure": 1,
        "operational_risk_delay_index": 1,
        "duration_waves": 1,
        "technical_debt_reduction_priority": 5,
        "modernization_value_priority": 5,
    }
    b = {
        "capital_frontload_index": 2,
        "execution_risk_early_exposure": 2,
        "operational_risk_delay_index": 2,
        "duration_waves": 2,
        "technical_debt_reduction_priority": 4,
        "modernization_value_priority": 4,
    }
    assert _dominates(a, b) and not _dominates(b, a)
    p = Portfolio(
        applications=[
            Application(
                application_id=f"a{i}",
                name=f"a{i}",
                migration_risk=1 + i,
                migration_effort=1,
                migration_cost=100 * (i + 1),
                technical_debt_score=2 + i,
                business_value=8 - i,
            )
            for i in range(4)
        ]
    )
    c = ConstraintSet(
        max_waves=4,
        max_effort_per_wave=2,
        team_capacity_per_wave=2,
        max_risk_per_wave=10,
        budget_per_wave=1000,
        max_critical_apps_per_wave=4,
    )
    out = pareto_frontier(p, c, solver_mode="fallback", max_candidates=20)
    assert (
        out["plans_attempted"] >= 20
        and out["unique_candidates"] <= out["plans_attempted"]
    )
    assert all(
        not any(
            _dominates(o["metrics"], q["metrics"])
            for o in out["frontier"]
            if o is not q
        )
        for q in out["frontier"]
    )


def test_cost_override_changes_estimate():
    app = Application(application_id="c", name="c", peak_traffic_rps=100, database="pg")
    low = estimate_cost(
        app, Strategy.replatform, CostAssumptions(compute_per_rps_month=0.1)
    )
    high = estimate_cost(
        app, Strategy.replatform, CostAssumptions(compute_per_rps_month=2.0)
    )
    assert high["monthly_run_cost_estimate"] > low["monthly_run_cost_estimate"]


def test_architecture_changes_with_requirements_and_avoids_default_microservices():
    simple = Application(
        application_id="s",
        name="s",
        integration_count=1,
        change_frequency=2,
        business_criticality="low",
    )
    critical = Application(
        application_id="h",
        name="h",
        integration_count=5,
        availability_requirement=99.99,
        business_criticality="critical",
        rpo_hours=0.25,
        rto_hours=0.5,
        data_sensitivity="restricted",
        database="shared-core",
    )
    simple_arch = generate_architecture(simple, Strategy.refactor)
    critical_arch = generate_architecture(critical, Strategy.refactor)
    assert simple_arch["pattern"] == "modular monolith"
    assert {
        "Failure-Isolated Multi-Zone Pattern",
        "Continuous Replication / Data Protection",
        "Audit Logging + Segmented Network",
    } <= {c["label"] for c in critical_arch["components"]}
    assert critical_arch["warnings"]


def test_sensitivity_is_labeled_as_stability_not_probability():
    app = Application(
        application_id="s",
        name="s",
        business_value=7,
        technical_debt_score=6,
        change_frequency=7,
        scalability_requirement=7,
    )
    result = run_sensitivity(Portfolio(applications=[app]), samples=20)[0]
    assert "not Bayesian probabilities" in result["method"]
    assert abs(sum(result["recommendation_distribution"].values()) - 1.0) < 1e-6


def test_simulation_reports_delay_distribution():
    a = Application(application_id="a", name="a", migration_risk=9, test_coverage=10)
    b = Application(
        application_id="b",
        name="b",
        dependencies=[Dependency(target="a")],
        migration_risk=5,
        test_coverage=30,
    )
    result = simulate_plan(
        Portfolio(applications=[a, b]),
        [{"wave": 1, "applications": ["a"]}, {"wave": 2, "applications": ["b"]}],
        runs=50,
        seed=1,
    )
    assert (
        "SIMULATED" in result["method"]
        and result["p90_completion_delay_weeks"]
        >= result["median_completion_delay_weeks"]
    )


@pytest.mark.skipif(
    cp_model is None, reason="OR-Tools not installed in this execution environment"
)
def test_explicit_cp_sat_path_reports_cp_sat():
    p = Portfolio(
        applications=[Application(application_id="a", name="a", migration_risk=1)]
    )
    plan = optimize_waves(
        p, ConstraintSet(max_waves=2, max_risk_per_wave=10), solver_mode="cp-sat"
    )
    assert plan["status"] == "FEASIBLE" and plan["solver_used"] == "cp-sat"


def test_explicit_cp_sat_mode_never_silently_falls_back():
    p = Portfolio(
        applications=[Application(application_id="a2", name="a2", migration_risk=1)]
    )
    plan = optimize_waves(
        p, ConstraintSet(max_waves=2, max_risk_per_wave=10), solver_mode="cp-sat"
    )
    if cp_model is None:
        assert (
            plan["status"] == "SOLVER UNAVAILABLE" and plan["solver_used"] == "cp-sat"
        )
    else:
        assert plan["status"] == "FEASIBLE" and plan["solver_used"] == "cp-sat"


@pytest.mark.skipif(
    cp_model is None,
    reason="OR-Tools not installed in this execution environment",
)
def test_auto_falls_back_only_when_cp_sat_is_indeterminate(
    monkeypatch,
):
    from app import optimizer as optimizer_module

    portfolio = Portfolio(
        applications=[
            Application(
                application_id="auto-fallback",
                name="Auto Fallback",
                migration_risk=1,
            )
        ]
    )

    constraints = ConstraintSet(
        max_waves=2,
        max_risk_per_wave=10,
    )

    def indeterminate(*args, **kwargs):
        raise optimizer_module.CpSatIndeterminateError("UNKNOWN")

    monkeypatch.setattr(
        optimizer_module,
        "_solve_ortools",
        indeterminate,
    )

    plan = optimizer_module.optimize_waves(
        portfolio,
        constraints,
        solver_mode="auto",
    )

    assert plan["status"] == "FEASIBLE"
    assert plan["solver_used"] == "deterministic_fallback"
    assert "UNKNOWN" in plan["solver_note"]


@pytest.mark.skipif(
    cp_model is None,
    reason="OR-Tools not installed in this execution environment",
)
def test_explicit_cp_sat_reports_indeterminate_without_fallback(
    monkeypatch,
):
    from app import optimizer as optimizer_module

    portfolio = Portfolio(
        applications=[
            Application(
                application_id="explicit-cp",
                name="Explicit CP",
                migration_risk=1,
            )
        ]
    )

    constraints = ConstraintSet(
        max_waves=2,
        max_risk_per_wave=10,
    )

    def indeterminate(*args, **kwargs):
        raise optimizer_module.CpSatIndeterminateError("UNKNOWN")

    monkeypatch.setattr(
        optimizer_module,
        "_solve_ortools",
        indeterminate,
    )

    plan = optimizer_module.optimize_waves(
        portfolio,
        constraints,
        solver_mode="cp-sat",
    )

    assert plan["status"] == "SOLVER INDETERMINATE"
    assert plan["solver_used"] == "cp-sat"
    assert "UNKNOWN" in plan["reason"]


@pytest.mark.skipif(
    cp_model is None,
    reason="OR-Tools not installed in this execution environment",
)
def test_cp_sat_resource_scaling_matches_real_capacity():
    # These cases deliberately exceed a capacity by an amount
    # that the old int(...) CP-SAT encoding could truncate away.

    # Risk
    risk_portfolio = Portfolio(
        applications=[
            Application(
                application_id="risk-a",
                name="Risk A",
                migration_risk=5.00005,
            ),
            Application(
                application_id="risk-b",
                name="Risk B",
                migration_risk=5.00005,
            ),
        ]
    )

    risk_plan = optimize_waves(
        risk_portfolio,
        ConstraintSet(
            max_waves=1,
            max_risk_per_wave=10.0,
        ),
        solver_mode="cp-sat",
    )

    assert risk_plan["status"] == "NO FEASIBLE PLAN"

    # Effort
    effort_portfolio = Portfolio(
        applications=[
            Application(
                application_id="effort-a",
                name="Effort A",
                migration_effort=5.00005,
                migration_risk=1,
            ),
            Application(
                application_id="effort-b",
                name="Effort B",
                migration_effort=5.00005,
                migration_risk=1,
            ),
        ]
    )

    effort_plan = optimize_waves(
        effort_portfolio,
        ConstraintSet(
            max_waves=1,
            max_effort_per_wave=10.0,
            team_capacity_per_wave=10.0,
        ),
        solver_mode="cp-sat",
    )

    assert effort_plan["status"] == "NO FEASIBLE PLAN"

    # Cost
    cost_portfolio = Portfolio(
        applications=[
            Application(
                application_id="cost-a",
                name="Cost A",
                migration_risk=1,
                migration_cost=5000.00005,
            ),
            Application(
                application_id="cost-b",
                name="Cost B",
                migration_risk=1,
                migration_cost=5000.00005,
            ),
        ]
    )

    cost_plan = optimize_waves(
        cost_portfolio,
        ConstraintSet(
            max_waves=1,
            budget_per_wave=10000.0,
        ),
        solver_mode="cp-sat",
    )

    assert cost_plan["status"] == "NO FEASIBLE PLAN"
