# LLM Eval Platform (Local-Only, Zero API Cost)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Production-style starter for evaluating prompt/model/retrieval variants with regression gates before release.

## What This Scaffold Includes

- Python-first architecture with strong type hints and modular packages.
- FastAPI endpoints for dataset registration, run execution, comparison, and report export.
- End-user web UI built with React + Tailwind CSS (blue theme) at `/ui`.
  - Workflow navigation: Board, Runs, Compare, Diagnostics, Artifacts
  - Pin baseline/candidate runs
  - Release decision card with blockers/checklist
  - Metric trend sparklines across repeated runs
  - Local model picker from Ollama (`/models/local`)
- Typer CLI with required commands:
  - `register-dataset`
  - `run-eval`
  - `compare-runs`
  - `export-report`
  - `db-check`
  - `run-trends`
  - `run-failures`
  - `run-release-decision`
  - `run-alerts`
- SQLite storage for datasets, runs, item-level scores, and gate outcomes.
- Rule-based scoring:
  - exact match
  - keyword coverage
  - structured JSON output schema validity
- Optional local LLM-judge mode (Ollama model only).
- Regression gates (minimum metrics + max drop from baseline).
- Markdown + JSON reporting with per-tag breakdown and pass/fail gate status.
- Portfolio-ready metrics snapshot JSON artifact.

## Folder Structure

```text
.
|-- configs/
|   |-- baseline.yaml
|   `-- candidate.yaml
|-- datasets/
|   `-- sample_benchmark.jsonl
|-- reports/
|-- src/llm_eval_platform/
|   |-- api.py
|   |-- cli.py
|   |-- config.py
|   |-- service.py
|   |-- domain/models.py
|   |-- ingestion/registry.py
|   |-- runner/{experiment.py, ollama_client.py, retrieval.py}
|   |-- scoring/{metrics.py, gates.py}
|   |-- storage/{db.py, repository.py}
|   |-- web/templates/index.html
|   |-- web/static/app.jsx
|   `-- reporting/exporter.py
`-- tests/
    |-- test_metrics.py
    `-- test_gates.py
```

## Prerequisites (Windows PowerShell)

1. Python 3.10+ installed.
2. Ollama installed and running (`http://localhost:11434`).
3. Local model pulled, for example:
   ```powershell
   ollama pull llama3.2:3b
   ```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Optional (higher-fidelity token estimation):

```powershell
pip install tiktoken
```

Token estimation strategy:
- Default fallback: character heuristic (`chars/4`) for deterministic local operation.
- If `tiktoken` is installed, runner will use model-aware encoding lookup and fallback to `cl100k_base`.
- Recommended mapping guidance:
  - Llama-family local models: fallback encoding is acceptable for relative trend tracking.
  - OpenAI-family names (if used in configs for portability): `tiktoken.encoding_for_model` will be used when available.

## CLI Workflow

### 1) Register Dataset

```powershell
llm-eval register-dataset --dataset-name sample_benchmark --version v1 --path datasets\sample_benchmark.jsonl
```

Expected output example:

```text
registered dataset sample_benchmark:v1 (4 items)
```

### 2) Run Baseline

```powershell
llm-eval run-eval --config configs\baseline.yaml
```

Expected output example:

```text
completed run 2f2c2d580f1e6d3a-v1 status=completed
{
  "exact_match": 0.5,
  "keyword_coverage": 0.67,
  "schema_valid": 0.75,
  "llm_judge_score": null,
  "sample_count": 4
}
```

### 3) Run Candidate (set baseline in config first)

Update `configs/candidate.yaml`:
- Set `gates.baseline_run_id` to your baseline run id.

Then run:

```powershell
llm-eval run-eval --config configs\candidate.yaml
```

### 4) Compare Runs

```powershell
llm-eval compare-runs --baseline-run-id <BASELINE_RUN_ID> --candidate-run-id <CANDIDATE_RUN_ID>
```

### 5) Export Report + Portfolio Snapshot

```powershell
llm-eval export-report --run-id <CANDIDATE_RUN_ID> --baseline-run-id <BASELINE_RUN_ID> --output-dir reports
```

Artifacts:
- `reports/<RUN_ID>.report.md`
- `reports/<RUN_ID>.report.json`
- `reports/<RUN_ID>.metrics_snapshot.json`

### 6) Check DB Schema Version

```powershell
llm-eval db-check
```

Expected output example:

```json
{
  "db_path": "C:\\Users\\you\\project\\llm_eval.db",
  "schema_version": 1
}
```

## API Workflow

Start API:

```powershell
uvicorn llm_eval_platform.api:app --reload
```

Open UI:

```text
http://127.0.0.1:8000/ui
```

Run detail deep-link:

```text
http://127.0.0.1:8000/ui/runs/<RUN_ID>
```

Notes:
- UI uses React (UMD) + Tailwind CDN to keep setup zero-build and local-first.
- For production hardening later, migrate UI to a bundled React build (Vite) and keep the same API routes.

Endpoints:
- `GET /health` (includes DB schema version)
- `GET /ui` (local dashboard)
- `GET /runs` (list runs)
- `GET /models/local` (list locally available Ollama models)
- `POST /datasets/register`
- `POST /runs`
- `POST /runs/from-config`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/results`
- `GET /runs/{run_id}/tag-metrics`
- `GET /runs/{run_id}/trends`
- `GET /runs/{run_id}/failures` (`limit`, `offset` query params)
- `GET /runs/{run_id}/release-decision`
- `GET /runs/{run_id}/alerts`
- `POST /compare`
- `POST /reports/export`

## Config Files

- Baseline config: `configs/baseline.yaml`
- Candidate config: `configs/candidate.yaml`

Both use this schema:

```yaml
variant:
  name: string
  dataset_name: string
  dataset_version: string
  model_name: string
  prompt_version: string
  prompt_template: "Task: {prompt}"
  retrieval_enabled: false
  llm_judge_enabled: false
  llm_judge_model: null
  seed: 42
  temperature: 0.0
gates:
  baseline_run_id: null
  min_metric:
    exact_match: 0.2
  max_drop_from_baseline:
    exact_match: 0.05
```

## Where To Plug In Real Data and Thresholds

- Replace placeholder benchmark with your real JSONL prompts in `datasets/`.
- Register your dataset version via `register-dataset`.
- Set your acceptance thresholds in:
  - `gates.min_metric`
  - `gates.max_drop_from_baseline`
- Add/adjust tags (`domain`, `difficulty`, `safety`, `format`) per row for richer per-tag reporting.

## Run Tests

```powershell
pytest -q
```

## LinkedIn Project Entry (Recruiter-Optimized)

### 1) LinkedIn Project Title
**LLM Evaluation Platform | Local AI Systems, Model Benchmarking, AI Guardrails (FastAPI + Python)**

### 2) One-Line Summary
Built a local-first, zero-API-cost LLM evaluation framework that benchmarks prompt/model/RAG variants, applies regression gates, and exports reproducible evidence for AI reliability.

### 3) LinkedIn Description (3–5 bullets)
- Designed a production-style **AI Evaluation Framework** for **LLMs** using **Python** + **FastAPI**, with CLI/API/UI parity for experiment execution, diagnostics, and report export.
- Implemented experiment orchestration for **Prompt Engineering**, local **Transformer Models** (Ollama), retrieval-on/off evaluation (**RAG** flow), and deterministic scoring (exact match, keyword coverage, JSON schema validity).
- Added release-safety controls with **AI Guardrails**: minimum quality thresholds, baseline-vs-candidate max-drop gates, and explicit release decisions (`APPROVED`, `DRIFT_WARNING`, `BLOCKED`).
- Built reproducibility and reliability primitives: deterministic fingerprints/signatures, SQLite experiment tracking, trend/volatility drift analysis, failure clustering, and run-level observability (latency, p95, token estimates).
- Delivered a local-only evaluation cockpit and artifact pipeline (Markdown/JSON snapshots) to support **Experiment Evaluation**, **Model Benchmarking**, and interview-ready evidence without paid APIs.

### 4) Key Technologies
- Python, FastAPI, Typer CLI, SQLite, SQLAlchemy
- Ollama (local LLM runtime), JSON Schema validation, PyYAML
- React (UMD), Tailwind CSS, structured logging
- Local-first evaluation workflows with optional RAG-style retrieval hooks

### 5) AI Engineering Signals
- **AI Reliability:** regression gating, drift alerts, and failure-mode surfacing.
- **Reproducibility:** deterministic run IDs, fingerprints, and experiment signatures.
- **Evaluation Depth:** deterministic metrics plus optional local LLM judge.
- **Infrastructure Thinking:** modular backend layers, persistent storage, API/CLI parity, report artifacts.
- **Applied GenAI Delivery:** local AI systems design, prompt/model variant testing, and release-readiness controls.
- **Scalable Extension Paths:** retrieval and **Vector Database** integration points, and **Agent Orchestration**-style workflow controls in the UI pipeline.

### 6) GitHub Link Placement
- Place the repository URL directly under the first two lines of the LinkedIn project entry:
  - **GitHub:** https://github.com/JuanGar1012/llm-eval-platform
