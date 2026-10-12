.PHONY: install test lint typecheck api frontend benchmark compose
install:
	python -m pip install -r backend/requirements-dev.txt
	cd frontend && npm install

test:
	cd backend && pytest ../tests

lint:
	ruff check backend tests benchmarks scripts

typecheck:
	cd backend && mypy app

api:
	cd backend && uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

benchmark:
	PYTHONPATH=backend python benchmarks/run_benchmarks.py

compose:
	docker compose up --build
