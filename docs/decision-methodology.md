# Decision methodology

CloudMorph is deterministic decision support, not a classifier and not an autonomous architecture oracle. The six supported strategies are Rehost, Replatform, Refactor, Replace, Retain and Retire. The authoritative formulas live in `backend/app/assessment.py` and are deliberately inspectable.

## Risk separation

CloudMorph does **not** use one overloaded risk number.

- **Current operational risk** estimates the pressure to change the existing workload: technical debt, declared/derived support risk, incidents, resilience gap and graph coupling.
- **Migration execution risk** estimates the difficulty of changing it: dependency pressure, data volume, downtime/availability constraints, low test coverage, team skill gap, graph coupling and the user-supplied migration-risk input.

High operational risk strengthens the case to modernize earlier. High execution risk can instead justify preparation, grouping, staged change or a later wave. `backend/app/risk_model.py` contains these transparent formulas.

## Availability complexity

Availability is transformed through annual downtime tolerance. Stricter availability produces equal or greater migration complexity. Tests explicitly check 99.0%, 99.9% and 99.99% monotonicity.

## Strategy criteria

The scoring engine uses business value, criticality, technical debt, operational risk, execution risk, change frequency, scalability, test/team maturity, usage, commodity/replacement fit and redundancy. The intended semantics are:

- **Rehost**: healthy/low-debt workload, adequate maturity, time pressure and manageable execution risk.
- **Replatform**: useful application with moderate modernization need and platform/scaling benefit without enough justification for deep refactoring.
- **Refactor**: high-value, high-change, high-debt/scaling workload where test/team maturity can support deeper change.
- **Replace**: commodity capability, poor custom implementation and credible replacement fit.
- **Retain**: critical/high-execution-risk workloads where near-term migration is unattractive, especially with weak test maturity, provided current operational risk does not overwhelmingly demand immediate change.
- **Retire**: low-value, low-usage, low-change and/or redundant workloads.

These are weighted criteria, not rigid if/else business rules. All scores are bounded to 0–100 and exposed to the UI/API.

## Confidence and sensitivity

The bundled `/api/analyze` result combines three pieces of evidence:

1. winner/runner-up score margin;
2. recommendation stability under seeded parameter perturbation;
3. input completeness.

Sensitivity varies cost, debt, risk, business-value, time-pressure, availability, scalability and modernization preferences. The returned recommendation distribution is explicitly described as **decision stability under parameter perturbation**, not a Bayesian probability.

## Calibration diagnostic

`scripts/calibration_diagnostic.py` evaluates multiple heterogeneous synthetic portfolios and warns if a single strategy exceeds an 85% share. It does not enforce target percentages. Explicit archetype tests prove that each strategy can become reasonable even when it does not happen to appear in a random sample.
