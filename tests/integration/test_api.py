import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def small_portfolio():
    return {
        "name": "Integration",
        "applications": [
            {
                "application_id": "a",
                "name": "A",
                "migration_effort": 1,
                "migration_risk": 1,
                "migration_cost": 10,
            },
            {
                "application_id": "b",
                "name": "B",
                "migration_effort": 1,
                "migration_risk": 1,
                "migration_cost": 10,
                "dependencies": [{"target": "a"}],
            },
        ],
    }


def test_health_graph_assessment_optimizer_architecture(client):
    assert client.get("/health").status_code == 200
    p = small_portfolio()
    graph = client.post("/api/graph", json=p)
    assert graph.status_code == 200 and graph.json()["analysis"]["edge_count"] == 1
    assess = client.post("/api/assessment", json={"portfolio": p, "weights": {}})
    assert assess.status_code == 200 and len(assess.json()) == 2
    bundle = client.post(
        "/api/analyze?samples=10", json={"portfolio": p, "weights": {}}
    )
    assert bundle.status_code == 200
    assert bundle.json()["graph"]["analysis"]["edge_count"] == 1
    assert len(bundle.json()["technical_debt"]) == 2
    optimize = client.post(
        "/api/optimize",
        json={
            "portfolio": p,
            "constraints": {
                "max_waves": 3,
                "max_effort_per_wave": 3,
                "team_capacity_per_wave": 3,
                "max_risk_per_wave": 3,
                "budget_per_wave": 100,
                "max_critical_apps_per_wave": 2,
            },
            "objective": "balanced",
        },
    )
    assert optimize.status_code == 200 and optimize.json()["status"] == "FEASIBLE"
    arch = client.post(
        "/api/architecture",
        json={"application": p["applications"][0], "strategy": "Replatform"},
    )
    assert arch.status_code == 200 and arch.json()["provider_neutral"] is True


def test_import_and_db_persistence(client):
    p = small_portfolio()
    resp = client.post(
        "/api/portfolio/import?persist=true",
        files={
            "file": ("estate.json", __import__("json").dumps(p), "application/json")
        },
    )
    assert resp.status_code == 200
    pid = resp.json()["portfolio_id"]
    loaded = client.get(f"/api/portfolio/{pid}")
    assert loaded.status_code == 200
    assert loaded.json()["name"] == "Integration"


def test_bad_upload_rejected(client):
    resp = client.post(
        "/api/portfolio/import",
        files={"file": ("../bad.json", "{}", "application/json")},
    )
    assert resp.status_code == 400


def test_cost_compare_exposes_all_six_strategies(client):
    app = small_portfolio()["applications"][0]
    response = client.post(
        "/api/cost-compare",
        json={"application": app, "assumptions": {"engineer_hourly_rate": 50}},
    )
    assert response.status_code == 200
    body = response.json()
    assert {row["strategy"] for row in body["alternatives"]} == {
        "Rehost",
        "Replatform",
        "Refactor",
        "Replace",
        "Retain",
        "Retire",
    }
    assert "ILLUSTRATIVE" in body["assumption_label"]
