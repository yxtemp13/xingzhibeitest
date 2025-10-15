"""Process level helpers."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import psutil


def _serialize_cmdline(cmdline: Iterable[str]) -> str:
    return " ".join(part for part in cmdline if part)


def _with_cpu_percent(proc: psutil.Process, interval: float) -> float:
    try:
        return proc.cpu_percent(interval=interval)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0


def list_top_processes(limit: int = 10, sort_by: str = "cpu") -> List[Dict[str, object]]:
    """Return the top ``limit`` processes sorted by ``sort_by``."""

    key = sort_by.lower()
    valid_keys = {"cpu", "memory"}
    if key not in valid_keys:
        raise ValueError(f"Unsupported sort key '{sort_by}', expected one of {sorted(valid_keys)}")

    processes: List[psutil.Process] = []
    for proc in psutil.process_iter(
        [
            "pid",
            "name",
            "username",
            "cmdline",
            "cpu_percent",
            "memory_percent",
            "num_threads",
            "create_time",
        ]
    ):
        try:
            proc.cpu_percent(interval=None)
            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.2)

    process_info: List[Dict[str, object]] = []
    for proc in processes:
        try:
            cpu_percent = proc.cpu_percent(interval=None)
            memory_percent = proc.memory_percent()
            info = {
                "pid": proc.pid,
                "name": proc.info.get("name"),
                "username": proc.info.get("username"),
                "cmdline": _serialize_cmdline(proc.info.get("cmdline") or []),
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "num_threads": proc.info.get("num_threads"),
                "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
            }
            process_info.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    process_info.sort(key=lambda item: item["cpu_percent" if key == "cpu" else "memory_percent"], reverse=True)
    return process_info[:limit]


def describe_process(pid: int) -> Optional[Dict[str, object]]:
    """Return detailed information for a specific process."""

    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    with proc.oneshot():
        cpu_times = proc.cpu_times()
        memory_info = proc.memory_full_info()
        io_counters = proc.io_counters() if proc.is_running() and proc.io_counters() else None
        connections = []
        try:
            for conn in proc.connections(kind="inet"):
                connections.append(
                    {
                        "fd": conn.fd,
                        "family": str(conn.family),
                        "type": str(conn.type),
                        "local_address": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                        "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                        "status": conn.status,
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            connections = []

    return {
        "pid": proc.pid,
        "name": proc.name(),
        "username": proc.username(),
        "cmdline": _serialize_cmdline(proc.cmdline()),
        "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
        "cpu_times": {
            "user": cpu_times.user,
            "system": cpu_times.system,
            "children_user": getattr(cpu_times, "children_user", 0.0),
            "children_system": getattr(cpu_times, "children_system", 0.0),
        },
        "memory": {
            "rss": memory_info.rss,
            "vms": memory_info.vms,
            "pfaults": getattr(memory_info, "pfaults", None),
            "pageins": getattr(memory_info, "pageins", None),
            "uss": getattr(memory_info, "uss", None),
            "pss": getattr(memory_info, "pss", None),
        },
        "threads": [
            {
                "id": thread.id,
                "user_time": thread.user_time,
                "system_time": thread.system_time,
            }
            for thread in proc.threads()
        ],
        "open_files": [
            {
                "path": f.path,
                "fd": f.fd,
            }
            for f in proc.open_files()
        ],
        "connections": connections,
        "io_counters": {
            "read_bytes": io_counters.read_bytes,
            "write_bytes": io_counters.write_bytes,
            "read_count": io_counters.read_count,
            "write_count": io_counters.write_count,
        }
        if io_counters
        else None,
    }
