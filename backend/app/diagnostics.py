from __future__ import annotations

import json
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from .config import DiagnosticsSettings, DiagnosticJobType
from .models import JobRequest, JobResult, JobStatus


class JobManager:
    def __init__(self, settings: DiagnosticsSettings) -> None:
        self.settings = settings
        self._jobs: Dict[str, JobResult] = {}
        self._lock = threading.Lock()
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

    def create_job(self, request: JobRequest) -> JobResult:
        job_type = self._get_job_type(request.job_type)
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()
        job = JobResult(
            job_id=job_id,
            job_type=request.job_type,
            target=request.target,
            duration=request.duration,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            mode=job_type.mode,
        )
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._run_job, args=(job_id, request, job_type), daemon=True)
        thread.start()
        return job

    def list_jobs(self) -> Dict[str, JobResult]:
        with self._lock:
            return dict(self._jobs)

    def get_job(self, job_id: str) -> JobResult | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _update_job(self, job_id: str, **kwargs) -> None:
        with self._lock:
            job = self._jobs[job_id]
            updated = job.copy(update={**kwargs, "updated_at": datetime.utcnow()})
            self._jobs[job_id] = updated

    def _get_job_type(self, job_type: str) -> DiagnosticJobType:
        if job_type not in self.settings.job_types:
            raise ValueError(f"Unknown job type: {job_type}")
        return self.settings.job_types[job_type]

    def _run_job(self, job_id: str, request: JobRequest, job_type: DiagnosticJobType) -> None:
        self._update_job(job_id, status=JobStatus.RUNNING)
        output_path = Path(self.settings.output_dir) / f"{job_id}.json"
        command_job_type = request.job_type
        command = [
            str(job_type.script),
            "--job-type",
            command_job_type,
            "--output",
            str(output_path),
            "--target",
            request.target,
            "--duration",
            str(request.duration),
        ]
        for key, value in sorted(request.options.items()):
            command.extend([f"--{key.replace('_', '-')}", str(value)])
        try:
            subprocess.run(command, check=True)
            data = json.loads(output_path.read_text())
            self._update_job(job_id, status=JobStatus.COMPLETED, data=data.get("data"))
        except subprocess.CalledProcessError as exc:
            self._update_job(job_id, status=JobStatus.FAILED, error=str(exc))
        except json.JSONDecodeError as exc:
            self._update_job(job_id, status=JobStatus.FAILED, error=f"Invalid job output: {exc}")
        finally:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
