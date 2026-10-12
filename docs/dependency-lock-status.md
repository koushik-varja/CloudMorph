# Dependency lock status

The final freeze requires real dependency locks only when package resolution is available. It was not available in this execution environment.

## What was attempted

### Python

`python -m pip install 'ortools>=9.10,<10'` failed after DNS/network retries because PyPI could not be resolved.

A second resolution attempt used uv's offline mode:

```bash
uv pip compile backend/requirements.txt -o backend/requirements.lock --offline
```

It failed because required packages such as FastAPI are not present in the local uv cache.

### Frontend

`npm install` could not complete while registry access was unavailable. An explicit cache-only attempt:

```bash
npm install --offline --ignore-scripts
```

failed with `ENOTCACHED` for registry packages.

Therefore CloudMorph-final-v2 intentionally includes **no fabricated `package-lock.json`, `uv.lock`, or requirements lockfile**.

## Generate real locks in a networked environment

Python:

```bash
python -m pip install uv
uv pip compile backend/requirements-dev.txt -o backend/requirements.lock
```

Frontend:

```bash
cd frontend
npm install
# npm writes package-lock.json from the resolved dependency graph
npm test
npm run lint
npm run build
```

Commit the generated lockfiles only after successful resolution and verification.
