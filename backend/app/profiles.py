from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .config import ProfileSettings
from .models import ProfileDetail, ProfileSummary


class ProfileStore:
    def __init__(self, settings: ProfileSettings) -> None:
        self.settings = settings
        self._profiles = self._load_profiles()

    def list_profiles(self) -> List[ProfileSummary]:
        return [
            ProfileSummary(
                id=item["id"],
                title=item["title"],
                service=item["service"],
                created_at=self._parse_datetime(item["created_at"]),
                sample_rate_hz=item["sample_rate_hz"],
            )
            for item in self._profiles.values()
        ]

    def get_profile(self, profile_id: str) -> ProfileDetail:
        if profile_id not in self._profiles:
            raise KeyError(profile_id)
        item = self._profiles[profile_id]
        return ProfileDetail(
            id=item["id"],
            title=item["title"],
            service=item["service"],
            created_at=self._parse_datetime(item["created_at"]),
            sample_rate_hz=item["sample_rate_hz"],
            flamegraph_url=item["flamegraph_url"],
            metrics=item["metrics"],
            tags=item.get("tags", {}),
        )

    def _load_profiles(self) -> Dict[str, Dict]:
        path = Path(self.settings.data_file)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {item["id"]: item for item in raw}

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)
