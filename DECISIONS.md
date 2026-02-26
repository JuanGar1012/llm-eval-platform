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
