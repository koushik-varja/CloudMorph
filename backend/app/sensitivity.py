from __future__ import annotations

from collections import Counter, defaultdict
import random

from .assessment import confidence_from_evidence, dimensions, input_completeness, strategy_scores
from .graph_engine import analyze_graph
from .schemas import Portfolio, ScoreWeights


def run_sensitivity(
    portfolio: Portfolio, samples: int = 80, seed: int = 42, graph_analysis: dict | None = None
) -> list[dict]:
    if samples < 10 or samples > 1000:
        raise ValueError("samples must be between 10 and 1000")
    rng = random.Random(seed)
    graph = graph_analysis or analyze_graph(portfolio)
    gm = {m["application_id"]: m for m in graph["metrics"]}
    results = []
    factors = list(ScoreWeights.model_fields)
    for app in portfolio.applications:
        dims = dimensions(app, gm.get(app.application_id))
        winners: Counter[str] = Counter()
        for _ in range(samples):
            weights = ScoreWeights(**{factor: rng.uniform(0.7, 1.3) for factor in factors})
            scores = strategy_scores(app, dims, weights)
            winners[max(scores, key=lambda strategy: scores[strategy]).value] += 1
        ordered = winners.most_common()
        stability = ordered[0][1] / samples
        baseline = strategy_scores(app, dims, ScoreWeights())
        baseline_order = sorted(baseline.items(), key=lambda kv: kv[1], reverse=True)
        margin = baseline_order[0][1] - baseline_order[1][1]
        influential = []
        for factor in factors:
            winners_1d: set[str] = set()
            spans: dict[str, list[float]] = defaultdict(list)
            for value in (0.7, 0.85, 1.15, 1.3):
                values = {name: 1.0 for name in factors}
                values[factor] = value
                scores = strategy_scores(app, dims, ScoreWeights(**values))
                winners_1d.add(max(scores, key=lambda strategy: scores[strategy]).value)
                for strategy, score in scores.items():
                    spans[strategy.value].append(score)
            span = max((max(v) - min(v) for v in spans.values()), default=0.0)
            switched = baseline_order[0][0].value not in winners_1d or len(winners_1d) > 1
            influential.append((factor, span + (10.0 if switched else 0.0)))
        influential.sort(key=lambda x: x[1], reverse=True)
        confidence, confidence_reason = confidence_from_evidence(
            margin, stability, input_completeness(app)
        )
        results.append(
            {
                "application_id": app.application_id,
                "samples": samples,
                "recommendation_distribution": {k: round(v / samples, 4) for k, v in ordered},
                "stability": round(stability, 4),
                "decision_stability": "HIGH"
                if stability >= 0.8
                else "MEDIUM"
                if stability >= 0.6
                else "LOW",
                "confidence": confidence,
                "confidence_reason": confidence_reason,
                "most_influential_factors": [x[0] for x in influential[:3]],
                "method": "Seeded parameter perturbation. Frequencies measure decision stability under assumptions; they are not Bayesian probabilities.",
            }
        )
    return results
