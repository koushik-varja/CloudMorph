from __future__ import annotations

from datetime import date

from .graph_engine import analyze_graph
from .schemas import Application, Portfolio, SupportStatus


UNSUPPORTED_RUNTIME_TOKENS = ("unsupported", "eol", "end-of-life", "end of life")
LEGACY_FRAMEWORK_TOKENS = ("struts", "cics", "legacy framework")


def _unsupported_runtime(app: Application) -> tuple[bool, list[str]]:
    """Return lifecycle/support evidence without inferring it from framework age."""
    evidence: list[str] = []
    runtime_metadata = f"{app.runtime} {app.runtime_version}".lower()
    if app.support_status in {SupportStatus.unsupported, SupportStatus.eol}:
        evidence.append(f"support_status={app.support_status.value}")
    if any(token in runtime_metadata for token in UNSUPPORTED_RUNTIME_TOKENS):
        evidence.append(f"runtime_metadata={app.runtime}/{app.runtime_version}")
    if app.support_end_date is not None and app.support_end_date < date.today():
        evidence.append(f"support_end_date={app.support_end_date.isoformat()} expired")
    return bool(evidence), evidence


def _legacy_framework(app: Application) -> tuple[bool, list[str]]:
    """Return architecture/framework legacy evidence only, never support lifecycle evidence."""
    framework = app.framework.lower()
    evidence = (
        [f"framework={app.framework}"]
        if any(token in framework for token in LEGACY_FRAMEWORK_TOKENS)
        else []
    )
    return bool(evidence), evidence


def calculate_technical_debt(
    portfolio: Portfolio, graph_analysis: dict | None = None
) -> list[dict]:
    graph = graph_analysis or analyze_graph(portfolio)
    gm = {m["application_id"]: m for m in graph["metrics"]}
    shared = graph["shared_database_coupling"]
    results = []
    for app in portfolio.applications:
        metric = gm[app.application_id]
        unsupported_runtime, runtime_evidence = _unsupported_runtime(app)
        legacy_framework, framework_evidence = _legacy_framework(app)
        factors = {
            "unsupported_runtime": 10.0 if unsupported_runtime else 0.0,
            "legacy_os": 10.0
            if any(
                x in app.operating_system.lower()
                for x in ("rhel6", "rhel7", "windows 2012", "legacy")
            )
            else 0.0,
            "shared_database": 10.0 if app.database in shared else 0.0,
            "point_to_point_integrations": min(10.0, app.integration_count * 1.5),
            "low_test_coverage": max(0.0, 10.0 - app.test_coverage / 10.0),
            "manual_or_slow_deployment": 8.0
            if app.deployment_frequency < 0.5
            else max(0.0, 5.0 - app.deployment_frequency / 3.0),
            "incident_pressure": min(10.0, app.incident_frequency),
            "graph_coupling": min(
                10.0,
                2.0 * (metric["in_degree"] + metric["out_degree"])
                + 15.0 * float(metric["betweenness"]),
            ),
            "old_framework": 10.0 if legacy_framework else 0.0,
            "scaling_gap": min(
                10.0,
                app.scalability_requirement
                * (
                    1.0
                    if app.deployment_model.lower() in {"vm", "bare-metal", "bare metal"}
                    else 0.4
                ),
            ),
        }
        weights = {
            "unsupported_runtime": 0.15,
            "legacy_os": 0.08,
            "shared_database": 0.12,
            "point_to_point_integrations": 0.10,
            "low_test_coverage": 0.12,
            "manual_or_slow_deployment": 0.08,
            "incident_pressure": 0.10,
            "graph_coupling": 0.10,
            "old_framework": 0.08,
            "scaling_gap": 0.07,
        }
        index = sum(factors[k] * weights[k] for k in factors)
        evidence = [f"{k}={v:.2f}" for k, v in factors.items() if v >= 6]
        evidence.extend(runtime_evidence)
        evidence.extend(framework_evidence)
        results.append(
            {
                "application_id": app.application_id,
                "technical_debt_index": round(index, 3),
                "input_debt_score": app.technical_debt_score,
                "factors": {k: round(v, 3) for k, v in factors.items()},
                "weights": weights,
                "evidence": evidence,
                "formula": "weighted sum of ten normalized 0–10 factors; unsupported_runtime is lifecycle/support risk and old_framework is architectural framework age; weights sum to 1.0",
            }
        )
    return sorted(results, key=lambda x: x["technical_debt_index"], reverse=True)
