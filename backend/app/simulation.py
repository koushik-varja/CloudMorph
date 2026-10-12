from __future__ import annotations
import random
import statistics
from collections import Counter
from .risk_model import migration_execution_risk
from .schemas import Portfolio


def simulate_plan(portfolio: Portfolio, waves: list[dict], runs: int = 250, seed: int = 42) -> dict:
    if runs < 10 or runs > 5000:
        raise ValueError("runs must be between 10 and 5000")
    by_id = {a.application_id: a for a in portfolio.applications}
    app_wave = {app: w["wave"] for w in waves for app in w.get("applications", [])}
    rng = random.Random(seed)
    delays: list[float] = []
    blocker_counts: Counter[str] = Counter()
    for _ in range(runs):
        wave_delay: dict[int, float] = {w["wave"]: 0.0 for w in waves}
        for wave in sorted(waves, key=lambda x: x["wave"]):
            w = wave["wave"]
            inherited = 0.0
            for app_id in wave.get("applications", []):
                app = by_id[app_id]
                for dep in app.dependencies:
                    dep_wave = app_wave.get(dep.target)
                    if dep_wave is not None and dep_wave < w:
                        inherited = max(inherited, wave_delay.get(dep_wave, 0.0))
            local = 0.0
            for app_id in wave.get("applications", []):
                app = by_id[app_id]
                risk = migration_execution_risk(app)
                p = min(0.55, 0.015 + 0.035 * risk + (0.06 if app.test_coverage < 30 else 0.0))
                if rng.random() < p:
                    local = max(local, rng.choice([0.5, 1.0, 2.0, 3.0]))
                    blocker_counts[app_id] += 1
            wave_delay[w] = inherited + local
        delays.append(max(wave_delay.values(), default=0.0))
    ordered = sorted(delays)
    p90 = ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]
    return {
        "runs": runs,
        "probability_any_delay": round(sum(d > 0 for d in delays) / runs, 4),
        "median_completion_delay_weeks": round(statistics.median(delays), 3),
        "p90_completion_delay_weeks": round(p90, 3),
        "most_common_blocking_dependency_or_app": blocker_counts.most_common(1)[0][0]
        if blocker_counts
        else None,
        "method": "SIMULATED: seeded execution-risk/test-failure delays propagate from prerequisite waves to dependent waves. not a project schedule forecast.",
    }
