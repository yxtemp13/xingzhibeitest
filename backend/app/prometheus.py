from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

from .config import PrometheusSettings


class PrometheusClient:
    def __init__(self, settings: PrometheusSettings) -> None:
        self.settings = settings

    async def query_range(self, expr: str, start: datetime, end: datetime, step: float) -> Dict[str, Any]:
        if self.settings.mock_data_dir:
            data = self._load_mock(expr)
            if data:
                return data

        if not self.settings.base_url:
            raise RuntimeError("Prometheus base URL is not configured")

        params = {
            "query": expr,
            "start": start.replace(tzinfo=timezone.utc).timestamp(),
            "end": end.replace(tzinfo=timezone.utc).timestamp(),
            "step": step,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.settings.base_url}/api/v1/query_range", params=params)
            response.raise_for_status()
            return response.json()

    def _load_mock(self, expr: str) -> Dict[str, Any] | None:
        directory = self.settings.mock_data_dir
        if not directory:
            return None
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", expr).strip("_")
        if not safe_name:
            safe_name = "default"
        path = Path(directory) / f"{safe_name}.json"
        if not path.exists():
            # fallback to generic file if available
            path = Path(directory) / "default_query_range.json"
            if not path.exists():
                return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
