from __future__ import annotations

from .graph_engine import analyze_graph
from .risk_model import availability_complexity, current_operational_risk, migration_execution_risk
from .schemas import Application, Portfolio, ScoreWeights, Strategy

CRIT = {"low": 2.0, "medium": 5.0, "high": 8.0, "critical": 10.0}
SENS = {"public": 1.0, "internal": 3.0, "confidential": 7.0, "restricted": 10.0}


def dimensions(app: Application, graph_metric: dict | None = None) -> dict[str, float]:
    gm = graph_metric or {}
    coupling = min(
        10.0,
        (float(gm.get("in_degree", 0)) + float(gm.get("out_degree", 0))) * 1.4
        + 10.0 * float(gm.get("betweenness", 0)),
    )
    op_risk = current_operational_risk(app, gm)
    exec_risk = migration_execution_risk(app, gm)
    security = min(
        10.0,
        0.7 * SENS[app.data_sensitivity.value]
        + 0.3 * (10 - (app.identity_maturity if app.identity_maturity is not None else 5)),
    )
    organization = min(
        10.0, 0.55 * (10 - app.team_skill_level) + 0.45 * (10 - app.test_coverage / 10)
    )
    return {
        "business": round(
            (app.business_value + CRIT[app.business_criticality.value] + app.change_frequency) / 3,
            3,
        ),
        "technical": round(
            (app.technical_debt_score + coupling + app.scalability_requirement + op_risk) / 4, 3
        ),
        "migration": exec_risk,
        "current_operational_risk": op_risk,
        "migration_execution_risk": exec_risk,
        "availability_complexity": availability_complexity(app.availability_requirement),
        "operations": op_risk,
        "security": round(security, 3),
        "organizational": round(organization, 3),
    }


def strategy_scores(
    app: Application, dims: dict[str, float], weights: ScoreWeights
) -> dict[Strategy, float]:
    debt = app.technical_debt_score
    business = app.business_value
    criticality = CRIT[app.business_criticality.value]
    change = app.change_frequency
    scale = app.scalability_requirement
    op_risk = dims["current_operational_risk"]
    exec_risk = dims["migration_execution_risk"]
    maturity = 0.55 * (app.test_coverage / 10.0) + 0.45 * app.team_skill_level
    health = max(0.0, 10.0 - (0.6 * debt + 0.4 * op_risk))
    cost_pressure = min(10.0, app.estimated_current_cost / 1500.0)
    low_usage = 10.0 - app.usage_level
    low_change = 10.0 - change
    low_value = 10.0 - business
    availability_penalty = dims["availability_complexity"]

    raw = {
        Strategy.rehost: 25
        + 3.0 * health
        + 1.8 * weights.time_pressure
        + 1.5 * maturity
        - 1.5 * exec_risk
        - 0.8 * scale,
        Strategy.replatform: 33
        + 2.0 * business
        + 1.9 * min(debt, 7)
        + 1.5 * scale
        + 1.0 * maturity
        - 1.15 * exec_risk,
        Strategy.refactor: 8
        + 2.7 * business
        + 2.8 * debt
        + 2.0 * change
        + 1.8 * scale
        + 1.7 * maturity
        - 1.5 * exec_risk
        - 0.45 * availability_penalty,
        Strategy.replace: 10
        + 3.0 * app.commodity_fit
        + 2.4 * app.replacement_fit
        + 2.2 * debt
        + 1.0 * cost_pressure
        - 0.8 * criticality
        - 0.7 * exec_risk,
        Strategy.retain: 18
        + 3.1 * exec_risk
        + 1.7 * criticality
        + 1.3 * health
        - 1.9 * op_risk
        - 1.3 * change
        - 0.8 * scale,
        Strategy.retire: 5
        + 3.8 * low_value
        + 3.2 * low_usage
        + 2.0 * low_change
        + 2.6 * app.redundancy_score
        - 1.5 * criticality,
    }

    raw[Strategy.rehost] += (
        5 * (weights.cost_importance - 1)
        + 6 * (weights.time_pressure - 1)
        - 2 * (weights.modernization_value_preference - 1)
    )
    raw[Strategy.replatform] += (
        4 * (weights.business_value - 1)
        + 4 * (weights.debt_importance - 1)
        + 3 * (weights.scalability_importance - 1)
    )
    raw[Strategy.refactor] += (
        8 * (weights.debt_importance - 1)
        + 6 * (weights.business_value - 1)
        + 5 * (weights.modernization_value_preference - 1)
        + 4 * (weights.scalability_importance - 1)
        - 4 * (weights.cost_importance - 1)
    )
    raw[Strategy.replace] += (
        5 * (weights.cost_importance - 1)
        + 4 * (weights.debt_importance - 1)
        + 3 * (weights.modernization_value_preference - 1)
    )
    raw[Strategy.retain] += (
        6 * (1 - weights.execution_risk_tolerance)
        - 6 * (weights.operational_risk_importance - 1)
        + 3 * (weights.risk_tolerance - 1)
    )
    raw[Strategy.retire] += 3 * (weights.cost_importance - 1)

    if app.availability_requirement >= 99.99:
        raw[Strategy.rehost] -= 4 * weights.availability_importance
        raw[Strategy.refactor] -= 2 * weights.availability_importance
    if app.business_criticality.value == "critical" and app.test_coverage < 30 and exec_risk >= 6:
        raw[Strategy.retain] += 24
    if app.database and "oracle" in app.database.lower():
        raw[Strategy.refactor] -= 3
        raw[Strategy.replatform] -= 2
    return {k: round(max(0.0, min(100.0, v)), 2) for k, v in raw.items()}


def input_completeness(app: Application) -> float:
    fields = [
        app.observability_maturity,
        app.identity_maturity,
        app.support_end_date,
        app.residency_region,
        app.maintenance_tag,
    ]
    present = sum(v is not None for v in fields)
    return round(0.65 + 0.35 * present / len(fields), 3)


def confidence_from_evidence(
    margin: float, stability: float | None, completeness: float
) -> tuple[str, str]:
    margin_score = min(1.0, margin / 12.0)
    stability_score = stability if stability is not None else 0.65
    evidence = 0.45 * margin_score + 0.40 * stability_score + 0.15 * completeness
    label = "HIGH" if evidence >= 0.78 else "MEDIUM" if evidence >= 0.55 else "LOW"
    reason = f"score margin={margin:.2f}; decision stability={stability if stability is not None else 'not yet sampled'}; input completeness={completeness:.2f}"
    if label == "LOW":
        reason += "; human review recommended because the decision is sensitive or closely scored"
    return label, reason


def explain(app: Application, dims: dict[str, float], scores: dict[Strategy, float]) -> list[str]:
    reasons: list[str] = []
    if app.business_criticality.value in {"high", "critical"}:
        reasons.append(
            "High business criticality penalizes retirement and favors controlled change."
        )
    if app.technical_debt_score >= 7:
        reasons.append("High technical debt raises the case for refactor or replacement.")
    if app.test_coverage < 40:
        reasons.append(
            "Low test coverage increases migration execution risk and weakens high-change options."
        )
    if dims["migration_execution_risk"] >= 7:
        reasons.append(
            "Migration execution risk is high due to dependency/data/downtime/maturity factors."
        )
    if dims["current_operational_risk"] >= 7:
        reasons.append(
            "Current operational risk is high, strengthening the case for modernization rather than passive retention."
        )
    if app.scalability_requirement >= 7:
        reasons.append("High scalability requirement favors platform improvement or refactoring.")
    if app.commodity_fit >= 7 and app.replacement_fit >= 7:
        reasons.append("Commodity/replacement fit makes replacement a credible alternative.")
    if app.business_value <= 3 and app.usage_level <= 3:
        reasons.append("Low value and usage make retirement economically plausible.")
    winner = max(scores, key=lambda strategy: scores[strategy])
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    reasons.append(
        f"{winner.value} leads {ordered[1][0].value} by {ordered[0][1] - ordered[1][1]:.2f} points under the supplied weights."
    )
    return reasons


def assess_portfolio(
    portfolio: Portfolio, weights: ScoreWeights | None = None, graph_analysis: dict | None = None
) -> list[dict]:
    weights = weights or ScoreWeights()
    graph = graph_analysis or analyze_graph(portfolio)
    gm = {m["application_id"]: m for m in graph["metrics"]}
    results = []
    for app in portfolio.applications:
        dims = dimensions(app, gm.get(app.application_id))
        scores = strategy_scores(app, dims, weights)
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        margin = ordered[0][1] - ordered[1][1]
        completeness = input_completeness(app)
        confidence, reason = confidence_from_evidence(margin, None, completeness)
        results.append(
            {
                "application_id": app.application_id,
                "name": app.name,
                "dimensions": dims,
                "scores": {k.value: v for k, v in scores.items()},
                "recommendation": ordered[0][0].value,
                "runner_up": ordered[1][0].value,
                "score_margin": round(margin, 2),
                "confidence": confidence,
                "confidence_reason": reason,
                "input_completeness": completeness,
                "reasons": explain(app, dims, scores),
                "weights": weights.model_dump(),
                "formula_note": "Deterministic transparent rule model. Scores and sensitivity frequencies are decision-support indicators, not probabilities.",
            }
        )
    return results


def diagnoses(portfolio: Portfolio, graph_analysis: dict | None = None) -> list[dict]:
    graph = graph_analysis or analyze_graph(portfolio)
    gm = {m["application_id"]: m for m in graph["metrics"]}
    out: list[dict] = []
    db_coupling = graph["shared_database_coupling"]
    for app in portfolio.applications:
        evidence: list[str] = []
        metric = gm[app.application_id]
        op = current_operational_risk(app, metric)
        exe = migration_execution_risk(app, metric)
        if app.technical_debt_score >= 7:
            evidence.append(f"technical_debt_score={app.technical_debt_score}")
        if app.runtime_version.lower() in {"legacy", "eol", "unsupported"}:
            evidence.append(f"runtime_version={app.runtime_version}")
        if app.test_coverage < 35:
            evidence.append(f"test_coverage={app.test_coverage}%")
        if app.incident_frequency >= 6:
            evidence.append(f"incident_frequency={app.incident_frequency}")
        if metric["blast_radius"] >= max(3, len(portfolio.applications) * 0.1):
            evidence.append(f"blast_radius={metric['blast_radius']}")
        if app.database in db_coupling:
            evidence.append(
                f"shared_database={app.database} used_by={len(db_coupling[app.database])}"
            )
        if metric["articulation_like"]:
            evidence.append("articulation-like bridge in undirected dependency projection")
        if app.deployment_model.lower() in {"vm", "bare-metal", "bare metal"} and any(
            x in app.operating_system.lower() for x in ("rhel7", "legacy", "windows 2012")
        ):
            evidence.append(f"legacy_infrastructure={app.deployment_model}/{app.operating_system}")
        if app.business_criticality.value == "critical" and app.technical_debt_score >= 7:
            evidence.append("business-critical application also has high technical debt")
        if evidence:
            out.append(
                {
                    "application_id": app.application_id,
                    "severity": "high" if len(evidence) >= 3 else "medium",
                    "current_operational_risk": op,
                    "migration_execution_risk": exe,
                    "evidence": evidence,
                }
            )
    return out
