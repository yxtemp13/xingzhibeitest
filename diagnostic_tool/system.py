"""System level metric collection helpers."""

from __future__ import annotations

import os
import platform
import time
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

import psutil


def _collect_load_average() -> Dict[str, float]:
    if hasattr(os, "getloadavg"):
        load1, load5, load15 = os.getloadavg()
        return {"load1": load1, "load5": load5, "load15": load15}
    return {"load1": 0.0, "load5": 0.0, "load15": 0.0}


def collect_system_metrics(sample_duration: float = 1.0) -> Dict[str, object]:
    """Return a snapshot of system level metrics.

    Args:
        sample_duration: Seconds spent sampling cpu utilisation. Larger values
            produce smoother numbers at the cost of slower responses.
    """

    cpu_percent = psutil.cpu_percent(interval=sample_duration)
    per_cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    boot_time = datetime.fromtimestamp(psutil.boot_time()).isoformat()

    disks = {}
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except PermissionError:
            continue
        disks[partition.mountpoint] = {
            "filesystem": partition.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        }

    disk_io = {}
    for name, counters in psutil.disk_io_counters(perdisk=True).items():
        disk_io[name] = {
            "read_bytes": counters.read_bytes,
            "write_bytes": counters.write_bytes,
            "read_time": counters.read_time,
            "write_time": counters.write_time,
            "busy_time": getattr(counters, "busy_time", 0),
        }

    net_io = {}
    for name, counters in psutil.net_io_counters(pernic=True).items():
        net_io[name] = {
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
            "errin": counters.errin,
            "errout": counters.errout,
            "dropin": counters.dropin,
            "dropout": counters.dropout,
        }

    sensors_temperatures = {}
    if hasattr(psutil, "sensors_temperatures"):
        try:
            for name, entries in psutil.sensors_temperatures().items():
                sensors_temperatures[name] = [
                    {
                        "label": getattr(entry, "label", ""),
                        "current": entry.current,
                        "high": getattr(entry, "high", None),
                        "critical": getattr(entry, "critical", None),
                    }
                    for entry in entries
                ]
        except Exception:
            sensors_temperatures = {}

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hostname": platform.node(),
        "platform": platform.platform(),
        "cpu_percent": cpu_percent,
        "per_cpu_percent": per_cpu_percent,
        "cpu_count": psutil.cpu_count(logical=True),
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "free": memory.free,
            "percent": memory.percent,
            "cached": getattr(memory, "cached", None),
            "buffers": getattr(memory, "buffers", None),
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": swap.percent,
            "sin": swap.sin,
            "sout": swap.sout,
        },
        "boot_time": boot_time,
        "load": _collect_load_average(),
        "disks": disks,
        "disk_io": disk_io,
        "network_io": net_io,
        "sensors": sensors_temperatures,
    }


def sample_cpu_usage(duration: float = 10.0, interval: float = 1.0) -> List[Dict[str, object]]:
    """Return CPU usage samples over ``duration`` seconds."""

    samples: List[Dict[str, object]] = []
    intervals = max(1, int(duration / interval))
    for _ in range(intervals):
        percent_total = psutil.cpu_percent(interval=interval)
        percent_per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        samples.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "total": percent_total,
                "per_cpu": percent_per_cpu,
            }
        )
    return samples


def sample_disk_io(duration: float = 10.0, interval: float = 1.0) -> List[Dict[str, object]]:
    """Collect disk IO deltas across the provided duration."""

    samples: List[Dict[str, object]] = []
    intervals = max(1, int(duration / interval))
    previous: Dict[str, Tuple[int, int]] | None = None
    for _ in range(intervals):
        current = {
            name: (counters.read_bytes, counters.write_bytes)
            for name, counters in psutil.disk_io_counters(perdisk=True).items()
        }
        if previous is not None:
            sample = {
                name: {
                    "read_bytes": max(0, current[name][0] - previous.get(name, (0, 0))[0]),
                    "write_bytes": max(0, current[name][1] - previous.get(name, (0, 0))[1]),
                }
                for name in current
            }
        else:
            sample = {
                name: {"read_bytes": 0, "write_bytes": 0}
                for name in current
            }
        samples.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "devices": sample,
            }
        )
        previous = current
        time.sleep(interval)
    return samples
