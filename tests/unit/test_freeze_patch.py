from datetime import date, timedelta

from app.schemas import Application, Portfolio, SupportStatus
from app.technical_debt import calculate_technical_debt


def debt_for(app: Application) -> dict:
    return calculate_technical_debt(Portfolio(name="freeze", applications=[app]))[0]


def test_unsupported_runtime_does_not_double_count_as_old_framework():
    row = debt_for(
        Application(
            application_id="runtime-eol",
            name="Runtime EOL",
            framework="Spring",
            runtime="jvm",
            runtime_version="unsupported",
            support_status=SupportStatus.unsupported,
        )
    )
    assert row["factors"]["unsupported_runtime"] == 10.0
    assert row["factors"]["old_framework"] == 0.0
    assert "unsupported_or_legacy_runtime" not in row["factors"]


def test_old_framework_does_not_imply_unsupported_runtime():
    row = debt_for(
        Application(
            application_id="old-framework",
            name="Old Framework",
            framework="Struts",
            runtime="jvm",
            runtime_version="17",
            support_status=SupportStatus.supported,
            support_end_date=date.today() + timedelta(days=365),
        )
    )
    assert row["factors"]["old_framework"] == 10.0
    assert row["factors"]["unsupported_runtime"] == 0.0


def test_expired_support_date_is_runtime_lifecycle_evidence_not_framework_evidence():
    row = debt_for(
        Application(
            application_id="expired-support",
            name="Expired Support",
            framework="FastAPI",
            runtime="python",
            runtime_version="3.12",
            support_status=SupportStatus.unknown,
            support_end_date=date.today() - timedelta(days=1),
        )
    )
    assert row["factors"]["unsupported_runtime"] == 10.0
    assert row["factors"]["old_framework"] == 0.0
    assert any("support_end_date=" in item for item in row["evidence"])
