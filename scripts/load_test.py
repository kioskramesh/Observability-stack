#!/usr/bin/env python3
"""Generate steady traffic against the order service.

Usage:
  python scripts/load_test.py
  python scripts/load_test.py --rps 20 --duration 120 --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time

import httpx

ITEMS = [
    "wireless-headphones",
    "usb-c-hub",
    "mechanical-keyboard",
    "laptop-stand",
    "webcam",
]
PAYMENTS = ["card", "upi", "wallet"]


async def worker(client: httpx.AsyncClient, stop_at: float, stats: dict) -> None:
    while time.time() < stop_at:
        payload = {
            "customer_id": f"cust-{random.randint(1, 50)}",
            "item": random.choice(ITEMS),
            "quantity": random.randint(1, 3),
            "unit_price": round(random.uniform(9.99, 199.99), 2),
            "payment_method": random.choice(PAYMENTS),
        }
        try:
            r = await client.post("/orders", json=payload, timeout=30.0)
            stats["total"] += 1
            if r.status_code >= 500:
                stats["5xx"] += 1
            elif r.status_code >= 400:
                stats["4xx"] += 1
            else:
                stats["2xx"] += 1
                # Occasionally fetch the order back
                if random.random() < 0.3:
                    order_id = r.json()["id"]
                    await client.get(f"/orders/{order_id}", timeout=10.0)
                    stats["gets"] += 1
        except Exception:
            stats["errors"] += 1
        await asyncio.sleep(0)  # yield


async def run(base_url: str, rps: float, duration: int, concurrency: int) -> None:
    stats = {"total": 0, "2xx": 0, "4xx": 0, "5xx": 0, "gets": 0, "errors": 0}
    stop_at = time.time() + duration
    interval = 1.0 / rps if rps > 0 else 0.05

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Health check first
        health = await client.get("/health")
        health.raise_for_status()
        print(f"Target healthy: {base_url}")

        async def paced_worker() -> None:
            while time.time() < stop_at:
                await worker(client, time.time() + 0.001, stats)
                await asyncio.sleep(interval * concurrency)

        tasks = [asyncio.create_task(paced_worker()) for _ in range(concurrency)]
        await asyncio.gather(*tasks)

    print("--- load test complete ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")


def main() -> None:
    p = argparse.ArgumentParser(description="Load test for order-service")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--rps", type=float, default=10.0, help="Approximate requests/sec")
    p.add_argument("--duration", type=int, default=60, help="Seconds")
    p.add_argument("--concurrency", type=int, default=5)
    args = p.parse_args()
    asyncio.run(run(args.base_url, args.rps, args.duration, args.concurrency))


if __name__ == "__main__":
    main()