from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HostModel(BaseModel):
    name: str
    address: str
    labels: Dict[str, str]


class QueryRangeResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class JobRequest(BaseModel):
    job_type: str = Field(description="Type of diagnostic job to run")
    target: str = Field(description="Host or container identifier")
    duration: int = Field(ge=1, le=3600, description="Job duration in seconds")
    options: Dict[str, Any] = Field(default_factory=dict)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResult(BaseModel):
    job_id: str
    job_type: str
    target: str
    duration: int
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    mode: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProfileSummary(BaseModel):
    id: str
    title: str
    service: str
    created_at: datetime
    sample_rate_hz: float


class ProfileDetail(ProfileSummary):
    flamegraph_url: str
    metrics: Dict[str, Any]
    tags: Dict[str, str]


class JobListResponse(BaseModel):
    jobs: List[JobResult]


class ProfileListResponse(BaseModel):
    profiles: List[ProfileSummary]
