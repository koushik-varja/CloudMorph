# CloudMorph

**Enterprise Modernization Graph & Migration Wave Optimizer**

CloudMorph is an original university engineering project for reasoning about a legacy application estate as a dependency graph, evaluating transparent modernization options, and producing constraint-valid migration waves. It is intentionally a **decision-support system**, not a cloud-migration oracle, pricing engine, compliance certification tool, or automatic deployment platform.

## What it solves

A flat “6R questionnaire” misses the hard part of estate modernization: dependencies, cyclic coupling, shared databases, blast radius, sequencing, capacity, budget, risk and uncertainty. CloudMorph turns a validated application portfolio into a directed dependency graph, detects coupling groups, diagnoses current-state risks, scores six modernization strategies, perturbs decision assumptions, and plans migration waves under explicit constraints.

Core flow:

`Portfolio → Dependency graph → Diagnosis → Strategy scores → Sensitivity → Constraint engine → Migration waves → Objective variants → Pareto frontier → Explainable roadmap → Target architecture`

## Architecture

```text
React + TypeScript + Vite
        │
        ▼
FastAPI / Pydantic
  ├─ importers + portfolio generator
  ├─ NetworkX graph engine
  ├─ deterministic strategy assessment
  ├─ sensitivity analysis
  ├─ cost / security models
  ├─ OR-Tools CP-SAT wave optimizer
  │    └─ validated deterministic fallback when OR-Tools is unavailable
  ├─ Pareto/scenario analysis
  └─ provider-neutral architecture + draft Terraform
        │
        ▼
SQLAlchemy + Alembic → PostgreSQL (Docker Compose)
```

The domain code is deliberately kept as focused modules under `backend/app/` rather than pretending each algorithm is a separate production microservice. See `docs/design-decisions.md`.

## Portfolio model

Applications include business criticality/value, runtime/framework/version, database and size, deployment model, traffic and availability, RTO/RPO, sensitivity/regulatory tags, current cost estimate, technical debt, explicit support status/support end date, team/test maturity, integrations/dependencies, deployment/incident frequency, scalability, migration effort/risk/cost, residency and maintenance metadata. Pydantic validates ranges, enums, duplicate IDs and dangling dependency references.

Imports support CSV, JSON, Docker Compose YAML and a conservative subset of Kubernetes workload YAML. Compose/Kubernetes parsers only infer facts actually present in those files; they do not invent business criticality, revenue impact or compliance.

## Graph engine

An edge `A → B` means A depends on B. CloudMorph uses only metrics that support migration decisions:

- in/out degree and dependency reach;
- SCCs as migration coupling groups;
- ancestor-based blast radius;
- dependency depth on the SCC condensation DAG;
- betweenness (exact through 300 nodes, sampled with fixed seed above 300);
- articulation-like bridges on the undirected projection;
- orphan detection and shared-database coupling.

See `docs/graph-model.md`.

## Decision framework

Each application is scored separately for Rehost, Replatform, Refactor, Replace, Retain and Retire. The formulas are explicit in `backend/app/assessment.py`; outputs include dimension scores, all strategy scores, winner, runner-up, score margin, confidence and evidence-based reasons.

There is no trained ML model. That avoids pretending a synthetic or unlabeled portfolio can support a credible learned classifier, and there is therefore no hidden training target or target-leakage pipeline. Sensitivity is handled separately by seeded perturbation of cost, debt, operational-risk, execution-risk tolerance, business value, time pressure, scalability and modernization-value preferences. Decision confidence combines score margin, perturbation stability and input completeness in the bundled analysis endpoint.

## Migration optimization

The optimizer is the technical centerpiece. It collapses SCCs and explicit together-groups, then enforces:

- strict `A before B` rules;
- dependency order (`dependency target ≤ dependent` so compatible applications may move in the same wave);
- earliest waves and deadlines;
- maximum effort and team capacity per wave;
- maximum risk and critical applications per wave;
- budget per wave;
- region/data-residency matching;
- compliance-tag allowed waves;
- maintenance-window tags.

With OR-Tools installed, CP-SAT solves the model. A deterministic topological fallback exists for environments where OR-Tools is unavailable; it is **not claimed globally optimal**. Every returned assignment is independently validated. Conflicts return `NO FEASIBLE PLAN` instead of silently dropping constraints.

Objectives distinguish `minimize_execution_risk`, `reduce_operational_risk`, `balanced_risk`, `cost`, `debt`, `value` and weighted multi-objective sweeps. The two risk concepts are intentionally separate. Pareto analysis attempts 36 preset/weighted candidates by default, canonicalizes duplicate wave structures, and retains only mathematically non-dominated plans over cost-frontloading, execution-risk exposure, operational-risk delay, debt-reduction priority, modernization-value priority and duration. These are planning indices—not guaranteed savings.

See `docs/migration-optimization.md`.

## Cost model

CloudMorph has no live provider-pricing connection. Cost output is labeled **ILLUSTRATIVE ESTIMATE** and returns every configurable assumption and the formula used. It never claims “AWS/Azure/GCP saves X%” unless the user supplies validated pricing inputs outside this demo model. See `docs/cost-model.md`.


### Technical-debt lifecycle vs framework factors

The calculated technical-debt index intentionally separates **unsupported runtime/support lifecycle** from **old framework architecture**. `unsupported_runtime` is triggered only by explicit lifecycle evidence (unsupported/EOL support status, unsupported/EOL runtime metadata, or an expired support-end date). `old_framework` is triggered only by legacy framework indicators such as Struts/CICS. A legacy framework does not automatically assert an unsupported runtime, and an expired runtime support date does not automatically assert an old framework. This prevents the same condition from being counted twice under two labels.

## Target architecture and security

Target architecture is provider-neutral and requirement-driven. It responds to availability, criticality, RTO/RPO, statefulness, traffic/scalability, data sensitivity, asynchronous integrations and shared-database warnings. Refactor does **not** automatically mean microservices: low-complexity cases can produce a modular monolith, while selective decomposition is reserved for higher change/integration pressure.

The Terraform endpoint returns a **DRAFT** starter and never runs Terraform or requests credentials. It intentionally emits no provider resources until a human chooses and reviews a provider-specific implementation. Security output says controls are *relevant to* a requirement; it never claims compliance certification. See `docs/security-considerations.md`.

## Dashboard

The React UI has 15 decision-support views: Portfolio Overview, Application Inventory, Dependency Graph, Architecture Risks, Technical Debt, Modernization Assessment, Decision Sensitivity, Strategy Comparison, Migration Wave Optimizer, Pareto Frontier, Migration Roadmap, Target Architecture, Cost Model, Security/Governance and Assumptions. Demo-load, import, analysis, optimization, scenario, architecture and cost controls call real API endpoints. Architecture risk, technical debt, scenario comparison, security/governance and assumptions use readable decision-support tables/cards with optional raw-result inspection. Modernization and sensitivity views use score/stability bars, migration waves expose “why this wave”, Pareto output is visualized as a scatter plot, architecture strategy is user-selectable, and all six cost strategies plus illustrative comparison are exposed without hiding assumptions.

## Quick start — Docker (preferred)

Prerequisites: Docker with Compose.

```bash
cp .env.example .env
# edit POSTGRES_PASSWORD in .env
docker compose up --build
```

Open `http://localhost:5173`. The API is at `http://localhost:8000` and FastAPI docs at `http://localhost:8000/docs`.

Docker Compose starts PostgreSQL, runs Alembic migrations in the backend container, then serves the React production bundle through nginx.

## Local development

Backend:

```bash
python -m venv .venv
# activate the environment
pip install -r backend/requirements-dev.txt
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

The direct local backend defaults to SQLite for zero-configuration development. Production Compose uses PostgreSQL. Set `DATABASE_URL` to test PostgreSQL locally without Docker.

## Demo

Generate a clearly labeled synthetic estate:

```bash
PYTHONPATH=backend python scripts/generate_demo.py --size 100 --out sample-data/synthetic-100.json
```

Or use the dashboard buttons for 100, 500 or 1,000 applications. Synthetic portfolios intentionally contain dependency chains, hubs, shared databases, multiple integration styles and SCCs.

## Tests and quality

```bash
cd backend
pytest ../tests
cd ..
ruff check backend tests benchmarks scripts
cd backend && mypy app
cd ../frontend && npm test && npm run lint && npm run build
```

The current acceptance suite includes graph construction, SCCs/blast radius/shared databases, explicit 6R archetypes, recommendation diversity, monotonic availability complexity, operational-vs-execution risk, risk-objective ordering, confidence/sensitivity, configurable costs, requirement-driven architecture, dependency/SCC grouping, capacity/budget/region/compliance/maintenance/deadline constraints, infeasibility explanations, Pareto dominance/deduplication/directionality, migration-delay simulation, path traversal, oversized files, safe YAML, invalid references, persistence and API integration. The frontend test source covers assessment rendering, SCC/dependency graph data, optimizer controls, architecture/cost strategy selection, Pareto rendering, wave explanations and strategy comparison. CP-SAT-specific tests cover dependencies/SCC grouping, budget, capacity, risk, deadline, region, compliance and infeasibility and are skipped only when OR-Tools is unavailable.

## Benchmarks

Run:

```bash
PYTHONPATH=backend python benchmarks/run_benchmarks.py
```

Actual results from the repository build session are stored in `benchmarks/results.json` and `benchmarks/RESULTS.md`. They record hardware, graph size, timings, solver path and API p50/p95. Results are generated, not hardcoded. The final verification environment had **no OR-Tools package available** and outbound PyPI access failed, so recorded optimizer timings explicitly use `solver_used=deterministic_fallback`. Explicit `solver_mode=cp-sat` never falls back silently: it returns `SOLVER UNAVAILABLE` when OR-Tools is missing. Install `backend/requirements.txt` in a networked environment and rerun the CP-SAT acceptance test to verify that path.

## Repository map

```text
CloudMorph/
├── backend/              FastAPI, domain engines, DB, Alembic, Dockerfile
├── frontend/             React/TypeScript/Vite decision-support UI
├── tests/                unit, integration and security-focused behavior tests
├── benchmarks/           benchmark runner + generated real results
├── scripts/              demo generator + 6R calibration diagnostic
├── sample-data/          clearly labeled synthetic 100-app portfolio
├── docs/                 methodology, graph, optimization, cost, security, decisions
├── docker-compose.yml    PostgreSQL + backend + frontend
├── Makefile
├── .env.example
├── THIRD_PARTY.md
└── LICENSE
```

## Known limitations

- CloudMorph is not a substitute for full enterprise discovery, interviews, CMDB reconciliation or production telemetry.
- The bundled demo portfolio is synthetic and clearly labeled.
- The cost model is illustrative and not live cloud-provider pricing.
- Compose/Kubernetes imports cannot discover business metadata that is absent from source configuration.
- No real cloud deployment is required or performed.
- Architecture and strategy outputs are decision support, not autonomous architecture truth.
- Optimization quality depends on the correctness of input assumptions and constraints.
- The deterministic fallback is feasibility-oriented and is not globally optimal; use the declared OR-Tools dependency for CP-SAT optimization.
- The final sandbox could not resolve Python/npm dependency lockfiles because outbound package registries were unavailable; `docs/dependency-lock-status.md` records the exact limitation rather than presenting a fabricated lock.
- NetworkX is appropriate for the demonstrated university scale, not claimed as a massive-enterprise graph database.
- Provider-specific service mappings and real pricing integrations are intentionally outside the core offline project.

## Academic integrity and provenance

The implementation, formulas, UI, examples and documentation in this repository are original for CloudMorph. Industry-standard terms (including the common migration strategy names) are used descriptively. No Accenture asset, commercial migration UI, customer data or public cloud-assessment repository is copied into the project.
