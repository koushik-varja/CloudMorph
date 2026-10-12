from app.architecture import generate_architecture, terraform_starter
from app.cost_model import estimate_cost
from app.schemas import Application, Sensitivity, Strategy


def test_cost_is_estimated_and_formula_driven():
    app = Application(
        application_id="a",
        name="A",
        peak_traffic_rps=100,
        traffic_rps=10,
        database="pg",
        database_size_gb=50,
        migration_effort=4,
    )
    out = estimate_cost(app, Strategy.replatform)
    assert out["annualized_first_year_estimate"] > 0
    assert "ILLUSTRATIVE ESTIMATE" in out["label"]
    assert "formula" in out


def test_architecture_rules_and_terraform_safety():
    app = Application(
        application_id="secure",
        name="Secure",
        data_sensitivity=Sensitivity.restricted,
        integration_count=5,
        database="pg",
    )
    arch = generate_architecture(app, Strategy.replatform)
    labels = {x["label"] for x in arch["components"]}
    assert "Container Platform" in labels
    assert "Managed Relational Database" in labels
    assert "Audit Logging + Segmented Network" in labels
    tf = terraform_starter(app, Strategy.replatform)
    assert "DRAFT ONLY" in tf
    assert "0.0.0.0/0" not in tf
    assert 'resource "' not in tf
