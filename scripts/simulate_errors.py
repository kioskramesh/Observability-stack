#!/usr/bin/env python3
"""Inject failures / latency, then generate traffic so dashboards light up.

Usage:
  python scripts/simulate_errors.py
  python scripts/simulate_errors.py --fail-rate 0.3 --latency-ms 800 --duration 90
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


async def set_chaos(base_url: str, fail_rate: float, latency_ms: int) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        r = await client.post(
            "/chaos",
            json={"fail_rate": fail_rate, "latency_ms": latency_ms},
        )
        r.raise_for_status()
        print(f"Chaos set: {r.json()}")


async def reset_chaos(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        r = await client.post("/chaos/reset")
        r.raise_for_status()
        print(f"Chaos reset: {r.json()}")


async def boom(base_url: str, times: int) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        for i in range(times):
            try:
                await client.get("/chaos/boom")
            except Exception:
                pass
            print(f"  boom #{i + 1}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--fail-rate", type=float, default=0.25)
    p.add_argument("--latency-ms", type=int, default=500)
    p.add_argument("--duration", type=int, default=60)
    p.add_argument("--rps", type=float, default=15.0)
    p.add_argument("--booms", type=int, default=5, help="Intentional 500s via /chaos/boom")
    p.add_argument("--no-reset", action="store_true", help="Leave chaos on after run")
    args = p.parse_args()

    async def scenario() -> None:
        print("=== 1) Intentional booms (unhandled 500s) ===")
        await boom(args.base_url, args.booms)

        print("=== 2) Enable chaos (partial failures + latency) ===")
        await set_chaos(args.base_url, args.fail_rate, args.latency_ms)

        print("=== 3) Run load while chaos is active ===")
        load_script = ROOT / "scripts" / "load_test.py"
        subprocess.run(
            [
                sys.executable,
                str(load_script),
                "--base-url",
                args.base_url,
                "--rps",
                str(args.rps),
                "--duration",
                str(args.duration),
            ],
            check=False,
        )

        # Business-rule 400s
        print("=== 4) Trigger business 400s (blocked item) ===")
        async with httpx.AsyncClient(base_url=args.base_url, timeout=15.0) as client:
            for _ in range(10):
                await client.post(
                    "/orders",
                    json={
                        "customer_id": "cust-bad",
                        "item": "forbidden",
                        "quantity": 1,
                        "unit_price": 10.0,
                        "payment_method": "card",
                    },
                )
            print("  sent 10 blocked-item orders")

        if not args.no_reset:
            print("=== 5) Reset chaos ===")
            await reset_chaos(args.base_url)
        else:
            print("Chaos left enabled (--no-reset)")

        print("\nOpen Grafana http://localhost:3000 (admin/admin)")
        print("Check: Order Service Overview dashboard, Explore → Loki & Tempo")

    asyncio.run(scenario())


if __name__ == "__main__":
    main()