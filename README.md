# Observability Stack Lab

End-to-end local lab for **Prometheus**, **Grafana**, **Loki**, **Tempo/OpenTelemetry**, and optional **Datadog** — built so you can demo and explain monitoring confidently in interviews.

> **Start here:** read and follow [`GUIDE.md`](./GUIDE.md) end-to-end.  
> Do **not** commit until you have reviewed the files yourself.

## Quick start

```powershell
cd Observability-stack
copy .env.example .env
docker compose up --build -d
```

| Component | URL |
|-----------|-----|
| Order API + Swagger | http://localhost:8000/docs |
| Grafana (`admin` / `admin`) | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

Generate traffic and failures:

```powershell
pip install -r scripts/requirements.txt
python scripts/simulate_errors.py
```

## What’s included

- **App:** FastAPI Order Service with JSON logs, Prometheus metrics, OTel traces, and `/chaos` failure injection
- **OSS stack:** Prometheus + alert rules, Grafana (pre-provisioned dashboard), Loki + Promtail, Tempo, OTel Collector
- **Optional:** Datadog Agent via `docker compose --profile datadog up`
- **Scripts:** load test, error simulation, named chaos scenarios for interview practice

## Interview one-liner

You instrumented a service for the three pillars, alerted on RED/business symptoms, and practiced correlating metrics → logs → traces during injected incidents — including how that maps to a commercial tool like Datadog.
