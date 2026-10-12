from __future__ import annotations
from .schemas import Portfolio


def assess_security(portfolio: Portfolio) -> list[dict]:
    out = []
    for app in portfolio.applications:
        controls = [
            {
                "control": "least_privilege",
                "status": "review",
                "evidence": "IAM design must be validated during target implementation",
            },
            {
                "control": "secret_handling",
                "status": "required",
                "evidence": "Use secret manager/environment injection; repository contains no runtime credentials",
            },
            {
                "control": "encryption",
                "status": "required",
                "evidence": f"data_sensitivity={app.data_sensitivity.value}",
            },
            {
                "control": "backup_recovery",
                "status": "required",
                "evidence": f"RTO={app.rto_hours}h RPO={app.rpo_hours}h",
            },
        ]
        if app.data_sensitivity.value in {"confidential", "restricted"}:
            controls.append(
                {
                    "control": "network_segmentation",
                    "status": "required",
                    "evidence": "sensitive data classification",
                }
            )
            controls.append(
                {
                    "control": "audit_logging",
                    "status": "required",
                    "evidence": "sensitive data classification",
                }
            )
        if app.identity_maturity is not None and app.identity_maturity < 5:
            controls.append(
                {
                    "control": "identity_modernization",
                    "status": "gap",
                    "evidence": f"identity_maturity={app.identity_maturity}",
                }
            )
        out.append(
            {
                "application_id": app.application_id,
                "controls": controls,
                "regulatory_tags": app.regulatory_tags,
                "disclaimer": "Relevant controls only; this is not a certification of PCI, GDPR, SOX, or any other regime.",
            }
        )
    return out
