from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .architecture import generate_architecture, terraform_starter
from .assessment import assess_portfolio, diagnoses
from .config import settings
from .cost_model import CostAssumptions, estimate_cost
from .db import Base, SessionLocal, engine
from .generator import generate_portfolio
from .graph_engine import analyze_graph, graph_payload
from .importers import ImportErrorDetail, parse_portfolio_bytes
from .optimizer import optimize_waves
from .pareto import pareto_frontier
from .scenarios import compare_scenarios
from .schemas import (
    ArchitectureRequest,
    AssessmentRequest,
    CostRequest,
    OptimizeRequest,
    Portfolio,
    ScenarioRequest,
    Strategy,
)
from .security_analysis import assess_security
from .sensitivity import run_sensitivity
from .simulation import simulate_plan
from .storage import get_portfolio, save_portfolio
from .technical_debt import calculate_technical_debt


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Alembic is preferred for production; create_all keeps direct local execution usable.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="CloudMorph",
    version="1.0.0",
    description="Enterprise Modernization Graph & Migration Wave Optimizer",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "cloudmorph", "version": "1.0.0"}


@app.post("/api/portfolio/import")
async def import_portfolio(
    file: UploadFile = File(...), persist: bool = Query(False), db: Session = Depends(db_session)
) -> dict:
    filename = file.filename or ""
    data = await file.read(settings.max_upload_bytes + 1)
    try:
        portfolio = parse_portfolio_bytes(filename, data, settings.max_upload_bytes)
    except ImportErrorDetail as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pid = save_portfolio(db, portfolio) if persist else None
    return {
        "portfolio_id": pid,
        "portfolio": portfolio.model_dump(mode="json"),
        "source": "user upload",
    }


@app.post("/api/portfolio/save")
def persist_portfolio(portfolio: Portfolio, db: Session = Depends(db_session)) -> dict:
    return {"portfolio_id": save_portfolio(db, portfolio)}


@app.get("/api/portfolio/{portfolio_id}")
def load_portfolio(portfolio_id: int, db: Session = Depends(db_session)) -> dict:
    portfolio = get_portfolio(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return portfolio.model_dump(mode="json")


@app.get("/api/demo/{size}")
def demo(size: int, seed: int = 42) -> dict:
    if size not in {100, 500, 1000}:
        raise HTTPException(status_code=400, detail="demo size must be 100, 500, or 1000")
    return generate_portfolio(size, seed).model_dump(mode="json")


@app.post("/api/graph")
def graph(portfolio: Portfolio) -> dict:
    return {**graph_payload(portfolio), "analysis": analyze_graph(portfolio)}


@app.post("/api/analyze")
def analyze(req: AssessmentRequest, samples: int = Query(80, ge=10, le=1000)) -> dict:
    graph_analysis = analyze_graph(req.portfolio)
    assessment_rows = assess_portfolio(req.portfolio, req.weights, graph_analysis)
    sensitivity_rows = run_sensitivity(
        req.portfolio, samples=samples, seed=settings.seed, graph_analysis=graph_analysis
    )
    sensitivity_by_id = {row["application_id"]: row for row in sensitivity_rows}
    for row in assessment_rows:
        stability = sensitivity_by_id[row["application_id"]]
        row["confidence"] = stability["confidence"]
        row["confidence_reason"] = stability["confidence_reason"]
        row["decision_stability"] = stability["decision_stability"]
        row["recommendation_distribution"] = stability["recommendation_distribution"]
        row["most_influential_factors"] = stability["most_influential_factors"]
    return {
        "graph": {**graph_payload(req.portfolio), "analysis": graph_analysis},
        "diagnosis": diagnoses(req.portfolio, graph_analysis),
        "technical_debt": calculate_technical_debt(req.portfolio, graph_analysis),
        "assessment": assessment_rows,
        "sensitivity": sensitivity_rows,
        "security": assess_security(req.portfolio),
    }


@app.post("/api/diagnosis")
def diagnosis(portfolio: Portfolio) -> list[dict]:
    return diagnoses(portfolio)


@app.post("/api/technical-debt")
def technical_debt(portfolio: Portfolio) -> list[dict]:
    return calculate_technical_debt(portfolio)


@app.post("/api/assessment")
def assessment(req: AssessmentRequest) -> list[dict]:
    return assess_portfolio(req.portfolio, req.weights)


@app.post("/api/sensitivity")
def sensitivity(req: AssessmentRequest, samples: int = Query(80, ge=10, le=1000)) -> list[dict]:
    return run_sensitivity(req.portfolio, samples=samples, seed=settings.seed)


@app.post("/api/optimize")
def optimize(req: OptimizeRequest) -> dict:
    return optimize_waves(
        req.portfolio, req.constraints, req.objective, req.objective_weights, req.solver_mode
    )


@app.post("/api/pareto")
def pareto(req: OptimizeRequest) -> dict:
    return pareto_frontier(req.portfolio, req.constraints, solver_mode=req.solver_mode)


@app.post("/api/simulate")
def simulate(req: OptimizeRequest, runs: int = Query(250, ge=10, le=5000)) -> dict:
    plan = optimize_waves(
        req.portfolio, req.constraints, req.objective, req.objective_weights, req.solver_mode
    )
    if plan.get("status") != "FEASIBLE":
        return {"plan": plan, "simulation": None}
    return {
        "plan": plan,
        "simulation": simulate_plan(req.portfolio, plan["waves"], runs=runs, seed=settings.seed),
    }


@app.post("/api/scenarios")
def scenarios(req: ScenarioRequest) -> list[dict]:
    return compare_scenarios(req.portfolio, req.scenarios)


@app.post("/api/architecture")
def architecture(req: ArchitectureRequest) -> dict:
    return generate_architecture(req.application, req.strategy)


@app.post("/api/terraform-draft")
def terraform_draft(req: ArchitectureRequest) -> dict:
    return {
        "status": "DRAFT",
        "auto_apply": False,
        "terraform": terraform_starter(req.application, req.strategy),
    }


@app.post("/api/security")
def security(portfolio: Portfolio) -> list[dict]:
    return assess_security(portfolio)


@app.post("/api/cost/{strategy}")
def cost(strategy: Strategy, req: CostRequest) -> dict:
    assumptions = CostAssumptions(**(req.assumptions or {}))
    return estimate_cost(req.application, strategy, assumptions)


@app.post("/api/cost-compare")
def cost_compare(req: CostRequest) -> dict:
    assumptions = CostAssumptions(**(req.assumptions or {}))
    strategies = list(Strategy)
    return {
        "current_estate_monthly_input": req.application.estimated_current_cost,
        "alternatives": [
            estimate_cost(req.application, strategy, assumptions) for strategy in strategies
        ],
        "assumption_label": "ILLUSTRATIVE SAMPLE VALUES unless explicitly overridden by the user",
    }
