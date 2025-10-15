"""FastAPI application exposing diagnostic information."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from diagnostic_tool import (
    analyze_system_health,
    collect_system_metrics,
    describe_process,
    list_top_processes,
    sample_cpu_usage,
    sample_disk_io,
)

app = FastAPI(title="Server Diagnostic Tool", version="0.1.0")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_file = static_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html missing")
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.get("/api/system")
def system_metrics(sample_duration: float = Query(1.0, ge=0.1, le=5.0)):
    metrics = collect_system_metrics(sample_duration=sample_duration)
    return metrics


@app.get("/api/processes")
def top_processes(limit: int = Query(10, ge=1, le=50), sort_by: str = Query("cpu")):
    try:
        processes = list_top_processes(limit=limit, sort_by=sort_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": processes}


@app.get("/api/processes/{pid}")
def process_detail(pid: int):
    info = describe_process(pid)
    if info is None:
        raise HTTPException(status_code=404, detail="process not found or access denied")
    return info


@app.get("/api/diagnostics/cpu")
def cpu_samples(duration: float = Query(10.0, ge=1.0, le=60.0), interval: float = Query(1.0, ge=0.5, le=10.0)):
    samples = sample_cpu_usage(duration=duration, interval=interval)
    return {"samples": samples}


@app.get("/api/diagnostics/disk")
def disk_samples(duration: float = Query(10.0, ge=1.0, le=60.0), interval: float = Query(1.0, ge=0.5, le=10.0)):
    samples = sample_disk_io(duration=duration, interval=interval)
    return {"samples": samples}


@app.get("/api/diagnostics/analysis")
def health_analysis(sample_duration: float = Query(1.0, ge=0.1, le=5.0)):
    metrics = collect_system_metrics(sample_duration=sample_duration)
    analysis = analyze_system_health(metrics)
    return {"metrics": metrics, "analysis": analysis}
