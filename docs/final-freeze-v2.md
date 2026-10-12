# Final freeze v2 patch

This patch is deliberately surgical. The graph engine, 6R calibration, SCC handling, risk formulas, sensitivity engine, migration constraints, fallback optimizer, Pareto mathematics, cost formulas, security model, architecture rules and benchmark methodology were preserved.

## Technical debt correction

`unsupported_runtime` and `old_framework` are independent factors:

- `unsupported_runtime`: explicit `support_status` of `unsupported`/`eol`, unsupported/EOL runtime metadata, or an expired `support_end_date`.
- `old_framework`: legacy framework architecture markers such as Struts/CICS.

The same framework condition is no longer counted under both labels. Missing support lifecycle metadata remains `unknown`; CloudMorph does not invent EOL status.

## Frontend freeze polish

Architecture Risks, Technical Debt, Strategy Comparison, Security/Governance and Assumptions now use readable tables/cards as the primary view. Structured JSON remains available through collapsible inspection sections. Target Architecture and Cost Model now expose all six strategies. Cost comparison uses the existing backend endpoint and is explicitly labeled illustrative.

## Reproducibility and verification

Dependency locks are generated only if package resolution succeeds. CP-SAT acceptance is executed only if OR-Tools is actually available. See `docs/verification-report.md` for the final executed/not-executed status.
