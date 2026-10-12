# Migration optimization

CloudMorph first collapses strongly connected components and explicit `together` groups. Cyclic applications therefore cannot be split across waves. The resulting group DAG receives strict precedence (`A before B`) plus non-strict dependency ordering (`dependency target <= dependent`).

The optimizer enforces earliest wave, deadline, effort, team capacity, declared migration-risk capacity, budget, critical-app caps, residency-region matching, compliance-tag allowed waves and maintenance windows. Every candidate is independently revalidated after solving.

## Solver paths

- `solver_mode=auto`: use CP-SAT when OR-Tools is installed; otherwise use the deterministic fallback.
- `solver_mode=cp-sat`: require CP-SAT. If OR-Tools is missing, return `SOLVER UNAVAILABLE`; never silently fall back.
- `solver_mode=fallback`: explicitly exercise the deterministic feasibility-oriented planner.

The fallback is not claimed globally optimal.

## Risk objectives

- `minimize_execution_risk`: prefer lower execution-risk groups earlier when constraints require sequencing.
- `reduce_operational_risk`: prioritize applications whose current operation is riskier to leave unchanged.
- `balanced_risk`: balances those opposing pressures with debt/value considerations.
- `cost`, `debt`, `value`: sequencing-oriented single-objective variants.
- `weighted`: configurable multi-objective combination used by the Pareto candidate sweep.

## Pareto frontier

`backend/app/pareto.py` generates preset plans plus a sparse weighted sweep (36 attempts by default), canonicalizes wave structures, removes duplicates, and performs true non-dominance checks. Directions are explicit:

- capital front-load exposure: minimize;
- execution-risk early exposure: minimize;
- operational-risk delay: minimize;
- duration: minimize;
- technical-debt reduction priority: maximize;
- modernization-value priority: maximize.

A plan is retained only when no other candidate is no worse in every objective and strictly better in at least one. The frontier is a decision set, not one “best” roadmap.

## Infeasibility

CloudMorph returns `NO FEASIBLE PLAN` rather than dropping constraints. It reports practical conflict hints such as total capacity shortfalls, impossible allowed-wave intersections and strict precedence depth. These hints are not presented as a formal CP-SAT unsat core.
