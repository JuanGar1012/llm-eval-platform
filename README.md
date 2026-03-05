# LLM Eval Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 1. Project Overview

`llm-eval-platform` is a production-style evaluation system for comparing LLM variants (prompt/model/retrieval settings), detecting quality regressions, and generating release evidence before shipping changes.

It is designed for AI engineering workflows where teams need to answer:
- Did the new prompt/model actually improve quality?
- Did any metric regress relative to baseline?
- Is output reliability stable across repeated runs and slices?
- Can the results be reproduced and audited later?

This project is **Local-first and zero-cost by design**:
- fully local runtime
- open-source model friendly (Ollama)
- no paid APIs
- no cloud dependency required

---

## 2. Key Capabilities

- **Dataset Registry (versioned JSONL)**
  - Registers benchmark datasets with checksum and version metadata.
  - Solves traceability problems when evaluating across changing datasets.

- **Experiment Runner (variant-based)**
  - Runs prompt/model/retrieval variants from YAML config.
  - Supports runtime overrides (model, seed, temperature, baseline run ID).
  - Solves controlled experiment execution for baseline vs candidate workflows.

- **Deterministic Scoring Pipeline**
  - exact match
  - keyword coverage
  - JSON schema validity
  - optional local LLM judge score
  - Solves deterministic, repeatable quality measurement without external services.

- **Regression Gates / AI Guardrails**
  - Minimum metric thresholds.
  - Max-drop-from-baseline thresholds.
  - Release status framing: `APPROVED`, `DRIFT_WARNING`, `BLOCKED`.
  - Solves release-safety decisioning instead of metric-only reporting.

- **Drift & Reliability Characterization**
  - Historical trend tracking and volatility.
  - Drift alert generation and dataset-level alert timeline.
  - Solves early warning for quality instability.

- **Failure Surfacing**
  - Worst-sample ranking by severity.
  - Schema violation and keyword-miss clustering.
  - Solves debugging depth and root-cause analysis.

- **Portfolio-Ready Reporting**
  - Markdown report
  - JSON report
  - metrics snapshot artifact
  - Solves reproducible evidence packaging for reviews and hiring portfolios.

---

## 3. System Architecture

### High-level components

- **UI Layer**: React + Tailwind dashboard (`/ui`) for guided workflows.
- **API Layer**: FastAPI endpoints for datasets, runs, compare, diagnostics, export.
- **Service Layer**: orchestration and business logic (`service.py`).
- **Runner Layer**: local Ollama generation + per-item scoring (`runner/experiment.py`).
- **Scoring & Gates Layer**: deterministic metrics and policy gates.
- **Analysis Layer**: trends, drift alerts, failure ranking, threshold overlays.
- **Storage Layer**: SQLite schema + repository access.
- **Reporting Layer**: report and snapshot exporters.

### ASCII architecture diagram

```text
User (UI/CLI)
   |
   v
FastAPI / Typer Interface
   |
   v
Service Orchestration Layer
   |
   +--> Dataset Registry (JSONL ingestion + checksum)
   |
   +--> Experiment Runner
   |      |
   |      +--> Retrieval Context Toggle (tag-based context injection)
   |      +--> Ollama Local Model Generation
   |      +--> Optional Local LLM Judge
   |
   +--> Scoring Layer
   |      +--> exact_match / keyword_coverage / schema_valid
   |
   +--> Gate Layer (min thresholds + max baseline drop)
   |
   +--> Analysis Layer (drift, volatility, failure clusters)
   |
   v
SQLite Persistence (runs, items, tag metrics, drift alerts)
   |
   v
Reporting (Markdown + JSON + metrics snapshot)
```

### Layer responsibilities

- **Interface layer**: accepts run commands and API requests, returns structured outputs.
- **Orchestration layer**: resolves config, invokes runner, triggers comparison/export.
- **Execution layer**: runs local model inference and captures latency/tokens/errors.
- **Evaluation layer**: computes deterministic metrics and applies release gates.
- **Reliability layer**: tracks drift, volatility, and high-severity failures.
- **Persistence layer**: stores all run artifacts for reproducible auditing.

---

## 4. Repository Structure

```text
.
|-- configs/                      # baseline/candidate run configurations
|-- datasets/                     # benchmark JSONL datasets
|-- src/llm_eval_platform/
|   |-- api.py                    # FastAPI routes
|   |-- cli.py                    # Typer CLI commands
|   |-- service.py                # orchestration/business logic
|   |-- config.py                 # app config + deterministic fingerprints
|   |-- domain/models.py          # typed domain contracts
|   |-- ingestion/registry.py     # dataset loading + checksum/version record
|   |-- runner/
|   |   |-- experiment.py         # end-to-end run execution pipeline
|   |   |-- ollama_client.py      # local model inference integration
|   |   `-- retrieval.py          # retrieval context helper
|   |-- scoring/
|   |   |-- metrics.py            # deterministic metric computation
|   |   `-- gates.py              # regression gate policy engine
|   |-- analysis.py               # trends, drift, failures, overlays
|   |-- storage/
|   |   |-- db.py                 # SQLite schema + migrations
|   |   `-- repository.py         # persistence/query abstraction
|   |-- reporting/exporter.py     # markdown/json/snapshot artifacts
|   `-- web/
|       |-- templates/index.html  # UI shell
|       `-- static/app.jsx        # guided React dashboard
|-- tests/                        # metrics, gates, analysis, API tests
|-- pyproject.toml                # packaging and dependencies
`-- LICENSE
```

---

## 5. Installation and Local Setup

### Requirements

- Python `>=3.10` (3.11 recommended)
- Ollama installed and running locally (`http://localhost:11434`)
- Local model pulled (example):

```powershell
ollama pull llama3.2:3b
```

### Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Optional (higher-fidelity token estimates):

```powershell
pip install tiktoken
```

### Start API + UI

```powershell
uvicorn llm_eval_platform.api:app --reload
```

Open:
- UI: `http://127.0.0.1:8000/ui`
- Health: `http://127.0.0.1:8000/health`

This setup remains fully local and does not require paid APIs or cloud services.

---

## 6. Example Usage

### Input

Example dataset row (`datasets/sample_benchmark.jsonl`):

```json
{
  "item_id": "json_001",
  "prompt": "Return JSON with fields status and reason for login failure due to incorrect password.",
  "keywords": ["incorrect password"],
  "output_schema": {
    "type": "object",
    "properties": {"status": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["status", "reason"]
  },
  "tags": {"domain": "auth", "difficulty": "easy", "format": "json"}
}
```

### Processing flow

1. Register dataset.
2. Run baseline config.
3. Run candidate config (optionally with retrieval enabled).
4. Compare baseline vs candidate.
5. Export report artifacts.

### Output

- Run-level metrics and gate decision.
- Delta comparison vs baseline.
- Failure diagnostics and drift alerts.
- Files:
  - `reports/<RUN_ID>.report.md`
  - `reports/<RUN_ID>.report.json`
  - `reports/<RUN_ID>.metrics_snapshot.json`

---

## 7. AI Evaluation Methodology

The evaluation pipeline is deterministic-first and reproducibility-oriented.

### Experiment design

- Variant configs define:
  - model
  - prompt template/version
  - retrieval toggle
  - seed and temperature
  - gate policies
- Dataset version/checksum is tracked to bind results to exact data state.

### Metrics implemented

- **Exact Match**: strict normalized string equality vs expected answer.
- **Keyword Coverage**: ratio of required keywords present in output.
- **Schema Validity**: JSON schema conformance for structured responses.
- **Optional Local LLM Judge**: normalized score from local judge model output.

### Aggregate tracking

- Per-run aggregate metric means.
- Per-tag slice metrics (`domain`, `difficulty`, `safety`, `format`).
- Baseline-vs-candidate metric deltas.
- Threshold overlay (`allowed_drop`, `actual_drop`, `breach`).

### Notes on additional metrics

Precision/Recall/F1/Retrieval relevance are not currently first-class metrics in this scaffold.  
The framework is designed so these can be added as future metric modules.

---

## 8. Guardrails and Safety Mechanisms

- **Regression gates**
  - `min_metric` thresholds enforce quality floors.
  - `max_drop_from_baseline` limits acceptable regressions.
- **Structured output validation**
  - JSON schema validation catches malformed structured responses.
- **Keyword constraints**
  - Coverage checks surface missing required concepts.
- **Release decision policy**
  - `APPROVED`, `DRIFT_WARNING`, `BLOCKED` based on gate + drift alerts.
- **Deterministic signatures**
  - Config/prompt/dataset fingerprints reduce ambiguity in debugging and audits.

Prompt-injection and adversarial input hardening are not fully implemented as a dedicated security module; this is a known extension area.

---

## 9. Failure Modes and Limitations

- **Prompt sensitivity**
  - Small prompt wording changes can produce large output shifts.
- **Baseline dependency risk**
  - Candidate run may fail if referenced baseline run ID is stale or missing.
- **Retrieval simplicity**
  - Current retrieval helper injects tag context only; no semantic retrieval/ranking yet.
- **Metric scope**
  - Current metrics are deterministic but may not capture deeper semantic correctness.
- **Volatility thresholds**
  - Drift alert thresholds are heuristic and dataset-dependent.
- **Local inference constraints**
  - Latency and quality vary by local hardware and model availability.
- **Token estimation**
  - Falls back to heuristic (`chars/4`) when tokenizer package is unavailable.

---

## 10. Future Improvements

- Add semantic metrics (e.g., relevance/entailment and rubric-based scoring).
- Add retrieval quality metrics and optional vector database integration.
- Add stronger safety policies for prompt injection and refusal compliance testing.
- Add asynchronous run queue and parallel execution controls.
- Add richer benchmark datasets and long-horizon regression suites.
- Add UI e2e test harness for guided workflow/tour verification.
- Add optional distributed execution mode while preserving local-first defaults.

---

## 11. Why This Project Matters for AI Engineering

It demonstrates:
- **LLM systems design**: model/prompt/retrieval variant orchestration.
- **Experiment evaluation rigor**: deterministic metrics, run lineage, baseline deltas.
- **AI safety/reliability thinking**: guardrails, release gates, drift/failure visibility.
- **Backend integration depth**: FastAPI + typed domain models + repository pattern.
- **Reproducible local AI development**: zero-cost, no-cloud workflow suitable for controlled testing.


---

## 12. License

This project is licensed under the **MIT License**.  
See [`LICENSE`](LICENSE) for details.
