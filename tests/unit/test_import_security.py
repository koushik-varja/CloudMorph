import json

import pytest
from app.importers import ImportErrorDetail, parse_portfolio_bytes, safe_filename


def test_path_traversal_rejected():
    with pytest.raises(ImportErrorDetail):
        safe_filename("../../portfolio.json")
    with pytest.raises(ImportErrorDetail):
        safe_filename(r"..\..\portfolio.json")


def test_oversized_upload_rejected():
    with pytest.raises(ImportErrorDetail):
        parse_portfolio_bytes("p.json", b"x" * 11, 10)


def test_malicious_yaml_constructor_not_executed():
    bad = b"!!python/object/apply:os.system ['echo unsafe']"
    with pytest.raises(ImportErrorDetail):
        parse_portfolio_bytes("p.yaml", bad, 1000)


def test_invalid_dependency_reference_rejected():
    payload = {
        "applications": [
            {
                "application_id": "a",
                "name": "A",
                "dependencies": [{"target": "missing"}],
            }
        ]
    }
    with pytest.raises(ImportErrorDetail):
        parse_portfolio_bytes("p.json", json.dumps(payload).encode(), 10000)


def test_sql_like_text_remains_data():
    payload = {
        "applications": [
            {"application_id": "a", "name": "A'; DROP TABLE portfolios;--"}
        ]
    }
    p = parse_portfolio_bytes("p.json", json.dumps(payload).encode(), 10000)
    assert "DROP TABLE" in p.applications[0].name
