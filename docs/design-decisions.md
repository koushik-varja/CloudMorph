# Design decisions

## One backend, domain modules
The original specification showed many top-level domain folders. CloudMorph keeps these as focused modules under `backend/app/` instead. This avoids a fake microservice architecture and lets one student run, understand, and defend the project.

## PostgreSQL production, SQLite verification
Docker Compose configures PostgreSQL. SQLAlchemy/Alembic remain database-portable enough for the execution sandbox to run migrations and integration tests against SQLite when Docker/PostgreSQL are unavailable.

## NetworkX with bounded expensive metrics
NetworkX is sufficient for the intended university-scale estates. Betweenness is sampled above 300 nodes. The project does not claim million-node graph performance.

## OR-Tools plus validated fallback
CP-SAT is the intended optimizer and is declared in runtime dependencies. The execution sandbox had no network and no OR-Tools installation, so an independently validated deterministic fallback exists rather than substituting a fake solver result.

## React client, no “AI” theater
The UI is a decision-support workstation with tables, graph exploration, assumptions, wave plans, Pareto output and explainability. There is no chatbot, fake generative AI feature, or cloud-provider UI imitation.
