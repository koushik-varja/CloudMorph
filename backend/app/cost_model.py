from __future__ import annotations
from pydantic import BaseModel, Field
from .schemas import Application, Strategy


class CostAssumptions(BaseModel):
    compute_per_rps_month: float = Field(default=0.8, ge=0)
    storage_per_gb_month: float = Field(default=0.12, ge=0)
    managed_db_base_month: float = Field(default=180, ge=0)
    network_fraction: float = Field(default=0.08, ge=0, le=1)
    operations_fraction: float = Field(default=0.12, ge=0, le=1)
    engineer_hourly_rate: float = Field(default=45, ge=0)
    effort_unit_hours: float = Field(default=40, ge=1)
    license_monthly: float = Field(default=0, ge=0)


STRATEGY_EFFORT = {
    Strategy.rehost: 0.7,
    Strategy.replatform: 1.0,
    Strategy.refactor: 1.8,
    Strategy.replace: 1.4,
    Strategy.retain: 0.1,
    Strategy.retire: 0.5,
}
STRATEGY_RUN = {
    Strategy.rehost: 0.95,
    Strategy.replatform: 0.82,
    Strategy.refactor: 0.75,
    Strategy.replace: 0.8,
    Strategy.retain: 1.0,
    Strategy.retire: 0.05,
}


def estimate_cost(
    app: Application, strategy: Strategy, assumptions: CostAssumptions | None = None
) -> dict:
    a = assumptions or CostAssumptions()
    compute = app.peak_traffic_rps * a.compute_per_rps_month
    storage = app.database_size_gb * a.storage_per_gb_month
    db = a.managed_db_base_month if app.database else 0
    base = compute + storage + db + a.license_monthly
    network = base * a.network_fraction
    operations = base * a.operations_fraction
    run_monthly = (base + network + operations) * STRATEGY_RUN[strategy]
    migration = (
        app.migration_effort
        * a.effort_unit_hours
        * a.engineer_hourly_rate
        * STRATEGY_EFFORT[strategy]
    )
    return {
        "label": "ILLUSTRATIVE ESTIMATE — configurable assumptions, not provider pricing",
        "strategy": strategy.value,
        "monthly_run_cost_estimate": round(run_monthly, 2),
        "migration_effort_cost_estimate": round(migration, 2),
        "annualized_first_year_estimate": round(run_monthly * 12 + migration, 2),
        "assumptions": a.model_dump(),
        "formula": "run=(compute+storage+managed_db+license)*(1+network_fraction+operations_fraction)*strategy_run_factor; migration=effort*hours_per_effort*hourly_rate*strategy_effort_factor",
    }
