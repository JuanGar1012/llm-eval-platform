# PROJECT_STATE.md

## Goal
- Build a local-first, zero-API-cost LLM evaluation and release-safety platform with production-style reproducibility, regression gating, diagnostics, observability, and a guided UI workflow.

## Non-goals
- No managed cloud services.
- No paid model APIs.
- No heavy frontend build pipeline requirement for dashboard operation.

## Current architecture
- Backend: FastAPI with service/repository layering.
- Runner: local Ollama inference and optional local judge.
- Storage: SQLite with additive migration behavior.
- UI: React UMD + Tailwind CDN cockpit served by FastAPI; run-first views and guided workflow tour.
- Reports: Markdown/JSON exports plus metrics snapshot artifacts.

## Data model (current)
- `datasets`: versioned dataset registry and checksums.
- `runs`: run metadata, reproducibility fingerprints/signature, metrics, gates, release status, observability metrics.
- `item_results`: per-sample outputs, deterministic scores, misses/errors, latency/tokens.
- `run_tag_metrics`: tag/slice aggregate metrics.
- `run_drift_alerts`: persisted run and dataset-level drift alerts.
- `schema_metadata`: schema version tracking.

## Key commands (dev/test/run)
- Setup: `python -m venv .venv`, `.venv\Scripts\Activate.ps1`, `pip install -e .[dev]`
- Tests: `pytest -q`
- API/UI: `uvicorn llm_eval_platform.api:app --reload`
- UI URL: `http://127.0.0.1:8000/ui`
- Reset local state: `Remove-Item .\llm_eval.db`, `Remove-Item .\reports\*.md`, `Remove-Item .\reports\*.json`

## Files created/modified (high-level)
- `src/llm_eval_platform/web/static/app.jsx`: guided workflow strip, tour panel, step locking, run-execution animation, run identity layout fix, release-decision visibility gating.
- `src/llm_eval_platform/api.py`: run diagnostics/timeline endpoints and UI routing support.
- `src/llm_eval_platform/service.py`: paginated alert/tag/failure analysis services.
- `src/llm_eval_platform/storage/db.py`, `src/llm_eval_platform/storage/repository.py`: drift alert persistence and pagination access patterns.
- `src/llm_eval_platform/runner/experiment.py`: reproducibility, gate/release metadata, observability instrumentation.
- `src/llm_eval_platform/analysis.py`: threshold overlay and drift/failure analysis helpers.
- `tests/test_api.py`, `tests/test_analysis.py`: API/analysis coverage for added behavior.
- `.gitignore`: private talk-track file ignore.
- `INTERVIEW_TALK_TRACK.md` (ignored): internal demo/interview script.

## Completed items
- Deterministic reproducibility fingerprints (`dataset`, `prompt`, `config`, `experiment_signature`) persisted in run records.
- Regression gate + release status model (`APPROVED`, `DRIFT_WARNING`, `BLOCKED`) implemented.
- Trend, volatility, drift alerts, and alert timeline exposed through API and UI.
- Failure surfacing (worst samples + cluster summaries) with pagination.
- Threshold overlays (allowed drop vs actual drop vs breach) implemented across compare and run detail.
- Local model discovery integrated into run form.
- Run-detail route and diagnostics page implemented.
- Run execution UX includes active animation, disabled controls, and completion/error messaging.
- Guided workflow system implemented with:
  - step cards
  - completion criteria text
  - progressive locking
  - guided tour with progress panel
  - locked tour advancement until current step completion
  - step-1 spotlight (dataset registry first, then run execution)
- Run Identity overlap fixed with card-based fingerprint presentation.
- Release Decision panel hidden until baseline + candidate + compare prerequisites are satisfied, with lightweight hidden-state hint.
- Test suite stable (`12 passed`).

## Open tasks (prioritized)
- [ ] Add frontend test harness (Playwright or JS unit tests) for guided tour and step-lock UX behavior.
- [ ] Add optional background run queue for long-running evaluations.
- [ ] Add CSV export for failures/tag metrics.

## Known issues / edge cases
- Token estimates remain heuristic when `tiktoken` is not installed.
- Local model list depends on Ollama availability.
- UI is CDN UMD-based; no production bundling pipeline yet.
- Additive migrations cover column additions but not destructive/type-changing migrations.
- Guided step completion currently infers from available run/result state; explicit dataset-registration flag is session-level UI state.

## Next 3 actions checklist
- [ ] Add automated UI regression checks for guided tour locks and step transitions.
- [ ] Add per-step inline “required action” links (jump/focus controls).
- [ ] Add optional demo seed mode for first-time UI walkthrough.
