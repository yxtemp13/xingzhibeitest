from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class PrometheusSettings:
    base_url: Optional[str] = None
    mock_data_dir: Optional[Path] = None


@dataclass
class DiagnosticJobType:
    title: str
    script: Path
    mode: str


@dataclass
class DiagnosticsSettings:
    output_dir: Path
    job_types: Dict[str, DiagnosticJobType] = field(default_factory=dict)


@dataclass
class ProfileSettings:
    data_file: Path


@dataclass
class Host:
    name: str
    address: str
    labels: Dict[str, str]


@dataclass
class AppConfig:
    prometheus: PrometheusSettings
    hosts: List[Host]
    diagnostics: DiagnosticsSettings
    profiles: ProfileSettings


def _load_job_types(raw: Dict[str, Dict[str, str]], root: Path) -> Dict[str, DiagnosticJobType]:
    job_types: Dict[str, DiagnosticJobType] = {}
    for key, value in raw.items():
        job_types[key] = DiagnosticJobType(
            title=value["title"],
            script=(root / value["script"]).resolve(),
            mode=value.get("mode", "histogram"),
        )
    return job_types


def load_config(path: Path | str = "config.yaml") -> AppConfig:
    root = Path(path).resolve().parent
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    prometheus_raw = raw.get("prometheus", {})
    prometheus = PrometheusSettings(
        base_url=prometheus_raw.get("base_url"),
        mock_data_dir=(root / prometheus_raw["mock_data_dir"]).resolve()
        if prometheus_raw.get("mock_data_dir")
        else None,
    )

    hosts = [
        Host(name=h["name"], address=h["address"], labels=h.get("labels", {}))
        for h in raw.get("hosts", [])
    ]

    diagnostics_raw = raw.get("diagnostics", {})
    diagnostics = DiagnosticsSettings(
        output_dir=(root / diagnostics_raw.get("output_dir", "data/jobs")).resolve(),
        job_types=_load_job_types(diagnostics_raw.get("job_types", {}), root),
    )

    profiles_raw = raw.get("profiles", {})
    profiles = ProfileSettings(
        data_file=(root / profiles_raw.get("data_file", "data/mock/profiles.json")).resolve()
    )

    return AppConfig(
        prometheus=prometheus,
        hosts=hosts,
        diagnostics=diagnostics,
        profiles=profiles,
    )
