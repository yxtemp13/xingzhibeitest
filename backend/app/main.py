from __future__ import annotations

from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .diagnostics import JobManager
from .models import (
    HostModel,
    JobListResponse,
    JobRequest,
    JobResult,
    ProfileDetail,
    ProfileListResponse,
    QueryRangeResponse,
)
from .profiles import ProfileStore
from .prometheus import PrometheusClient

CONFIG = load_config(Path(__file__).resolve().parents[2] / "config.yaml")
PROM_CLIENT = PrometheusClient(CONFIG.prometheus)
JOB_MANAGER = JobManager(CONFIG.diagnostics)
PROFILE_STORE = ProfileStore(CONFIG.profiles)

app = FastAPI(title="Web Performance Diagnostics")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/", include_in_schema=False)
def redirect_root() -> RedirectResponse:
    return RedirectResponse(url="/frontend/index.html")


@app.get("/api/hosts", response_model=list[HostModel])
def get_hosts() -> list[HostModel]:
    return [HostModel(name=h.name, address=h.address, labels=h.labels) for h in CONFIG.hosts]


@app.get("/api/query_range", response_model=QueryRangeResponse)
async def query_range(
    expr: str = Query(..., description="PromQL expression"),
    start: datetime = Query(..., description="Range start timestamp"),
    end: datetime = Query(..., description="Range end timestamp"),
    step: float = Query(15.0, description="Step size in seconds"),
) -> QueryRangeResponse:
    data = await PROM_CLIENT.query_range(expr=expr, start=start, end=end, step=step)
    return QueryRangeResponse(status=data.get("status", "success"), data=data.get("data", {}))


@app.post("/api/diagnose/jobs", response_model=JobResult)
def create_job(request: JobRequest) -> JobResult:
    try:
        return JOB_MANAGER.create_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/diagnose/jobs", response_model=JobListResponse)
def list_jobs() -> JobListResponse:
    jobs = JOB_MANAGER.list_jobs()
    return JobListResponse(jobs=list(jobs.values()))


@app.get("/api/diagnose/jobs/{job_id}", response_model=JobResult)
def get_job(job_id: str) -> JobResult:
    job = JOB_MANAGER.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/profiles", response_model=ProfileListResponse)
def list_profiles() -> ProfileListResponse:
    return ProfileListResponse(profiles=PROFILE_STORE.list_profiles())


@app.get("/api/profiles/{profile_id}", response_model=ProfileDetail)
def get_profile(profile_id: str) -> ProfileDetail:
    try:
        return PROFILE_STORE.get_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
