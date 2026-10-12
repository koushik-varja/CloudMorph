from app.assessment import assess_portfolio, dimensions, strategy_scores
from app.schemas import Application, Portfolio, ScoreWeights, Strategy
from app.sensitivity import run_sensitivity


def test_strategy_scoring_is_bounded_and_explainable():
    app = Application(
        application_id="billing",
        name="Billing",
        business_value=9,
        technical_debt_score=8,
        scalability_requirement=8,
        test_coverage=70,
    )
    dims = dimensions(app)
    scores = strategy_scores(app, dims, ScoreWeights())
    assert set(scores) == set(Strategy)
    assert all(0 <= v <= 100 for v in scores.values())
    result = assess_portfolio(Portfolio(applications=[app]))[0]
    assert result["recommendation"] in {s.value for s in Strategy}
    assert result["reasons"]
    assert result["confidence"] in {"LOW", "MEDIUM", "HIGH"}


def test_sensitivity_distribution_sums_to_one():
    p = Portfolio(
        applications=[Application(application_id="a", name="A", technical_debt_score=8)]
    )
    result = run_sensitivity(p, samples=20, seed=1)[0]
    assert abs(sum(result["recommendation_distribution"].values()) - 1.0) < 1e-9
