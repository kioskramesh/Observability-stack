# Observability Lab — End-to-End Implementation Guide

This document is your single source of truth. Follow it top-to-bottom once, then re-run the chaos scenarios until you can explain every box without looking.

---

## Table of contents

1. [What you are building](#1-what-you-are-building)
2. [Concepts you must own in interviews](#2-concepts-you-must-own-in-interviews)
3. [Prerequisites](#3-prerequisites)
4. [Project layout](#4-project-layout)
5. [Bring the stack up](#5-bring-the-stack-up)
6. [Verify each pillar](#6-verify-each-pillar)
7. [How the app is instrumented](#7-how-the-app-is-instrumented)
8. [Prometheus deep dive](#8-prometheus-deep-dive)
9. [Grafana deep dive](#9-grafana-deep-dive)
10. [Loki + Promtail deep dive](#10-loki--promtail-deep-dive)
11. [Traces (OTel → Tempo)](#11-traces-otel--tempo)
12. [Datadog (optional commercial path)](#12-datadog-optional-commercial-path)
13. [Simulate load and failures](#13-simulate-load-and-failures)
14. [Incident walkthrough (practice script)](#14-incident-walkthrough-practice-script)
15. [Interview Q&A cheat sheet](#15-interview-qa-cheat-sheet)
16. [Troubleshooting](#16-troubleshooting)
17. [What to say you built](#17-what-to-say-you-built)

---

## 1. What you are building

A tiny **Order Service** (FastAPI) plus a full local observability stack:

| Pillar | Tool | Role |
|--------|------|------|
| Metrics | Prometheus | Scrapes `/metrics`, stores time series, evaluates alerts |
| Visualization / alerts UI | Grafana | Dashboards + Explore across metrics/logs/traces |
| Logs | Loki + Promtail | Aggregates container JSON logs; LogQL queries |
| Traces | OpenTelemetry Collector + Tempo | App emits OTLP spans → collector → Tempo |
| Commercial APM (optional) | Datadog Agent | Same signals into a SaaS product |

```
                 ┌──────────────┐
  HTTP clients → │ order-service│──/metrics───────► Prometheus ──► Grafana
                 │  (FastAPI)   │──stdout JSON───► Promtail ──► Loki ──► Grafana
                 │              │──OTLP traces───► OTel Collector ──► Tempo ──► Grafana
                 └──────────────┘                      │
                                                       └──(optional)► Datadog
```

You will learn to **correlate** the three pillars: spike in metrics → matching error logs → slow/failed trace spans.

---

## 2. Concepts you must own in interviews

### Three pillars

- **Metrics** — numeric time series (cheap, aggregated, great for SLOs/alerts).
- **Logs** — event records (high cardinality detail, expensive at scale).
- **Traces** — request journeys across services (latency breakdown, dependency maps).

### RED vs USE

- **RED** (for request-driven services): **R**ate, **E**rrors, **D**uration.
- **USE** (for resources): **U**tilization, **S**aturation, **E**rrors (CPU, disk, queues).

This lab’s Grafana dashboard is built around RED + business metrics (`orders_created_total`).

### Cardinality

Labels explode series count. Prefer `status="5xx"` grouping over raw user IDs on metrics. Put high-cardinality IDs in **logs/traces**, not Prometheus labels.

### Pull vs push

- Prometheus **pulls** (scrapes) metrics — service discovery + `/metrics`.
- Many SaaS agents **push** (DogStatsD, OTLP export).
- Know both; this lab uses pull for Prometheus and push (OTLP) for traces.

### SLI / SLO / SLA / error budget

- **SLI**: measurement (e.g. success rate).
- **SLO**: target (e.g. 99.9% success over 30d).
- **SLA**: contractual consequence.
- **Error budget**: `1 - SLO`; when burned fast → freeze features / focus reliability.

### Instrumentation vs agents

- **Library instrumentation** (in-process): `prometheus-client`, OTel SDK, `ddtrace`.
- **Agents/sidecars**: Promtail, Datadog Agent, OTel Collector — collect, batch, route, enrich.

---

## 3. Prerequisites

- Docker Desktop (or Docker Engine) with Compose v2+
- ~4 GB RAM free for the stack
- Python 3.10+ on the host **only if** you want to run `scripts/` locally (optional; you can also `curl`)
- (Optional) Free Datadog trial API key

Check:

```powershell
docker version
docker compose version
```

---

## 4. Project layout

```
Observability-stack/
├── GUIDE.md                 ← you are here
├── README.md
├── docker-compose.yml
├── .env.example
├── app/                     ← instrumented Order API
│   ├── main.py
│   ├── metrics.py
│   ├── tracing.py
│   ├── logging_setup.py
│   ├── routes/              ← orders, health, chaos
│   ├── Dockerfile
│   └── requirements.txt
├── observability/
│   ├── prometheus/          ← scrape config + alert rules
│   ├── grafana/             ← datasources + dashboard provisioning
│   ├── loki/                ← Loki config
│   ├── promtail/            ← scrapes Docker logs
│   ├── tempo/               ← trace storage
│   └── otel/                ← collector pipelines
└── scripts/
    ├── load_test.py
    ├── simulate_errors.py
    └── chaos_scenarios.py
```

---

## 5. Bring the stack up

From the `Observability-stack` folder:

```powershell
cd c:\Users\User\Desktop\Harshitha\Observability-stack
copy .env.example .env
docker compose up --build -d
```

Wait ~30–60s, then check:

```powershell
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

### URLs

| UI / API | URL | Login |
|----------|-----|-------|
| Order API docs | http://localhost:8000/docs | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | `admin` / `admin` |
| Loki | http://localhost:3100/ready | — |
| Tempo | http://localhost:3200/ready | — |

Stop later with:

```powershell
docker compose down
```

---

## 6. Verify each pillar

### Metrics (Prometheus)

1. Open http://localhost:9090/targets — `order-service` should be **UP**.
2. Query:

```promql
up{job="order-service"}
http_requests_total
orders_created_total
```

3. Create one order:

```powershell
curl -X POST http://localhost:8000/orders `
  -H "Content-Type: application/json" `
  -d "{\"customer_id\":\"cust-1\",\"item\":\"webcam\",\"quantity\":1,\"unit_price\":49.99,\"payment_method\":\"card\"}"
```

4. Re-query `orders_created_total` — it should increment.

### Logs (Loki via Grafana)

1. Grafana → **Explore** → datasource **Loki**.
2. Query:

```logql
{service="order-service"}
```

or:

```logql
{container="order-service"} |= "order_created"
```

### Traces (Tempo via Grafana)

1. Generate traffic (see §13).
2. Grafana → **Explore** → **Tempo** → Search by service `order-service`.
3. Open a span for `POST /orders` — you should see nested `create_order` spans.

### Dashboard

Grafana → Dashboards → **Observability Lab** → **Order Service Overview**.

---

## 7. How the app is instrumented

Read these files and be ready to walk through them:

| File | What it does |
|------|----------------|
| `app/logging_setup.py` | JSON logs to stdout with `service` / `env` fields |
| `app/metrics.py` | Custom business metrics (Counter / Histogram / Gauge) |
| `app/tracing.py` | OTel TracerProvider + OTLP exporter + FastAPI auto-instrumentation |
| `app/main.py` | Wires logging, tracing, Prometheus instrumentator, routers |
| `app/routes/orders.py` | Business logic + span attributes + metric increments + structured logs |
| `app/routes/chaos.py` | Runtime failure/latency injection for demos |

### Create-order signal flow (say this out loud)

1. Request hits FastAPI → OTel creates an HTTP server span.
2. Handler opens child span `create_order`, sets attributes (`customer.id`, etc.).
3. On success: `orders_created_total` ++, `order_value_dollars` observe, JSON log `order_created`.
4. On chaos failure: `orders_failed_total{reason="chaos_injected"}` ++, error log, HTTP 503.
5. Instrumentator records RED metrics on `/metrics`.
6. Prometheus scrapes; Promtail ships logs; Collector ships traces.

---

## 8. Prometheus deep dive

### Config

`observability/prometheus/prometheus.yml`:

- `scrape_interval: 15s`
- Job `order-service` → `order-service:8000/metrics`

### Useful PromQL

```promql
# Request rate
sum(rate(http_requests_total{job="order-service"}[1m]))

# 5xx error ratio
sum(rate(http_requests_total{job="order-service",status=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="order-service"}[5m]))

# Latency percentiles
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{job="order-service"}[5m])) by (le))

# Business
sum(rate(orders_created_total[5m])) by (payment_method)
sum(rate(orders_failed_total[5m])) by (reason)
```

### Alerting

`observability/prometheus/alerts.yml` defines:

- `HighErrorRate` — 5xx ratio > 5% for 1m
- `HighLatencyP99` — p99 > 1s for 2m
- `OrdersFailing` — elevated `orders_failed_total` rate

View in Prometheus → **Alerts**. Trigger them with chaos (§13).

**Interview tip:** Alert on **symptoms** (user-facing error rate / latency), not only causes (CPU). Use multi-window burn-rate alerts for SLOs in production.

---

## 9. Grafana deep dive

Provisioning (no manual clicks required):

- Datasources: `observability/grafana/provisioning/datasources/datasources.yml`
- Dashboard provider: `.../dashboards/dashboards.yml`
- Dashboard JSON: `observability/grafana/dashboards/order-service-overview.json`

Practice:

1. Edit a panel → understand the PromQL.
2. Add a panel for `orders_in_progress`.
3. From a log line / trace, use correlations (Tempo ↔ Loki links are prewired).

---

## 10. Loki + Promtail deep dive

- **Promtail** discovers Docker containers via `/var/run/docker.sock`, parses JSON, attaches labels (`service`, `level`, `container`).
- **Loki** indexes **labels**, not full-text like Elasticsearch — keep label sets low-cardinality.

LogQL patterns:

```logql
{service="order-service"} |= "order_create_failed"
{service="order-service"} | json | level="ERROR"
sum(rate({service="order-service"} |= "order_create_failed" [1m]))
```

**Interview tip:** Metrics for alerting; logs for forensics; avoid unbounded labels like `order_id` on Loki streams.

---

## 11. Traces (OTel → Tempo)

Pipeline:

`app (OTLP gRPC :4317)` → `otel-collector` → `tempo` → Grafana Explore

Why a collector?

- App speaks one protocol (OTLP).
- Collector batches, retries, fans out (Tempo today, Datadog tomorrow).
- Keeps vendor logic out of application code — strong architecture answer.

Span attributes set in `routes/orders.py` (`order.id`, `order.total`) show up in Tempo — good for debugging a single customer request.

---

## 12. Datadog (optional commercial path)

1. Create a Datadog free trial → copy API key.
2. Put it in `.env`:

```env
DD_API_KEY=your_key_here
DD_SITE=datadoghq.com
```

(`DD_SITE` may be `datadoghq.eu` etc. depending on region.)

3. Start with the profile:

```powershell
docker compose --profile datadog up -d
```

4. In Datadog UI explore: **Infrastructure → Containers**, **Logs**, **APM** (if you later add `ddtrace` or OTel→Datadog exporter).

### How to talk about Datadog vs Prometheus/Grafana/Loki

| Topic | OSS stack | Datadog |
|-------|-----------|---------|
| Hosting | You operate it | SaaS |
| Cost model | Eng time + storage | Ingest/host/custom metrics pricing |
| Correlation | You wire Grafana links | First-class out of the box |
| Best for | Control, cost at scale, on-prem | Speed to value, unified product |

Strong answer: “I’ve run both. For learning and cost control I use Prometheus/Grafana/Loki/Tempo; for enterprise teams that want one vendor pane I use Datadog. The instrumentation concepts transfer.”

---

## 13. Simulate load and failures

Install script deps once (host Python):

```powershell
pip install -r scripts/requirements.txt
```

### Steady load

```powershell
python scripts/load_test.py --rps 10 --duration 60
```

### Full error simulation (recommended first demo)

```powershell
python scripts/simulate_errors.py --fail-rate 0.3 --latency-ms 600 --duration 90
```

This will:

1. Hit `/chaos/boom` (hard 500s).
2. Set fail rate + latency via `/chaos`.
3. Run load.
4. Send blocked-item `400`s.
5. Reset chaos.

### Named interview scenarios

```powershell
python scripts/chaos_scenarios.py latency
python scripts/chaos_scenarios.py errors
python scripts/chaos_scenarios.py spike
python scripts/chaos_scenarios.py mixed
```

### Manual chaos (no Python scripts)

```powershell
# 25% failures + 500ms delay
curl -X POST http://localhost:8000/chaos `
  -H "Content-Type: application/json" `
  -d "{\"fail_rate\":0.25,\"latency_ms\":500}"

# reset
curl -X POST http://localhost:8000/chaos/reset
```

Watch Grafana panels and Prometheus **Alerts** flip while traffic runs.

---

## 14. Incident walkthrough (practice script)

Say this in mock interviews while clicking the UIs:

1. **Detect** — Grafana error-rate panel rises / Prometheus `HighErrorRate` fires.
2. **Quantify** — “~25% 5xx, p99 ~600ms, order create rate flat.”
3. **Logs** — Loki: `order_create_failed` with `reason=chaos_injected`.
4. **Traces** — Tempo: spans marked error on `create_order`.
5. **Hypothesis** — “Upstream/simulated dependency failure, not bad deploy of happy-path logic.”
6. **Mitigate** — reset chaos / disable feature / rollback (in real life).
7. **Follow-up** — better alert threshold, runbook, dependency SLO.

That narrative is what interviewers want — not tool logos.

---

## 15. Interview Q&A cheat sheet

**Q: Difference between monitoring and observability?**  
A: Monitoring checks known conditions (dashboards/alerts you predefined). Observability is the ability to ask new questions about the system using metrics/logs/traces without shipping new code every time.

**Q: Why not only logs?**  
A: Logs are costly and high-cardinality; metrics are cheap for alerts/SLOs; traces explain *where* time went.

**Q: What is cardinality and why does it hurt Prometheus?**  
A: Each unique label set is a series. User IDs / request IDs as labels → memory blowup. Keep metrics aggregated; put IDs in logs/traces.

**Q: Pull vs push metrics?**  
A: Prometheus scrapes (pull) — simpler failure modes for targets, SD-based. Push useful for short-lived jobs (Pushgateway) or SaaS agents.

**Q: What is an exemplar?**  
A: A trace ID attached to a metric sample so you jump from a latency spike to an example trace.

**Q: How do you design alerts?**  
A: Alert on user symptoms + SLO burn. Page humans sparingly. Tickets for non-urgent. Every alert needs a runbook.

**Q: OpenTelemetry vs vendor agents?**  
A: OTel is vendor-neutral instrumentation API/SDK + collector. Vendor agents add proprietary features. Many teams instrument with OTel and export to Datadog/Grafana Cloud/etc.

**Q: Golden signals?**  
A: Latency, traffic, errors, saturation (Google SRE).

---

## 16. Troubleshooting

| Symptom | Check |
|---------|--------|
| `order-service` target DOWN | `docker compose logs order-service`; port 8000 |
| No logs in Loki | `docker compose logs promtail`; Docker socket mount on Windows/Mac needs Desktop running |
| No traces | `docker compose logs otel-collector tempo`; confirm `OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317` |
| Grafana login fails | default `admin`/`admin` from compose env |
| PromQL empty | Generate traffic first; wait 15–30s for scrapes |
| Datadog silent | Valid `DD_API_KEY`, correct `DD_SITE`, profile enabled |

Reset everything cleanly:

```powershell
docker compose down -v
docker compose up --build -d
```

---

## 17. What to say you built

> “I built a sample Order API and wired a full local observability stack: Prometheus for RED + business metrics and alert rules, Grafana dashboards, Loki/Promtail for structured logs, and OpenTelemetry exporting traces to Tempo. I also practiced incident workflows by injecting latency and failures, and optionally shipped the same environment telemetry to Datadog. I can walk through correlation across metrics → logs → traces and discuss SLO-style alerting.”

Rehearse that paragraph until it is natural. Then do one live demo with `chaos_scenarios.py mixed`.

---

## Next learning upgrades (optional)

After you are comfortable:

1. Add a second service (e.g. `payment-service`) and show distributed traces across both.
2. Add Grafana Alertmanager / notification channel (Slack webhook).
3. Instrument with `ddtrace` alongside OTel and compare UIs.
4. Define a real SLO (99% success / 30d) and a multi-window burn-rate alert.
5. Deploy the same compose stack to a VM / k8s and talk about service discovery (`kubernetes_sd_configs`).

You do not need these for a solid interview story — the lab as shipped is enough if you can operate and explain it.
