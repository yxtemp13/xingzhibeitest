"""Generate simple health assessments from collected metrics."""

from __future__ import annotations

from typing import Dict, List


def _percent(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return (value / total) * 100.0


def analyze_system_health(metrics: Dict[str, object]) -> Dict[str, object]:
    """Provide a lightweight health assessment based on collected metrics."""

    assessments: List[str] = []
    severity = "ok"

    cpu_percent = float(metrics.get("cpu_percent", 0.0))
    if cpu_percent > 90:
        assessments.append("CPU 利用率持续超过 90%，建议排查高负载进程或调整容量。")
        severity = "critical"
    elif cpu_percent > 75:
        assessments.append("CPU 利用率偏高，可关注核心业务进程并评估是否需要扩容。")
        severity = "warning"

    memory = metrics.get("memory") or {}
    memory_percent = float(memory.get("percent", 0.0))
    if memory_percent > 90:
        assessments.append("内存使用率超过 90%，请检查是否存在内存泄漏或优化缓存策略。")
        severity = "critical"
    elif memory_percent > 80 and severity != "critical":
        assessments.append("内存使用率较高，建议回收不必要的进程或增加内存。")
        severity = "warning"

    swap_percent = float((metrics.get("swap") or {}).get("percent", 0.0))
    if swap_percent > 10:
        assessments.append("Swap 使用率超过 10%，可能存在内存压力导致频繁换页。")
        severity = "warning" if severity != "critical" else severity

    load = metrics.get("load") or {}
    cpu_count = metrics.get("cpu_count") or 1
    load1 = float(load.get("load1", 0.0))
    if load1 > cpu_count * 1.5:
        assessments.append("1 分钟负载超过核心数 1.5 倍，疑似存在 CPU 争抢或阻塞。")
        severity = "critical"

    disks = metrics.get("disks") or {}
    saturated_disks: List[str] = []
    for mountpoint, data in disks.items():
        if float(data.get("percent", 0.0)) > 85:
            saturated_disks.append(mountpoint)
    if saturated_disks:
        text = "、".join(saturated_disks)
        assessments.append(f"磁盘分区 {text} 剩余空间不足 15%，请及时扩容或清理无用数据。")
        severity = "warning" if severity != "critical" else severity

    network_io = metrics.get("network_io") or {}
    drop_interfaces: List[str] = []
    for name, counters in network_io.items():
        drops = float(counters.get("dropin", 0.0)) + float(counters.get("dropout", 0.0))
        errors = float(counters.get("errin", 0.0)) + float(counters.get("errout", 0.0))
        if drops > 0 or errors > 0:
            drop_interfaces.append(name)
    if drop_interfaces:
        assessments.append(
            "检测到网卡出现丢包或错误：" + ", ".join(drop_interfaces) + "，建议检查链路和网卡状态。"
        )
        severity = "warning" if severity != "critical" else severity

    if not assessments:
        assessments.append("系统运行平稳，未发现明显风险。")

    return {
        "severity": severity,
        "assessments": assessments,
    }
