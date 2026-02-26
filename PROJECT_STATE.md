# PROJECT_STATE.md

## Goal
- Build a local-first, zero-API-cost LLM evaluation and release-safety platform with production-style reproducibility, regression gating, diagnostics, and observability.

## Non-goals
- No managed cloud services.
- No paid model APIs.
- No heavy frontend build pipeline requirement for dashboard operation.

## Current architecture
- Backend: FastAPI + service/repository layers.
- Runner: local Ollama inference and optional local judge.
- Storage: SQLite with additive migration logic.
- UI: React UMD + Tailwind CDN cockpit served by FastAPI, with route-level run detail view.
- Reports: Markdown/JSON + metrics snapshot artifacts.

## Data model (current)
- `datasets`: versioned dataset registry.
- `runs`: run metadata, gate decision, fingerprints, release status, latency/tokens/cost estimates.
- `item_results`: per-sample outputs, scores, misses, schema errors, latency/tokens.
- `run_tag_metrics`: per-tag aggregate metrics for slice analysis.
- `schema_metadata`: schema version tracking.

## Key commands
- Setup: `python -m venv .venv`, `.venv\Scripts\Activate.ps1`, `pip install -e .[dev]`
- Tests: `pytest -q`
- CLI DB check: `llm-eval db-check`
- API: `uvicorn llm_eval_platform.api:app --reload`
- UI: open `http://127.0.0.1:8000/ui`
- Run detail: open `http://127.0.0.1:8000/ui/runs/<RUN_ID>`

## Files modified (high-level)
- `src/llm_eval_platform/config.py`: reproducibility fingerprint generation.
- `src/llm_eval_platform/storage/db.py`: schema extensions and additive migration logic.
- `src/llm_eval_platform/storage/repository.py`: persistence/read APIs for new run/item/tag fields.
- `src/llm_eval_platform/runner/experiment.py`: run instrumentation, fingerprints, drift alerts, release status, latency/tokens.
- `src/llm_eval_platform/analysis.py`: trends, volatility, drift alerts, failure ranking/clustering.
- `src/llm_eval_platform/service.py`: trends and failure analysis services.
- `src/llm_eval_platform/api.py`: analysis endpoints, local model list endpoint, `/ui/{path}` deep-link support.
- `src/llm_eval_platform/runner/ollama_client.py`: local model listing via `/api/tags`.
- `src/llm_eval_platform/web/static/app.jsx`: run-first cockpit enhancements, pinned compare flow, run-detail route page and diagnostics.
- `tests/test_api.py`: endpoint coverage updates.
- `README.md`: route/features updates.
- `AGENTS.md`: context management policy.

## Completed items
- Deterministic run-level fingerprints and experiment signature implemented and stored.
- Release status layer added (`APPROVED`, `DRIFT_WARNING`, `BLOCKED`).
- Observability metrics added: duration, avg latency, p95, token estimates, cost estimate.
- Drift characterization added: trends, volatility, drift alerts.
- Failure surfacing added: worst samples and failure clustering endpoints.
- Tag-level slice metrics persisted and exposed.
- Local model discovery endpoint added and wired to UI run execution form.
- UI upgraded with pin baseline/candidate, release decision panel, trends, diagnostics previews, and dedicated run detail route/page.
- Drift alerts persisted as first-class DB rows with run and dataset-level timeline API.
- Threshold overlays and allowed-drop breach indicators added to compare and run-detail views.
- CLI parity added for trends/failures/release-decision/alert timeline.
- Dataset-slice degradation ranking panel added on run detail.
- Token estimation hardened with optional `tiktoken` path and deterministic fallback.
- Drift alerts exported in report artifacts (Markdown + JSON) with timeline.
- Alert timeline filtering controls (severity + metric) added in run detail UI.
- Failure inspection API/CLI now supports pagination (`limit`, `offset`, `total`, `has_more`).
- Threshold overlay utility covered by dedicated tests.
- Run-detail UI pagination is now fully prop-driven and uses API metadata (`total`, `has_more`) for tag metrics and alert timeline controls.
- Test suite passing (`12 passed`).

## Open tasks (priority order)
- No queued tasks remaining from the prior checkpoint list.

## Known issues / edge cases
- Legacy DBs created before new columns rely on additive migration; destructive or type-change migrations are not handled.
- Token estimates use heuristic (`chars/4`), not tokenizer-accurate.
- Local model endpoint depends on Ollama availability; returns empty model list when unavailable.
- UI uses CDN-delivered React/Tailwind in-browser; production bundling is not yet applied.
- Route handling is client-side in UMD React; refreshing on unknown nested paths depends on FastAPI catch-all `/ui/{path:path}`.
- `tiktoken` is optional; without it token estimates remain heuristic and best used for trend direction.

## Next 3 actions
- [ ] Add JS test harness (Vitest + RTL or Playwright smoke) for run-detail pagination and threshold overlay rendering.
- [ ] Add CSV export for failures and tag metrics to support offline review workflows.
- [ ] Add background run queue mode for multi-variant batches from UI without blocking request cycle.
