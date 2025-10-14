from __future__ import annotations

import time
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_hosts():
    response = client.get("/api/hosts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "demo-host-1"


def test_query_range_mock():
    end = datetime.utcnow()
    start = end - timedelta(minutes=15)
    params = {
        "expr": 'node_cpu_seconds_total{mode="user"}',
        "start": start.isoformat(),
        "end": end.isoformat(),
        "step": 60,
    }
    response = client.get("/api/query_range", params=params)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["data"]["result"]) >= 1


def test_create_job_and_fetch_result():
    payload = {
        "job_type": "runqlen",
        "target": "demo-host-1",
        "duration": 10,
    }
    response = client.post("/api/diagnose/jobs", json=payload)
    assert response.status_code == 200
    job = response.json()
    job_id = job["job_id"]

    # Wait for job to complete
    for _ in range(10):
        job_response = client.get(f"/api/diagnose/jobs/{job_id}")
        assert job_response.status_code == 200
        job_payload = job_response.json()
        if job_payload["status"] == "completed":
            assert job_payload["data"]["type"] == "histogram"
            break
        time.sleep(0.2)
    else:
        raise AssertionError("Job did not complete in time")


def test_profiles_list_and_detail():
    list_response = client.get("/api/profiles")
    assert list_response.status_code == 200
    profiles = list_response.json()["profiles"]
    assert len(profiles) >= 1
    profile_id = profiles[0]["id"]

    detail_response = client.get(f"/api/profiles/{profile_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == profile_id
    assert "flamegraph_url" in detail
