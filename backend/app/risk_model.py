from __future__ import annotations

import math
from datetime import date

from .schemas import Application

CRITICALITY = {"low": 2.0, "medium": 5.0, "high": 8.0, "critical": 10.0}


def availability_complexity(availability_requirement: float) -> float:
    """Return monotonic 0-10 migration complexity from the availability SLO.

    The transform is based on annual downtime tolerance. Tighter availability means less
    allowed downtime and therefore more cutover, failover and validation complexity.
    """
    availability = min(99.9999, max(90.0, availability_requirement))
    downtime_minutes = 525_600.0 * (1.0 - availability / 100.0)
    baseline = 525_600.0 * (1.0 - 0.99)  # 99.0% availability
    strict = 525_600.0 * (1.0 - 0.99999)  # 99.999% availability
    if downtime_minutes >= baseline:
        return 1.0
    ratio = (math.log10(baseline) - math.log10(max(strict, downtime_minutes))) / (
        math.log10(baseline) - math.log10(strict)
    )
    return round(min(10.0, 1.0 + 9.0 * max(0.0, ratio)), 3)


def support_risk(app: Application) -> float:
    tokens = f"{app.runtime_version} {app.framework} {app.operating_system}".lower()
    declared = any(
        t in tokens
        for t in (
            "legacy",
            "eol",
            "unsupported",
            "struts",
            "cics",
            "rhel6",
            "rhel7",
            "windows 2012",
        )
    )
    expired = app.support_end_date is not None and app.support_end_date < date.today()
    return 10.0 if declared or expired else 2.0


def current_operational_risk(app: Application, graph_metric: dict | None = None) -> float:
    gm = graph_metric or {}
    coupling = min(
        10.0,
        (float(gm.get("in_degree", 0)) + float(gm.get("out_degree", 0))) * 1.2
        + 12.0 * float(gm.get("betweenness", 0)),
    )
    incident = min(10.0, app.incident_frequency)
    resilience_gap = min(
        10.0,
        0.55 * CRITICALITY[app.business_criticality.value]
        + 0.45 * availability_complexity(app.availability_requirement),
    )
    value = (
        0.26 * app.technical_debt_score
        + 0.22 * support_risk(app)
        + 0.20 * incident
        + 0.17 * resilience_gap
        + 0.15 * coupling
    )
    return round(min(10.0, max(0.0, value)), 3)


def migration_execution_risk(app: Application, graph_metric: dict | None = None) -> float:
    gm = graph_metric or {}
    graph_coupling = min(
        10.0,
        (float(gm.get("in_degree", 0)) + float(gm.get("out_degree", 0))) * 1.4
        + 10.0 * float(gm.get("betweenness", 0)),
    )
    dependency_pressure = min(10.0, max(app.integration_count, int(gm.get("out_degree", 0))) * 1.4)
    data_complexity = min(10.0, math.log10(1.0 + app.database_size_gb) * 3.0)
    test_gap = max(0.0, 10.0 - app.test_coverage / 10.0)
    skill_gap = max(0.0, 10.0 - app.team_skill_level)
    availability = availability_complexity(app.availability_requirement)
    stated = app.migration_risk
    value = (
        0.20 * dependency_pressure
        + 0.16 * data_complexity
        + 0.21 * availability
        + 0.17 * test_gap
        + 0.10 * skill_gap
        + 0.10 * graph_coupling
        + 0.06 * stated
    )
    return round(min(10.0, max(0.0, value)), 3)
