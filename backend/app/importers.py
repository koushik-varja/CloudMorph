from __future__ import annotations

import csv
import io
import json
from pathlib import PurePath
from typing import Any
import yaml
from pydantic import ValidationError
from .schemas import Application, Dependency, IntegrationType, Portfolio

ALLOWED_EXTENSIONS = {".json", ".csv", ".yaml", ".yml"}


class ImportErrorDetail(ValueError):
    pass


def safe_filename(filename: str) -> str:
    if "/" in filename or "\\" in filename:
        raise ImportErrorDetail("unsafe filename")
    name = PurePath(filename).name
    if name != filename or name in {"", ".", ".."}:
        raise ImportErrorDetail("unsafe filename")
    suffix = PurePath(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ImportErrorDetail(f"unsupported extension: {suffix}")
    return name


def _decode(data: bytes, max_bytes: int) -> str:
    if len(data) > max_bytes:
        raise ImportErrorDetail(f"upload exceeds {max_bytes} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportErrorDetail("file must be UTF-8 text") from exc


def parse_portfolio_bytes(filename: str, data: bytes, max_bytes: int) -> Portfolio:
    name = safe_filename(filename)
    text = _decode(data, max_bytes)
    suffix = PurePath(name).suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(text)
            return Portfolio.model_validate(payload)
        if suffix == ".csv":
            return _parse_csv(text, PurePath(name).stem)
        if suffix in {".yaml", ".yml"}:
            return _parse_yaml(text, PurePath(name).stem)
    except (json.JSONDecodeError, yaml.YAMLError, ValidationError, csv.Error) as exc:
        raise ImportErrorDetail(str(exc)) from exc
    raise ImportErrorDetail("unsupported file")


def _parse_csv(text: str, name: str) -> Portfolio:
    reader = csv.DictReader(io.StringIO(text))
    if (
        not reader.fieldnames
        or "application_id" not in reader.fieldnames
        or "name" not in reader.fieldnames
    ):
        raise ImportErrorDetail("CSV requires application_id and name columns")
    apps: list[Application] = []
    for row in reader:
        deps: list[Dependency] = []
        for target in (row.get("dependencies") or "").split(";"):
            target = target.strip()
            if target:
                deps.append(Dependency(target=target))
        payload: dict[str, Any] = {k: v for k, v in row.items() if v not in {None, ""}}
        payload["dependencies"] = deps
        for numeric in (
            "business_value",
            "change_frequency",
            "database_size_gb",
            "traffic_rps",
            "peak_traffic_rps",
            "availability_requirement",
            "rto_hours",
            "rpo_hours",
            "estimated_current_cost",
            "technical_debt_score",
            "team_skill_level",
            "test_coverage",
            "deployment_frequency",
            "incident_frequency",
            "scalability_requirement",
            "migration_effort",
            "migration_risk",
            "migration_cost",
        ):
            if numeric in payload:
                payload[numeric] = float(payload[numeric])
        if "integration_count" in payload:
            payload["integration_count"] = int(payload["integration_count"])
        if "regulatory_tags" in payload and isinstance(payload["regulatory_tags"], str):
            payload["regulatory_tags"] = [x for x in payload["regulatory_tags"].split(";") if x]
        apps.append(Application.model_validate(payload))
    return Portfolio(name=name, applications=apps)


def _parse_yaml(text: str, name: str) -> Portfolio:
    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ImportErrorDetail("YAML root must be a mapping")
    if "services" in payload:
        return parse_compose_payload(payload, name)
    if "kind" in payload or "apiVersion" in payload:
        return parse_kubernetes_payload(payload, name)
    return Portfolio.model_validate(payload)


def parse_compose_payload(payload: dict[str, Any], name: str = "compose-import") -> Portfolio:
    services = payload.get("services")
    if not isinstance(services, dict) or not services:
        raise ImportErrorDetail("Compose YAML requires services mapping")
    apps: list[Application] = []
    ids = set(services)
    for service_name, spec in services.items():
        spec = spec if isinstance(spec, dict) else {}
        raw_depends = spec.get("depends_on", [])
        if isinstance(raw_depends, dict):
            dep_names = list(raw_depends)
        elif isinstance(raw_depends, list):
            dep_names = [str(x) for x in raw_depends]
        else:
            dep_names = []
        deps = [
            Dependency(target=d, integration_type=IntegrationType.api)
            for d in dep_names
            if d in ids
        ]
        image = str(spec.get("image", "unknown"))
        ports = spec.get("ports", []) if isinstance(spec.get("ports", []), list) else []
        apps.append(
            Application(
                application_id=service_name,
                name=service_name,
                description=f"Imported from Docker Compose; image={image}; ports={len(ports)}",
                runtime="container",
                deployment_model="container",
                dependencies=deps,
                integration_count=len(deps),
            )
        )
    return Portfolio(name=name, applications=apps)


def parse_kubernetes_payload(payload: dict[str, Any], name: str = "kubernetes-import") -> Portfolio:
    items = payload.get("items") if payload.get("kind") == "List" else [payload]
    if not isinstance(items, list):
        raise ImportErrorDetail("invalid Kubernetes object list")
    apps: list[Application] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", ""))
        if kind not in {"Deployment", "StatefulSet", "DaemonSet"}:
            continue
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        app_id = str(metadata.get("name", "")).strip()
        if not app_id:
            continue
        spec = item.get("spec", {}) if isinstance(item.get("spec"), dict) else {}
        template = spec.get("template", {}) if isinstance(spec.get("template"), dict) else {}
        pod_spec = template.get("spec", {}) if isinstance(template.get("spec"), dict) else {}
        containers = (
            pod_spec.get("containers", [])
            if isinstance(pod_spec.get("containers", []), list)
            else []
        )
        images = [str(c.get("image", "unknown")) for c in containers if isinstance(c, dict)]
        apps.append(
            Application(
                application_id=app_id,
                name=app_id,
                description=f"Imported from Kubernetes {kind}; images={', '.join(images) or 'unknown'}",
                runtime="container",
                deployment_model="kubernetes",
            )
        )
    if not apps:
        raise ImportErrorDetail("no supported workload objects found")
    return Portfolio(name=name, applications=apps)
