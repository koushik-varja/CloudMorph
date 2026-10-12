from __future__ import annotations
from .assessment import assess_portfolio
from .cost_model import estimate_cost
from .schemas import Portfolio, Scenario, Strategy


def compare_scenarios(portfolio: Portfolio, scenarios: list[Scenario]) -> list[dict]:
    results = []
    for scenario in scenarios:
        assessments = assess_portfolio(portfolio, scenario.weights)
        counts = {s.value: 0 for s in Strategy}
        total_cost = 0.0
        debt_reduction = 0.0
        risk = 0.0
        effort = 0.0
        architecture_complexity = 0.0
        resilience_potential = 0.0
        for app, result in zip(portfolio.applications, assessments):
            scores = dict(result["scores"])
            for strategy, bias in scenario.strategy_bias.items():
                scores[strategy.value] = scores.get(strategy.value, 0) + bias
            chosen = Strategy(max(scores, key=lambda strategy: scores[strategy]))
            counts[chosen.value] += 1
            total_cost += estimate_cost(app, chosen)["annualized_first_year_estimate"]
            risk += (
                app.migration_risk
                * (
                    {
                        Strategy.refactor: 1.4,
                        Strategy.replace: 1.2,
                        Strategy.replatform: 1.0,
                        Strategy.rehost: 0.7,
                        Strategy.retain: 0.2,
                        Strategy.retire: 0.5,
                    }[chosen]
                )
            )
            effort += (
                app.migration_effort
                * (
                    {
                        Strategy.refactor: 1.8,
                        Strategy.replace: 1.4,
                        Strategy.replatform: 1.0,
                        Strategy.rehost: 0.7,
                        Strategy.retain: 0.1,
                        Strategy.retire: 0.5,
                    }[chosen]
                )
            )
            debt_reduction += (
                app.technical_debt_score
                * (
                    {
                        Strategy.refactor: 0.8,
                        Strategy.replace: 0.9,
                        Strategy.replatform: 0.5,
                        Strategy.rehost: 0.1,
                        Strategy.retain: 0,
                        Strategy.retire: 1.0,
                    }[chosen]
                )
            )
            architecture_complexity += {
                Strategy.refactor: 1.0,
                Strategy.replace: 0.7,
                Strategy.replatform: 0.6,
                Strategy.rehost: 0.25,
                Strategy.retain: 0.1,
                Strategy.retire: 0.05,
            }[chosen]
            resilience_potential += {
                Strategy.refactor: 0.9,
                Strategy.replace: 0.8,
                Strategy.replatform: 0.7,
                Strategy.rehost: 0.35,
                Strategy.retain: 0.2,
                Strategy.retire: 0.4,
            }[chosen]
        results.append(
            {
                "name": scenario.name,
                "strategy_counts": counts,
                "estimated_first_year_cost": round(total_cost, 2),
                "effort_index": round(effort, 2),
                "migration_risk_index": round(risk, 2),
                "technical_debt_reduction_index": round(debt_reduction, 2),
                "apps_modernized": counts[Strategy.replatform.value]
                + counts[Strategy.refactor.value]
                + counts[Strategy.replace.value],
                "migration_duration_estimate_waves": max(1, round(effort / 40)),
                "architecture_complexity_index": round(
                    architecture_complexity / max(1, len(portfolio.applications)) * 10, 2
                ),
                "resilience_potential_index": round(
                    resilience_potential / max(1, len(portfolio.applications)) * 10, 2
                ),
                "label": "Comparative estimated indicators under configurable assumptions; not guaranteed savings or outcomes.",
            }
        )
    return results
