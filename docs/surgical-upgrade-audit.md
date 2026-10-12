# Surgical upgrade audit

| Feature | Existing implementation | Correct before upgrade? | Main weakness found | Surgical action |
|---|---|---:|---|---|
| Portfolio/importers | Pydantic + CSV/JSON/Compose/K8s parsers | Yes | New decision fields absent | Preserved parsers; added validated optional decision metadata |
| Graph/SCC/blast radius/shared DB | NetworkX directed graph | Yes | None requiring rewrite | Preserved |
| 6R scoring | Transparent rule model | Partly | Strong Replatform bias; weak Retire/Replace semantics | Recalibrated around explicit archetypes and added semantic tests |
| Availability complexity | Formula inside dimensions | No | Inverted: stricter availability lowered complexity | Replaced with downtime-tolerance monotonic transform |
| Risk model | Single migration-risk concept | No | Operational and execution risk conflated | Added separate risk model and UI/API exposure |
| Risk objective | `risk * wave` style prioritization | No | Could move high execution-risk work earlier | Added minimize-execution, reduce-operational and balanced-risk objectives |
| Confidence | Score gap | Weak | Ignored sensitivity/input completeness | Combined margin, perturbation stability and completeness |
| Sensitivity | Seeded weight perturbation | Mostly | Too few semantic factors | Expanded factors and explicit non-probability labeling |
| CP-SAT | Implemented optional path | Unverified | Runtime path had never been executed here | Added explicit solver mode and CP-only tests; sandbox still cannot install OR-Tools |
| Deterministic fallback | Greedy topological planner | Yes | Solver identity ambiguous | Kept, labeled, and independently revalidated |
| Pareto | Five objective presets | No | Too shallow; weak frontier | Added 36-plan preset/weighted sweep, deduplication and true non-dominance |
| Cost | Transparent backend model | Partly | API/UI used defaults only | Added assumption override API + editable UI |
| Technical debt | Weighted components | Partly | Runtime lifecycle and old-framework factors shared one predicate, causing double counting | Separated explicit runtime/support lifecycle evidence from framework-architecture evidence; added regression tests |
| Target architecture | Provider-neutral rule generator | Weak | Too generic | Added RTO/RPO, HA, sensitivity, async integration and shared-DB reasoning; avoided automatic microservices |
| Simulation | Independent Bernoulli events | Weak | No dependency delay propagation | Added prerequisite-wave delay propagation and P50/P90-style outputs |
| Wave explanations | Wave-level reasons | Mostly | Not enough risk distinction | Added execution/operational risk and richer placement reasons |
| Frontend | 15-view React UI | Partly | Raw JSON for primary decision views | Added typed assessment, sensitivity, Pareto, architecture and cost views; enhanced graph selection/highlighting |
| TypeScript config | Project references | No | `allowImportingTsExtensions` lacked `noEmit` | Fixed `tsconfig.node.json` |
| Lockfiles | None | No | Offline registries prevent legitimate generation | Documented exact limitation; did not fabricate lockfiles |
| Security controls | Safe YAML/upload checks/no auto-Terraform | Yes | None requiring redesign | Preserved and re-audited |
