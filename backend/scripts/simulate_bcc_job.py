#!/usr/bin/env python3
"""Simulate output of BCC/eBPF diagnostics.

This script generates deterministic but realistic-looking data for different
job types so the web application can demonstrate behaviour without requiring
kernel level tooling in the execution environment.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

RANDOM = random.Random(42)


def build_histogram(buckets: int = 10, base: float = 1.5) -> dict:
    values = []
    current = 0.1
    for _ in range(buckets):
        current *= base + RANDOM.random() * 0.5
        values.append(round(current, 3))
    histogram = []
    for idx, upper in enumerate(values):
        count = int(RANDOM.random() * 100)
        histogram.append({"le": upper, "count": count})
    return {"type": "histogram", "buckets": histogram}


def build_offcpu_stacks(max_items: int = 5) -> dict:
    stacks = []
    for i in range(max_items):
        duration = round(RANDOM.random() * 250, 2)
        stacks.append(
            {
                "rank": i + 1,
                "total_ms": duration,
                "stack": [
                    "libpthread.so.0 + 0x1234",
                    "libc.so.6 + 0x4321",
                    f"workload::do_something_slow::{i}",
                ],
            }
        )
    return {"type": "stacks", "frames": stacks}


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate BCC job output")
    parser.add_argument("--job-type", required=True, choices=[
        "runqlen",
        "runqlat",
        "offcputime",
        "biolatency",
    ])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", default="demo-host-1")
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()

    # Simulate processing time proportional to duration but capped for tests.
    sleep_time = min(args.duration / 100.0, 0.5)
    time.sleep(sleep_time)

    if args.job_type in {"runqlen", "runqlat", "biolatency"}:
        result = {
            "job_type": args.job_type,
            "target": args.target,
            "duration": args.duration,
            "generated_at": time.time(),
            "data": build_histogram(),
        }
    else:
        result = {
            "job_type": args.job_type,
            "target": args.target,
            "duration": args.duration,
            "generated_at": time.time(),
            "data": build_offcpu_stacks(),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
