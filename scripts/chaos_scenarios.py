#!/usr/bin/env python3
"""Guided chaos scenarios that map to interview talking points.

Scenarios:
  latency   — slow downstream / network delay
  errors    — elevated 5xx rate (SLO burn)
  spike     — sudden traffic spike
  mixed     — latency + errors together (realistic incident)

Usage:
  python scripts/chaos_scenarios.py latency
  python scripts/chaos_scenarios.py mixed --duration 90
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


SCENARIOS = {
    "latency": {
        "fail_rate": 0.0,
        "latency_ms": 1200,
        "rps": 8,
        "talking_point": (
            "Latency without errors — classic 'slow but alive'. "
            "Talk about p99, saturation, and whether queues are backing up."
        ),
    },
    "errors": {
        "fail_rate": 0.4,
        "latency_ms": 0,
        "rps": 12,
        "talking_point": (
            "Error budget burn — RED metrics show rising 5xx. "
            "Correlate with Loki error logs and Tempo failed spans."
        ),
    },
    "spike": {
        "fail_rate": 0.05,
        "latency_ms": 100,
        "rps": 40,
        "talking_point": (
            "Traffic spike — rate climbs, latency may climb after. "
            "Discuss autoscaling signals and load shedding."
        ),
    },
    "mixed": {
        "fail_rate": 0.2,
        "latency_ms": 700,
        "rps": 20,
        "talking_point": (
            "Realistic incident — latency + errors. "
            "Walk the three pillars: Metrics → Logs → Traces."
        ),
    },
}


async def set_chaos(base_url: str, fail_rate: float, latency_ms: int) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        r = await client.post(
            "/chaos", json={"fail_rate": fail_rate, "latency_ms": latency_ms}
        )
        r.raise_for_status()
        print("Chaos:", r.json())


async def reset(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        await client.post("/chaos/reset")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("scenario", choices=sorted(SCENARIOS.keys()))
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--duration", type=int, default=60)
    args = p.parse_args()
    cfg = SCENARIOS[args.scenario]

    print(f"\nScenario: {args.scenario}")
    print(f"Interview angle: {cfg['talking_point']}\n")

    async def run() -> None:
        await set_chaos(args.base_url, cfg["fail_rate"], cfg["latency_ms"])
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "load_test.py"),
                "--base-url",
                args.base_url,
                "--rps",
                str(cfg["rps"]),
                "--duration",
                str(args.duration),
            ],
            check=False,
        )
        await reset(args.base_url)
        print("\nDone. Inspect Grafana + Prometheus alerts + Tempo traces.")

    asyncio.run(run())


if __name__ == "__main__":
    main()