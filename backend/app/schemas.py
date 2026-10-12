from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Criticality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Sensitivity(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class IntegrationType(str, Enum):
    api = "API"
    batch = "Batch"
    database = "Database"
    messaging = "Messaging"
    file_transfer = "File Transfer"
    legacy = "Legacy Integration"


class SupportStatus(str, Enum):
    unknown = "unknown"
    supported = "supported"
    extended = "extended"
    unsupported = "unsupported"
    eol = "eol"


class Strategy(str, Enum):
    rehost = "Rehost"
    replatform = "Replatform"
    refactor = "Refactor"
    replace = "Replace"  # type: ignore[assignment]
    retain = "Retain"
    retire = "Retire"


class Dependency(BaseModel):
    target: str = Field(min_length=1, max_length=120)
    integration_type: IntegrationType = IntegrationType.api
    synchronous: bool = True


class Application(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    business_domain: str = Field(default="General", max_length=80)
    owner: str = Field(default="Unassigned", max_length=120)
    business_criticality: Criticality = Criticality.medium
    business_value: float = Field(default=5, ge=0, le=10)
    change_frequency: float = Field(default=5, ge=0, le=10)
    runtime: str = Field(default="unknown", max_length=80)
    language: str = Field(default="unknown", max_length=80)
    framework: str = Field(default="unknown", max_length=80)
    runtime_version: str = Field(default="unknown", max_length=40)
    database: str | None = Field(default=None, max_length=120)
    database_size_gb: float = Field(default=10, ge=0, le=1_000_000)
    deployment_model: str = Field(default="vm", max_length=60)
    operating_system: str = Field(default="linux", max_length=80)
    traffic_rps: float = Field(default=10, ge=0, le=10_000_000)
    peak_traffic_rps: float = Field(default=20, ge=0, le=10_000_000)
    availability_requirement: float = Field(default=99.9, ge=0, le=100)
    rto_hours: float = Field(default=4, ge=0, le=8760)
    rpo_hours: float = Field(default=4, ge=0, le=8760)
    data_sensitivity: Sensitivity = Sensitivity.internal
    regulatory_tags: list[str] = Field(default_factory=list)
    estimated_current_cost: float = Field(default=1000, ge=0)
    technical_debt_score: float = Field(default=5, ge=0, le=10)
    support_status: SupportStatus = SupportStatus.unknown
    support_end_date: date | None = None
    team_skill_level: float = Field(default=5, ge=0, le=10)
    test_coverage: float = Field(default=50, ge=0, le=100)
    integration_count: int = Field(default=0, ge=0, le=10000)
    dependencies: list[Dependency] = Field(default_factory=list)
    deployment_frequency: float = Field(default=2, ge=0, le=1000)
    incident_frequency: float = Field(default=1, ge=0, le=1000)
    scalability_requirement: float = Field(default=5, ge=0, le=10)
    observability_maturity: float | None = Field(default=None, ge=0, le=10)
    identity_maturity: float | None = Field(default=None, ge=0, le=10)
    migration_effort: float = Field(default=5, gt=0, le=100)
    migration_risk: float = Field(default=5, ge=0, le=10)
    migration_cost: float = Field(default=10000, ge=0)
    residency_region: str | None = Field(default=None, max_length=40)
    maintenance_tag: str | None = Field(default=None, max_length=40)
    usage_level: float = Field(default=5, ge=0, le=10)
    commodity_fit: float = Field(default=5, ge=0, le=10)
    redundancy_score: float = Field(default=0, ge=0, le=10)
    replacement_fit: float = Field(default=5, ge=0, le=10)
    synthetic: bool = False

    @model_validator(mode="after")
    def validate_peak(self) -> "Application":
        if self.peak_traffic_rps < self.traffic_rps:
            raise ValueError("peak_traffic_rps must be >= traffic_rps")
        return self

    @field_validator("regulatory_tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        clean = sorted({x.strip().upper() for x in value if x.strip()})
        if any(len(x) > 32 for x in clean):
            raise ValueError("regulatory tag too long")
        return clean


class Portfolio(BaseModel):
    name: str = Field(default="CloudMorph Portfolio", min_length=1, max_length=120)
    applications: list[Application]
    synthetic: bool = False

    @model_validator(mode="after")
    def unique_ids(self) -> "Portfolio":
        ids = [a.application_id for a in self.applications]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate application_id")
        known = set(ids)
        missing = sorted(
            {d.target for a in self.applications for d in a.dependencies if d.target not in known}
        )
        if missing:
            raise ValueError(f"invalid dependency references: {missing[:8]}")
        return self


class ScoreWeights(BaseModel):
    cost_importance: float = Field(default=1.0, ge=0.25, le=2.0)
    debt_importance: float = Field(default=1.0, ge=0.25, le=2.0)
    risk_tolerance: float = Field(default=1.0, ge=0.25, le=2.0)
    business_value: float = Field(default=1.0, ge=0.25, le=2.0)
    time_pressure: float = Field(default=1.0, ge=0.25, le=2.0)
    availability_importance: float = Field(default=1.0, ge=0.25, le=2.0)
    operational_risk_importance: float = Field(default=1.0, ge=0.25, le=2.0)
    execution_risk_tolerance: float = Field(default=1.0, ge=0.25, le=2.0)
    scalability_importance: float = Field(default=1.0, ge=0.25, le=2.0)
    modernization_value_preference: float = Field(default=1.0, ge=0.25, le=2.0)


class AssessmentRequest(BaseModel):
    portfolio: Portfolio
    weights: ScoreWeights = Field(default_factory=ScoreWeights)


class ConstraintSet(BaseModel):
    max_waves: int = Field(default=8, ge=1, le=30)
    max_effort_per_wave: float = Field(default=80, gt=0)
    max_critical_apps_per_wave: int = Field(default=3, ge=0)
    max_risk_per_wave: float = Field(default=60, ge=0)
    budget_per_wave: float = Field(default=200_000, ge=0)
    team_capacity_per_wave: float = Field(default=80, gt=0)
    precedence: list[tuple[str, str]] = Field(default_factory=list)
    together: list[list[str]] = Field(default_factory=list)
    earliest_wave: dict[str, int] = Field(default_factory=dict)
    deadlines: dict[str, int] = Field(default_factory=dict)
    wave_regions: dict[int, str] = Field(default_factory=dict)
    compliance_allowed_waves: dict[str, list[int]] = Field(default_factory=dict)
    maintenance_allowed_waves: dict[str, list[int]] = Field(default_factory=dict)
    enforce_dependencies: bool = True


class ObjectiveWeights(BaseModel):
    cost: float = Field(default=0.2, ge=0, le=1)
    execution_risk: float = Field(default=0.2, ge=0, le=1)
    operational_risk_reduction: float = Field(default=0.2, ge=0, le=1)
    technical_debt_reduction: float = Field(default=0.2, ge=0, le=1)
    modernization_value: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="after")
    def nonzero(self) -> "ObjectiveWeights":
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("at least one objective weight must be > 0")
        return self


class OptimizeRequest(BaseModel):
    portfolio: Portfolio
    constraints: ConstraintSet = Field(default_factory=ConstraintSet)
    objective: str = Field(
        default="balanced_risk",
        pattern=r"^(risk|cost|debt|value|balanced|balanced_risk|minimize_execution_risk|reduce_operational_risk|weighted)$",
    )
    objective_weights: ObjectiveWeights | None = None
    solver_mode: str = Field(default="auto", pattern=r"^(auto|cp-sat|fallback)$")


class Scenario(BaseModel):
    name: str
    strategy_bias: dict[Strategy, float] = Field(default_factory=dict)
    weights: ScoreWeights = Field(default_factory=ScoreWeights)


class ScenarioRequest(BaseModel):
    portfolio: Portfolio
    scenarios: list[Scenario]


class CostRequest(BaseModel):
    application: Application
    assumptions: dict[str, float] | None = None


class ArchitectureRequest(BaseModel):
    application: Application
    strategy: Strategy
    assessment: dict[str, Any] | None = None
