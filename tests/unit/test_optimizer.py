from app.optimizer import optimize_waves
from app.pareto import pareto_frontier
from app.schemas import Application, ConstraintSet, Dependency, Portfolio


def portfolio() -> Portfolio:
    return Portfolio(
        applications=[
            Application(
                application_id="identity",
                name="Identity",
                migration_effort=2,
                migration_risk=2,
                migration_cost=100,
            ),
            Application(
                application_id="payments",
                name="Payments",
                dependencies=[Dependency(target="identity")],
                migration_effort=3,
                migration_risk=3,
                migration_cost=120,
            ),
            Application(
                application_id="billing",
                name="Billing",
                dependencies=[Dependency(target="payments")],
                migration_effort=3,
                migration_risk=2,
                migration_cost=130,
            ),
            Application(
                application_id="docs",
                name="Docs",
                migration_effort=2,
                migration_risk=1,
                migration_cost=80,
            ),
        ]
    )


def locate(plan: dict, app_id: str) -> int:
    return next(w["wave"] for w in plan["waves"] if app_id in w["applications"])


def test_dependency_order_capacity_and_budget():
    c = ConstraintSet(
        max_waves=4,
        max_effort_per_wave=6,
        team_capacity_per_wave=6,
        budget_per_wave=250,
        max_risk_per_wave=10,
        max_critical_apps_per_wave=2,
    )
    plan = optimize_waves(portfolio(), c, "balanced")
    assert plan["status"] == "FEASIBLE"
    assert (
        locate(plan, "identity") <= locate(plan, "payments") <= locate(plan, "billing")
    )
    assert all(w["effort"] <= 6 for w in plan["waves"])
    assert all(w["budget"] <= 250 for w in plan["waves"])


def test_scc_grouping_and_together_constraint():
    p = Portfolio(
        applications=[
            Application(
                application_id="a",
                name="A",
                dependencies=[Dependency(target="b")],
                migration_effort=1,
                migration_risk=1,
                migration_cost=10,
            ),
            Application(
                application_id="b",
                name="B",
                dependencies=[Dependency(target="a")],
                migration_effort=1,
                migration_risk=1,
                migration_cost=10,
            ),
            Application(
                application_id="c",
                name="C",
                migration_effort=1,
                migration_risk=1,
                migration_cost=10,
            ),
        ]
    )
    plan = optimize_waves(
        p,
        ConstraintSet(
            max_waves=3,
            max_effort_per_wave=5,
            team_capacity_per_wave=5,
            max_risk_per_wave=5,
            budget_per_wave=100,
            max_critical_apps_per_wave=3,
        ),
        "risk",
    )
    assert plan["status"] == "FEASIBLE"
    assert locate(plan, "a") == locate(plan, "b")


def test_infeasible_plan_detection():
    p = Portfolio(
        applications=[
            Application(
                application_id="huge",
                name="Huge",
                migration_effort=20,
                migration_risk=1,
                migration_cost=10,
            )
        ]
    )
    c = ConstraintSet(
        max_waves=2,
        max_effort_per_wave=5,
        team_capacity_per_wave=5,
        max_risk_per_wave=5,
        budget_per_wave=100,
        max_critical_apps_per_wave=1,
    )
    plan = optimize_waves(p, c)
    assert plan["status"] == "NO FEASIBLE PLAN"
    assert "cannot fit" in plan["reason"]


def test_earliest_deadline_region_compliance_and_maintenance():
    p = Portfolio(
        applications=[
            Application(
                application_id="a",
                name="A",
                migration_effort=1,
                migration_risk=1,
                migration_cost=10,
                residency_region="IN",
                regulatory_tags=["PCI"],
                maintenance_tag="weekend",
            )
        ]
    )
    c = ConstraintSet(
        max_waves=4,
        max_effort_per_wave=5,
        team_capacity_per_wave=5,
        max_risk_per_wave=5,
        budget_per_wave=100,
        max_critical_apps_per_wave=1,
        earliest_wave={"a": 2},
        deadlines={"a": 3},
        wave_regions={2: "IN", 3: "EU"},
        compliance_allowed_waves={"PCI": [2, 3]},
        maintenance_allowed_waves={"weekend": [2, 4]},
    )
    plan = optimize_waves(p, c)
    assert plan["status"] == "FEASIBLE"
    assert locate(plan, "a") == 2


def test_pareto_frontier_contains_nondominated_plans():
    c = ConstraintSet(
        max_waves=4,
        max_effort_per_wave=6,
        team_capacity_per_wave=6,
        budget_per_wave=250,
        max_risk_per_wave=10,
        max_critical_apps_per_wave=2,
    )
    out = pareto_frontier(portfolio(), c)
    assert out["plans_considered"] >= 1
    assert len(out["frontier"]) >= 1
