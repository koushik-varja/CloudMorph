from app.assessment import diagnoses
from app.generator import generate_portfolio
from app.importers import parse_portfolio_bytes
from app.scenarios import compare_scenarios
from app.schemas import Application, Portfolio, Scenario, Strategy
from app.security_analysis import assess_security
from app.simulation import simulate_plan
from app.technical_debt import calculate_technical_debt


def test_synthetic_generator_is_labeled_and_has_cycles():
    p = generate_portfolio(100, seed=7)
    assert p.synthetic is True
    assert all(a.synthetic for a in p.applications)
    assert len(p.applications) == 100
    assert sum(len(a.dependencies) for a in p.applications) > 50


def test_compose_parser_only_infers_available_fields():
    y = b"""services:\n  api:\n    image: example/api:1\n    depends_on: [db]\n    ports: [\"8080:8080\"]\n  db:\n    image: postgres:17\n"""
    p = parse_portfolio_bytes("compose.yaml", y, 5000)
    api = next(a for a in p.applications if a.application_id == "api")
    assert api.deployment_model == "container"
    assert api.dependencies[0].target == "db"
    assert (
        api.business_criticality.value == "medium"
    )  # default, not inferred from Compose


def test_kubernetes_parser_conservative():
    y = b"""apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: orders\nspec:\n  template:\n    spec:\n      containers:\n        - name: orders\n          image: example/orders:1\n"""
    p = parse_portfolio_bytes("orders.yaml", y, 5000)
    assert p.applications[0].deployment_model == "kubernetes"
    assert p.applications[0].business_value == 5


def test_calculated_technical_debt_and_diagnosis_have_evidence():
    p = Portfolio(
        applications=[
            Application(
                application_id="legacy",
                name="Legacy",
                framework="Struts",
                runtime_version="legacy",
                support_status="unsupported",
                operating_system="rhel7",
                deployment_model="vm",
                test_coverage=10,
                incident_frequency=8,
                scalability_requirement=9,
                technical_debt_score=9,
                business_criticality="critical",
                deployment_frequency=0.1,
            )
        ]
    )
    debt = calculate_technical_debt(p)[0]
    assert debt["technical_debt_index"] > 5
    assert debt["weights"] and abs(sum(debt["weights"].values()) - 1.0) < 1e-9
    diag = diagnoses(p)[0]
    assert any("legacy_infrastructure" in e for e in diag["evidence"])
    assert any("business-critical" in e for e in diag["evidence"])


def test_scenario_comparison_includes_requested_tradeoff_dimensions():
    p = Portfolio(
        applications=[Application(application_id="a", name="A", technical_debt_score=8)]
    )
    out = compare_scenarios(
        p, [Scenario(name="Aggressive", strategy_bias={Strategy.refactor: 20})]
    )[0]
    assert out["estimated_first_year_cost"] > 0
    assert out["migration_duration_estimate_waves"] >= 1
    assert "architecture_complexity_index" in out
    assert "resilience_potential_index" in out


def test_security_controls_and_simulation_are_labeled():
    p = Portfolio(
        applications=[
            Application(
                application_id="s",
                name="Sensitive",
                data_sensitivity="restricted",
                migration_risk=6,
                test_coverage=20,
            )
        ]
    )
    sec = assess_security(p)[0]
    names = {c["control"] for c in sec["controls"]}
    assert {"network_segmentation", "audit_logging"} <= names
    assert "not a certification" in sec["disclaimer"]
    sim = simulate_plan(p, [{"wave": 1, "applications": ["s"]}], runs=20, seed=2)
    assert 0 <= sim["probability_any_delay"] <= 1
    assert "not a project schedule forecast" in sim["method"]


def test_demo_scale_profiles_generate_feasible_default_waves():
    import math

    from app.optimizer import optimize_waves
    from app.schemas import ConstraintSet

    for size in (100, 500, 1000):
        p = generate_portfolio(size, seed=42)
        target = 6
        effort = sum(a.migration_effort for a in p.applications)
        risk = sum(a.migration_risk for a in p.applications)
        cost = sum(a.migration_cost for a in p.applications)
        critical = sum(
            a.business_criticality.value == "critical" for a in p.applications
        )
        constraints = ConstraintSet(
            max_waves=min(12, max(4, math.ceil(size / 100) + 6)),
            max_effort_per_wave=max(10, math.ceil(effort / target * 1.25)),
            team_capacity_per_wave=max(10, math.ceil(effort / target * 1.25)),
            max_risk_per_wave=max(10, math.ceil(risk / target * 1.25)),
            budget_per_wave=max(10000, math.ceil(cost / target * 1.25)),
            max_critical_apps_per_wave=max(1, math.ceil(critical / target) + 1),
        )
        plan = optimize_waves(p, constraints)
        assert plan["status"] == "FEASIBLE"
        assert len(plan["waves"]) >= 2
        assert all(w["why"] for w in plan["waves"])


def test_csv_import_parses_dependencies_and_numeric_fields():
    csv_data = (
        b"application_id,name,business_value,dependencies\na,Alpha,8,\nb,Beta,6,a\n"
    )
    p = parse_portfolio_bytes("estate.csv", csv_data, 5000)
    assert len(p.applications) == 2
    assert p.applications[0].business_value == 8
    assert p.applications[1].dependencies[0].target == "a"
