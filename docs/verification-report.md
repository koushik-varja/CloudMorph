# Verification report — final freeze v2

This report records what was actually executed for the final CloudMorph freeze patch on 2026-10-12. Nothing is marked passed unless it ran in the available environment.

## Executed and passed

- Backend unit/integration/security/acceptance suite: **43 passed, 5 skipped, 0 failed**.
- Technical-debt separation regression tests: passed. `unsupported_runtime` and `old_framework` now have independent predicates and evidence.
- Cost-comparison API regression test: passed and confirms all six strategies are returned.
- Explicit no-silent-fallback CP-SAT guard: passed. `solver_mode=cp-sat` returns `SOLVER UNAVAILABLE` when OR-Tools is missing.
- Python bytecode compilation for backend/tests/benchmarks/scripts: passed.
- Fresh Alembic migration against `/tmp/cloudmorph_freeze.db`: passed and created `alembic_version` and `portfolios`.
- 6R calibration diagnostic: executed across 500 synthetic applications / five seeds and saved to `benchmarks/recommendation_distribution.json`.
- 100/500/1,000 application benchmark: executed using the existing benchmark methodology and saved to `benchmarks/results.json` and `benchmarks/RESULTS.md`.
- Frontend TypeScript/TSX syntax transpilation smoke check using the installed TypeScript compiler API: **11 files, 0 syntax errors**. This is not a substitute for the production build.
- Frontend source audit confirms Architecture Risks, Technical Debt, Strategy Comparison, Security/Governance and Assumptions use typed presentation components rather than raw JSON as the primary view.
- Frontend source audit confirms Target Architecture uses the selected strategy and Cost Model uses the selected strategy across Rehost/Replatform/Refactor/Replace/Retain/Retire.
- Source scans found no TODO/FIXME markers, obvious private-key/API-key patterns, unsafe `yaml.load`, shell execution, or dynamic `eval`/`exec` patterns in the application source.

## Backend test skips — exact reason

Five tests are skipped only because OR-Tools is unavailable:

1. CP-SAT dependency + SCC grouping acceptance.
2. CP-SAT budget + capacity + risk-limit acceptance.
3. CP-SAT deadline + region + compliance acceptance.
4. CP-SAT infeasibility acceptance.
5. Existing explicit `solver_used=cp-sat` smoke acceptance.

A direct installation attempt using `python -m pip install 'ortools>=9.10,<10'` failed because the sandbox cannot resolve/reach PyPI.

## 6R calibration diagnostic

Across five heterogeneous 100-app synthetic portfolios (500 applications total):

- Replatform: **189 (37.8%)**
- Refactor: **159 (31.8%)**
- Retire: **101 (20.2%)**
- Replace: **49 (9.8%)**
- Rehost: **2 (0.4%)**
- Retain: **0 in this random sample**; explicit archetype tests prove Retain can win for a critical, highly coupled, low-test-maturity workload with high execution risk.

No strategy exceeded the 85% calibration-warning threshold. The diagnostic is not a target distribution.

## Final benchmark snapshot

Environment: Linux-6.18.44-x86_64-with-glibc2.41; Python 3.13.5; CPUs 5; RAM 5.82 GiB; OR-Tools available: False.

| Apps | Edges | Graph build ms | Graph/SCC analysis ms | Scoring ms | Sensitivity ms | Optimize ms | Pareto ms | Pareto attempted | Unique | Frontier | API p50 ms | API p95 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 118 | 1.582 | 18.601 | 19.655 | 151.788 | 24.527 | 769.220 | 36 | 32 | 29 | 28.138 | 41.306 |
| 500 | 630 | 2.343 | 63.538 | 115.607 | 750.718 | 78.070 | 3523.589 | 36 | 33 | 32 | 114.831 | 161.418 |
| 1000 | 1190 | 14.132 | 120.686 | 185.337 | 1425.744 | 207.257 | 12942.666 | 36 | 33 | 33 | 228.496 | 515.360 |

All optimizer timings above used `solver_used=deterministic_fallback`; they are **not CP-SAT benchmark results**.

## Frontend tests / lint / production build

Meaningful Vitest + Testing Library tests were added for:

- modernization assessment rendering;
- dependency/SCC graph data hand-off;
- migration optimizer controls;
- architecture strategy request selection;
- cost strategy selection and comparison request;
- Pareto rendering;
- migration-wave explanations;
- strategy-comparison rendering.

However, the package registry is unavailable in this sandbox.

- `npm install`: could not complete while registry access was unavailable.
- `npm install --offline --ignore-scripts`: failed with `ENOTCACHED`, confirming the required packages are not present in the npm cache.
- `npm test`: **NOT EXECUTED SUCCESSFULLY** — `vitest` is not installed.
- `npm run lint`: **NOT EXECUTED SUCCESSFULLY** — `eslint` is not installed.
- `npm run build`: **NOT PASSED** — the global TypeScript compiler runs, but React/Vite/type packages are absent, so module/type resolution fails before a real Vite production bundle can be produced.

No `package-lock.json` was fabricated.

## Dependency reproducibility

A legitimate Python resolution was also attempted with:

```bash
uv pip compile backend/requirements.txt -o backend/requirements.lock --offline
```

It failed because FastAPI and other registry packages are not in the local uv cache. No Python lockfile was fabricated.

See `docs/dependency-lock-status.md` for exact reproduction commands in a networked environment.

## Docker

**NOT EXECUTED — Docker binary is not installed in this sandbox.**

## Exact CP-SAT reproduction commands

In a networked environment:

```bash
python -m venv .venv
# activate the environment
pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest tests/unit/test_cp_sat_freeze_acceptance.py -q -rs
PYTHONPATH=backend python -m pytest tests/unit/test_upgrade_acceptance.py -q -k cp_sat -rs
```

Successful CP-SAT acceptance must show no skips and the tests assert `solver_used == "cp-sat"`. The CP-SAT acceptance file checks dependencies, SCC grouping, budget, team capacity, risk limits, deadlines, region restrictions, compliance restrictions and infeasibility.

## Exact frontend reproduction commands

```bash
cd frontend
npm install
npm test
npm run lint
npm run build
```

A successful networked run should generate and retain the real `package-lock.json`; do not hand-author one.
