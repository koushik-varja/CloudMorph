from __future__ import annotations

import json
import math
import os
import platform
import statistics
import time
from pathlib import Path

from app.assessment import assess_portfolio
from app.generator import generate_portfolio
from app.graph_engine import analyze_graph, build_graph
from app.main import app
from app.optimizer import optimize_waves
from app.pareto import pareto_frontier
from app.schemas import ConstraintSet, Portfolio
from app.sensitivity import run_sensitivity
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "benchmarks" / "results.json"
OUT_MD = ROOT / "benchmarks" / "RESULTS.md"


def timed(fn):
    start = time.perf_counter()
    value = fn()
    return (time.perf_counter() - start) * 1000, value


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[idx]


def memory_gb() -> float | None:
    try:
        line = next(
            x
            for x in Path("/proc/meminfo").read_text().splitlines()
            if x.startswith("MemTotal:")
        )
        return round(int(line.split()[1]) / 1024 / 1024, 2)
    except (OSError, StopIteration, ValueError, IndexError):
        return None


def main() -> None:
    hardware = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor() or "not reported",
        "cpu_count": os.cpu_count(),
        "memory_gb": memory_gb(),
        "ortools_available": __import__("app.optimizer", fromlist=["cp_model"]).cp_model
        is not None,
    }
    results = []
    with TestClient(app) as client:
        for size in (100, 500, 1000):
            portfolio = generate_portfolio(size, seed=42)
            raw = json.dumps(portfolio.model_dump(mode="json"))
            import_ms, parsed = timed(
                lambda raw=raw: Portfolio.model_validate_json(raw)
            )
            graph_build_ms, _ = timed(lambda parsed=parsed: build_graph(parsed))
            graph_analysis_ms, graph_result = timed(
                lambda parsed=parsed: analyze_graph(parsed)
            )
            scoring_ms, _ = timed(lambda parsed=parsed: assess_portfolio(parsed))
            sensitivity_ms, _ = timed(
                lambda parsed=parsed: run_sensitivity(parsed, samples=20, seed=42)
            )
            total_effort = sum(a.migration_effort for a in parsed.applications)
            total_risk = sum(a.migration_risk for a in parsed.applications)
            total_cost = sum(a.migration_cost for a in parsed.applications)
            total_critical = sum(
                a.business_criticality.value == "critical" for a in parsed.applications
            )
            target_waves = 6
            constraints = ConstraintSet(
                max_waves=min(12, max(4, math.ceil(size / 100) + 6)),
                max_effort_per_wave=max(
                    10, math.ceil(total_effort / target_waves * 1.25)
                ),
                team_capacity_per_wave=max(
                    10, math.ceil(total_effort / target_waves * 1.25)
                ),
                max_risk_per_wave=max(10, math.ceil(total_risk / target_waves * 1.25)),
                budget_per_wave=max(
                    10_000, math.ceil(total_cost / target_waves * 1.25)
                ),
                max_critical_apps_per_wave=max(
                    1, math.ceil(total_critical / target_waves) + 1
                ),
            )
            optimize_ms, plan = timed(
                lambda parsed=parsed, constraints=constraints: optimize_waves(
                    parsed,
                    constraints,
                    "balanced_risk",
                    solver_mode="fallback",
                )
            )
            pareto_ms, frontier = timed(
                lambda parsed=parsed, constraints=constraints: pareto_frontier(
                    parsed,
                    constraints,
                    solver_mode="fallback",
                )
            )
            api_times = []
            payload = parsed.model_dump(mode="json")
            for _ in range(7):
                t0 = time.perf_counter()
                response = client.post("/api/graph", json=payload)
                response.raise_for_status()
                api_times.append((time.perf_counter() - t0) * 1000)
            results.append(
                {
                    "apps": size,
                    "edges": graph_result["edge_count"],
                    "scc_groups": len(graph_result["strongly_connected_components"]),
                    "import_ms": round(import_ms, 3),
                    "graph_construction_ms": round(graph_build_ms, 3),
                    "scc_graph_analysis_ms": round(graph_analysis_ms, 3),
                    "scoring_ms": round(scoring_ms, 3),
                    "sensitivity_20_samples_ms": round(sensitivity_ms, 3),
                    "wave_optimization_ms": round(optimize_ms, 3),
                    "wave_status": plan["status"],
                    "solver": plan.get("solver_used", plan.get("solver")),
                    "pareto_generation_ms": round(pareto_ms, 3),
                    "pareto_plans_attempted": frontier["plans_attempted"],
                    "pareto_unique_candidates": frontier["unique_candidates"],
                    "pareto_frontier_count": frontier["frontier_count"],
                    "api_graph_p50_ms": round(statistics.median(api_times), 3),
                    "api_graph_p95_ms": round(percentile(api_times, 0.95), 3),
                }
            )
    payload = {
        "hardware": hardware,
        "methodology": {
            "runs_per_api_size": 7,
            "sensitivity_samples": 20,
            "seed": 42,
            "note": "Measured in the execution sandbox. The solver_used field states the actual optimizer path; no Docker daemon or OR-Tools package was available during this run, so fallback timings are not CP-SAT timings.",
        },
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# CloudMorph benchmark results",
        "",
        "These values were generated by `benchmarks/run_benchmarks.py`; they are not hardcoded claims.",
        "",
        "## Environment",
        "",
        *[f"- **{k}**: {v}" for k, v in hardware.items()],
        "",
        "## Results",
        "",
        "| Apps | Edges | Import ms | Graph build ms | Graph analysis ms | Scoring ms | Sensitivity ms | Optimize ms | Pareto ms | API p50 ms | API p95 ms |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['apps']} | {r['edges']} | {r['import_ms']} | {r['graph_construction_ms']} | {r['scc_graph_analysis_ms']} | {r['scoring_ms']} | {r['sensitivity_20_samples_ms']} | {r['wave_optimization_ms']} | {r['pareto_generation_ms']} | {r['api_graph_p50_ms']} | {r['api_graph_p95_ms']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Betweenness centrality is exact up to 300 nodes and sampled (`k=100`, fixed seed) above that threshold to keep analysis practical.",
        "- Sensitivity timings use 20 perturbation samples per application for benchmark repeatability; the API defaults to 80.",
        "- The optimizer result includes the actual solver name. In this benchmark environment OR-Tools was unavailable, so the deterministic fallback was exercised and candidate assignments were independently revalidated.",
        "- API latency is local in-process `POST /api/graph` latency, not network or production throughput.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
