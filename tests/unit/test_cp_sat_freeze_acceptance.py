import pytest
from app.optimizer import cp_model, optimize_waves
from app.schemas import Application, ConstraintSet, Dependency, Portfolio

pytestmark = pytest.mark.skipif(
    cp_model is None, reason="OR-Tools not installed in this execution environment"
)


def locate(plan: dict, app_id: str) -> int:
    return next(w["wave"] for w in plan["waves"] if app_id in w["applications"])


def test_cp_sat_dependencies_and_scc_groups():
    portfolio = Portfolio(
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
                dependencies=[Dependency(target="a")],
                migration_effort=1,
                migration_risk=1,
                migration_cost=10,
            ),
        ]
    )
    constraints = ConstraintSet(
        max_waves=3,
        max_effort_per_wave=4,
        team_capacity_per_wave=4,
        max_risk_per_wave=4,
        budget_per_wave=100,
        max_critical_apps_per_wave=3,
    )
    plan = optimize_waves(portfolio, constraints, solver_mode="cp-sat")
    assert plan["status"] == "FEASIBLE" and plan["solver_used"] == "cp-sat"
    assert locate(plan, "a") == locate(plan, "b")
    assert locate(plan, "a") <= locate(plan, "c")


def test_cp_sat_budget_capacity_and_risk_limits():
    portfolio = Portfolio(
        applications=[
            Application(
                application_id=f"app-{i}",
                name=f"App {i}",
                migration_effort=4,
                migration_risk=4,
                migration_cost=60,
            )
            for i in range(3)
        ]
    )
    constraints = ConstraintSet(
        max_waves=3,
        max_effort_per_wave=5,
        team_capacity_per_wave=5,
        max_risk_per_wave=5,
        budget_per_wave=70,
        max_critical_apps_per_wave=3,
    )
    plan = optimize_waves(portfolio, constraints, solver_mode="cp-sat")
    assert plan["status"] == "FEASIBLE" and plan["solver_used"] == "cp-sat"
    assert len(plan["waves"]) == 3
    assert all(w["effort"] <= 5 for w in plan["waves"])
    assert all(w["risk_capacity_used"] <= 5 for w in plan["waves"])
    assert all(w["budget"] <= 70 for w in plan["waves"])


def test_cp_sat_deadline_region_and_compliance():
    portfolio = Portfolio(
        applications=[
            Application(
                application_id="regulated",
                name="Regulated",
                residency_region="IN",
                regulatory_tags=["PCI"],
                migration_effort=1,
                migration_risk=1,
                migration_cost=10,
            )
        ]
    )
    constraints = ConstraintSet(
        max_waves=3,
        max_effort_per_wave=5,
        team_capacity_per_wave=5,
        max_risk_per_wave=5,
        budget_per_wave=100,
        max_critical_apps_per_wave=1,
        deadlines={"regulated": 2},
        wave_regions={1: "EU", 2: "IN", 3: "IN"},
        compliance_allowed_waves={"PCI": [2]},
    )
    plan = optimize_waves(portfolio, constraints, solver_mode="cp-sat")
    assert plan["status"] == "FEASIBLE" and plan["solver_used"] == "cp-sat"
    assert locate(plan, "regulated") == 2


def test_cp_sat_infeasibility_is_reported_without_constraint_violation():
    portfolio = Portfolio(
        applications=[
            Application(
                application_id="too-expensive",
                name="Too Expensive",
                migration_effort=1,
                migration_risk=1,
                migration_cost=200,
            )
        ]
    )
    constraints = ConstraintSet(
        max_waves=2,
        max_effort_per_wave=5,
        team_capacity_per_wave=5,
        max_risk_per_wave=5,
        budget_per_wave=50,
        max_critical_apps_per_wave=1,
    )
    plan = optimize_waves(portfolio, constraints, solver_mode="cp-sat")
    assert plan["status"] == "NO FEASIBLE PLAN"
    assert plan["solver_used"] == "cp-sat"
    assert "budget" in plan["reason"].lower()
