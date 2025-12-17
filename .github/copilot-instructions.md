<!-- .github/copilot-instructions.md for sre-starter -->
# SRE Starter — Copilot instructions

Purpose: Give an AI coding agent the minimal, actionable context needed to be productive in this repo.

## Big picture
- This is a tiny SRE demo service (FastAPI) that exposes:
  - /metrics (Prometheus) via prometheus_fastapi_instrumentator
  - /alertmanager webhook to receive Alertmanager notifications
  - /health and a root endpoint
- Monitoring stack is defined in `docker-compose.monitoring.yml` and `monitoring/` (Prometheus, Alertmanager, Grafana).

## Key files to inspect
- `app/main.py` — main FastAPI app, logging, metrics, exception handling, and webhook receiver.
- `docker-compose.monitoring.yml` — brings up Prometheus (9090), Alertmanager (9093), Grafana (3000).
- `monitoring/prometheus.yml` — scrape config (targets `host.docker.internal:8000`) and `alerts.yml` rule file.
- `monitoring/alerts.yml` — Prometheus rules (examples: `High5xxErrorRate`, `HighP95Latency`).
- `monitoring/alertmanager.yml` — receivers (Slack webhook + webhook to `/alertmanager`).

## Quick developer workflows (commands)
- Run the app locally (recommended for rapid iteration):
  - APP_ENV=dev LOG_LEVEL=INFO python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
- Start the monitoring stack (macOS):
  - docker compose -f docker-compose.monitoring.yml up -d
- Useful checks:
  - curl http://localhost:8000/metrics
  - curl -X POST http://localhost:8000/alertmanager -d '{}' -H 'Content-Type: application/json'
  - Visit Prometheus (http://localhost:9090), Alertmanager (http://localhost:9093), Grafana (http://localhost:3000)

## Project-specific patterns & conventions
- Logging: JSON-formatted logs via `logging` (see `LOG_LEVEL`, `APP_ENV`). Two loggers: `sre-starter` (access) and `alert-recv` (webhook summaries).
- Access logging is implemented as FastAPI middleware that writes compact JSON with env/method/path/status/latency.
- Errors: a global exception handler returns a simple `500` with `{"detail":"internal_error"}` and logs full details.
- Metrics: `prometheus_fastapi_instrumentator` is used with
  - `should_group_status_codes=True` (status labels like `2xx/4xx/5xx`)
  - `excluded_handlers=["/metrics"]`
- Alerts reference metric names and labels from instrumentator (see `monitoring/alerts.yml`). Verify the metric names the instrumentator actually exports (e.g., the repo's alerts reference `http_requests_total` and `http_request_duration_highr_seconds_bucket`).

## Integration notes & gotchas
- Prometheus scrapes `host.docker.internal:8000` — the app MUST be reachable from host (not only from a container). On macOS this resolves correctly in Docker for Mac.
- Alertmanager forwards alerts to `http://host.docker.internal:8000/alertmanager` and to Slack (see `monitoring/alertmanager.yml`). The Slack `api_url` in the repo is committed — treat as sensitive and prefer using secrets or env substitution in real projects.
- Test alert flow: run the app, bring up monitoring stack, hit `GET /fail` repeatedly or trigger rules manually in Prometheus UI to validate alerts reach `/alertmanager` and Slack.

## When changing metrics/alerts
- If you change metric names or labels in instrumentation code, update `monitoring/alerts.yml` accordingly; mismatches will silently prevent alerts from firing.

## Quick checklist for an AI agent
1. Verify the app runs on port 8000 and `/metrics` exposes expected metric names.
2. Confirm Prometheus `scrape_configs` and Alertmanager `route` match expected endpoints.
3. Check for hard-coded secrets (e.g., Slack webhook) and flag them.
4. If adding or changing alerts, add a short note in `monitoring/alerts.yml` explaining the rationale and the metric used.

---
If any section is unclear or you'd like me to expand examples (e.g., a quick test script that triggers an alert end-to-end), tell me which part to iterate on. ✅
