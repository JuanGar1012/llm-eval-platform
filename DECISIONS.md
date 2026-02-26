# DECISIONS.md

## 2026-02-25
- Added deterministic reproducibility fingerprints (`dataset`, `prompt`, `config`, `experiment_signature`) and persisted them on `runs` to support immutable experiment identity and auditability.
- Introduced release control status (`APPROVED`, `DRIFT_WARNING`, `BLOCKED`) derived from gate decision plus drift alerts to frame model evaluation as release governance.
- Extended run observability with runtime/performance fields (duration, avg latency, p95, token estimates, cost estimate) to signal production-readiness awareness.
- Added drift characterization using dataset-scoped historical trends and volatility, with alerts stored in run metadata for immediate UI/API consumption.
- Added failure surfacing primitives (worst sample ranking + keyword/schema failure clustering) to shift from metric-only reporting to debugging-oriented analysis.
- Added local model discovery (`/models/local`) and model override in `run from config` flow to keep UX local-first while improving experimentation speed.
- Adopted additive SQLite migration approach (column existence checks + `ALTER TABLE ADD COLUMN`) to preserve local user data without destructive resets.
- Added run deep-link architecture with FastAPI UI catch-all (`/ui/{path:path}`) and client-side route handling for `/ui/runs/<RUN_ID>`, making run detail a first-class navigable entity.
- Added dedicated run detail page structure in UI with identity metadata, signature visibility, gate/delta context, failure preview, tag-slice view, and observability summary.
- Persisted drift alerts in dedicated `run_drift_alerts` storage (in addition to metadata fallback) to support historical timeline queries and stronger auditability.
- Added CLI parity commands (`run-trends`, `run-failures`, `run-release-decision`, `run-alerts`) to ensure non-UI workflows have full analysis access.
- Added threshold overlay UX showing allowed drop vs actual drop and breach amount in compare and run-detail contexts to improve release-risk interpretability.
- Added dataset-slice degradation ranking in run detail to prioritize investigation toward highest-impact slices.
- Hardened token estimation with optional `tiktoken` tokenization when available, preserving deterministic fallback when unavailable.
- Added drift alert export into Markdown/JSON reports so offline artifacts carry release-risk timeline evidence without requiring live DB/API access.
- Added failure pagination at service/API/CLI boundaries (`limit` + `offset` + `total` + `has_more`) to keep large run diagnostics tractable.
- Added UI filtering for alert timeline by severity and metric to reduce debugging noise in long-lived datasets.
- Added threshold overlay math utility in analysis layer with dedicated tests to keep allowed-drop/breach calculations consistent across surfaces.

## 2026-02-26
- Reframed the UI around a guided workflow pathway (`Runs -> Board -> Diagnostics -> Compare -> Artifacts`) with per-step purpose and completion criteria to reduce onboarding ambiguity.
- Added progressive step locking across both top workflow cards and left workspace navigation so users cannot jump ahead before prerequisite steps are completed.
- Added guided tour mode with explicit progression controls and hard gating (`Next` disabled until current step is complete) to enforce sequential understanding.
- Added step-level visual spotlighting in Step 1 (dataset registration first, then run execution) so users are directed to the correct action order.
- Changed default run config path to `configs/baseline.yaml` to align first-run UX with baseline-first evaluation flow.
- Hid `Release Decision` until baseline/candidate pinning plus comparison are complete; replaced early empty panel with a lightweight prerequisite hint state.
- Refactored Run Identity rendering to card-based fingerprint blocks with wrapping (`break-all`) to prevent overlap and improve readability.
- Added run-execution animation and disabled-state controls to make long-running evaluation actions visibly in progress.

## 2026-02-26 (Checkpoint 1539)
- Added UI-first run setup controls: profile-based config selection, explicit config visibility, launcher history, seed/temperature overrides with guidance, and pinned-baseline auto-handoff for candidate runs.
- Extended API/service run-from-config flow to support runtime overrides (`seed`, `temperature`, `baseline_run_id`) while preserving reproducibility metadata.
- Added frontend and backend reset controls: workflow-cycle reset (UI-only state) and full app data reset endpoint (`/admin/reset`) with report cleanup.
- Added compare setup summary card to reduce run-id copy/paste and improve contextual clarity of baseline vs candidate setup.
- Improved guided tour directionality with section anchors, smooth-scroll targeting, and pulse spotlight on destination.
- Added Step Insights educational panel (expect/watch guidance) and post-tour celebration overlay for completion feedback.
- Added persistent light/dark mode toggle with local storage state and template-level dark CSS overrides.
- Kept checkpoint artifacts local-only by honoring `.gitignore` rules for `PROJECT_STATE.md` and `CHECKPOINTS/*`.
