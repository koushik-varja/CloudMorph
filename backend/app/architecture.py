from __future__ import annotations
from .schemas import Application, Strategy


def generate_architecture(app: Application, strategy: Strategy) -> dict:
    components: list[dict] = []
    edges: list[tuple[str, str]] = []
    warnings: list[str] = []

    def add(cid: str, label: str, why: str) -> None:
        if not any(c["id"] == cid for c in components):
            components.append({"id": cid, "label": label, "why": why})

    add(
        "entry",
        "Controlled Ingress / Load Balancing",
        f"Traffic entry is controlled for {app.availability_requirement}% availability and {app.peak_traffic_rps:.0f} peak RPS.",
    )
    if strategy == Strategy.retain:
        pattern = "retain existing architecture"
        add(
            "compute",
            "Existing Runtime Boundary",
            "Retention preserves the current runtime while governance and observability gaps are addressed.",
        )
    elif strategy == Strategy.rehost:
        pattern = "virtualized / minimal-change compute"
        add(
            "compute",
            "Virtual Compute",
            "Rehost minimizes code change while moving the runtime boundary.",
        )
    elif strategy == Strategy.replatform:
        pattern = (
            "containerized monolith" if app.integration_count < 6 else "containerized services"
        )
        add(
            "compute",
            "Container Platform",
            "Replatform improves deployment/runtime operations without assuming a microservices decomposition.",
        )
    elif strategy == Strategy.refactor:
        if app.change_frequency >= 7 and app.integration_count >= 6:
            pattern = "service decomposition"
            add(
                "compute",
                "Service-Oriented Application Boundary",
                "High change rate and integration pressure justify selective decomposition; this is not a blanket microservices recommendation.",
            )
        else:
            pattern = "modular monolith"
            add(
                "compute",
                "Modular Application Runtime",
                "Refactoring is warranted, but current complexity does not justify distributed microservices.",
            )
    elif strategy == Strategy.replace:
        pattern = "managed capability replacement"
        add(
            "compute",
            "Managed / SaaS Capability Boundary",
            "Replacement fit moves commodity capability behind a controlled integration boundary.",
        )
    else:
        pattern = "retirement / archival"
        add(
            "compute",
            "Retirement Redirect / Archive",
            "Retirement requires controlled traffic removal and data disposition.",
        )
    edges.append(("entry", "compute"))
    if app.database and strategy != Strategy.retire:
        add(
            "data",
            "Managed Relational Database",
            f"The application declares {app.database_size_gb:.1f} GB state and RPO={app.rpo_hours}h.",
        )
        edges.append(("compute", "data"))
        if "shared" in app.database.lower() or "oracle" in app.database.lower():
            warnings.append(
                "Shared/legacy database coupling should be treated as a migration blocker or decomposition dependency, not silently split."
            )
    if app.availability_requirement >= 99.99 or app.business_criticality.value == "critical":
        add(
            "ha",
            "Failure-Isolated Multi-Zone Pattern",
            "High criticality/availability requires failure isolation and tested failover.",
        )
    if app.rpo_hours <= 1 and strategy != Strategy.retire:
        add(
            "replication",
            "Continuous Replication / Data Protection",
            f"RPO={app.rpo_hours}h requires stronger replication/data-protection controls than periodic backup alone.",
        )
    if app.rto_hours <= 1:
        add(
            "dr",
            "Rapid Recovery / DR Runbook",
            f"RTO={app.rto_hours}h requires rehearsed recovery and automation.",
        )
    async_integrations = sum(
        1
        for d in app.dependencies
        if not d.synchronous or d.integration_type.value in {"Messaging", "Batch"}
    )
    if async_integrations >= 2:
        add(
            "integration",
            "Message / Event Integration",
            f"{async_integrations} asynchronous/batch dependencies justify decoupled messaging for those flows.",
        )
        edges.append(("compute", "integration"))
    if app.scalability_requirement >= 8 or app.peak_traffic_rps >= 1000:
        add(
            "scale",
            "Horizontal Scaling Policy",
            "Peak traffic/scalability requirements justify explicit autoscaling and load testing.",
        )
    add(
        "iam",
        "IAM / Least Privilege",
        "Centralizes authorization and limits workload/operator permissions.",
    )
    add(
        "secrets",
        "Secret Management",
        "Keeps credentials outside code, images and repository configuration.",
    )
    add(
        "obs",
        "Logs / Metrics / Traces",
        "Migration validation and production diagnosis require observable behavior.",
    )
    add(
        "backup",
        "Backup / Recovery",
        f"Backup and restore tests must demonstrate the declared RTO={app.rto_hours}h and RPO={app.rpo_hours}h.",
    )
    if app.data_sensitivity.value in {"confidential", "restricted"}:
        add(
            "segmentation",
            "Audit Logging + Segmented Network",
            "Sensitive data requires controlled ingress, encryption, isolation and auditable access.",
        )
    return {
        "application_id": app.application_id,
        "strategy": strategy.value,
        "provider_neutral": True,
        "pattern": pattern,
        "components": components,
        "edges": [{"source": a, "target": b} for a, b in edges],
        "warnings": warnings,
        "governance_note": "These controls support requirements relevant to security/compliance; they do not constitute certification.",
    }


def terraform_starter(app: Application, strategy: Strategy) -> str:
    arch = generate_architecture(app, strategy)
    comment = ", ".join(c["label"] for c in arch["components"])
    return f'''# DRAFT ONLY — generated from CloudMorph provider-neutral architecture intent.\n# Never auto-applied. Review IAM, network, encryption, backup and provider-specific controls.\n# Architecture intent: {comment}\nterraform {{\n  required_version = ">= 1.6.0"\n}}\n\nvariable "environment" {{\n  type = string\n  validation {{\n    condition = contains(["dev", "test", "prod"], var.environment)\n    error_message = "environment must be dev, test, or prod"\n  }}\n}}\n\nlocals {{ application_id = "{app.application_id}"; strategy = "{strategy.value}" }}\n# No provider resources are emitted automatically.\noutput "cloudmorph_plan" {{ value = {{ application_id = local.application_id, strategy = local.strategy }} }}\n'''
