from __future__ import annotations

from pathlib import Path

import yaml

from llm_eval_platform.analysis import (
    build_threshold_overlay,
    cluster_failures,
    summarize_trends,
    worst_failures,
)
from llm_eval_platform.config import AppConfig
from llm_eval_platform.domain.models import CompareResult, DriftSummary, EvalRunConfig, GateConfig
from llm_eval_platform.runner.experiment import ExperimentRunner, compute_metric_deltas
from llm_eval_platform.runner.ollama_client import OllamaClient
from llm_eval_platform.scoring.gates import evaluate_gates
from llm_eval_platform.storage.db import create_db_engine, get_schema_version, init_db
from llm_eval_platform.storage.repository import EvalRepository


class EvalService:
    def __init__(self, app_config: AppConfig) -> None:
        self.engine = create_db_engine(app_config.db_path)
        init_db(self.engine)
        self.repository = EvalRepository(self.engine)
        self.runner = ExperimentRunner(
            repository=self.repository,
            ollama_client=OllamaClient(app_config.ollama_url),
        )
        self.app_config = app_config

    def run_from_config(
        self,
        path: Path,
        model_name: str | None = None,
        *,
        seed: int | None = None,
        temperature: float | None = None,
        baseline_run_id: str | None = None,
    ):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload.setdefault("variant", {})
        payload.setdefault("gates", {})
        if model_name:
            payload["variant"]["model_name"] = model_name
        if seed is not None:
            payload["variant"]["seed"] = int(seed)
        if temperature is not None:
            payload["variant"]["temperature"] = float(temperature)
        if baseline_run_id is not None:
            payload["gates"]["baseline_run_id"] = baseline_run_id
        run_config = EvalRunConfig.model_validate(payload)
        run = self.runner.run(run_config)
        metadata = dict(run.metadata or {})
        metadata["config_path"] = str(path)
        if model_name:
            metadata["model_override"] = model_name
        if seed is not None:
            metadata["seed_override"] = int(seed)
        if temperature is not None:
            metadata["temperature_override"] = float(temperature)
        if baseline_run_id is not None:
            metadata["baseline_run_id_override"] = baseline_run_id
        self.repository.update_run_metadata(run_id=run.run_id, metadata=metadata)
        updated = self.repository.get_run(run.run_id)
        if updated is None:
            raise RuntimeError(f"Run {run.run_id} not found after metadata update.")
        return updated

    def reset_application_data(self, *, clear_reports: bool = True) -> dict:
        self.repository.reset_application_data()
        cleared_reports: list[str] = []
        if clear_reports:
            for suffix in ("*.md", "*.json"):
                for file in self.app_config.report_dir.glob(suffix):
                    try:
                        file.unlink(missing_ok=True)
                        cleared_reports.append(str(file))
                    except Exception:
                        continue
        return {"status": "ok", "cleared_reports": cleared_reports}

    def compare_runs(
        self,
        *,
        baseline_run_id: str,
        candidate_run_id: str,
        gate_config: GateConfig | None = None,
    ) -> CompareResult:
        baseline = self.repository.get_run(baseline_run_id)
        candidate = self.repository.get_run(candidate_run_id)
        if baseline is None or baseline.aggregate_metrics is None:
            raise ValueError(f"Baseline run {baseline_run_id} missing metrics.")
        if candidate is None or candidate.aggregate_metrics is None:
            raise ValueError(f"Candidate run {candidate_run_id} missing metrics.")
        effective_gate_config = gate_config or GateConfig(max_drop_from_baseline={})
        gate_decision = evaluate_gates(
            candidate=candidate.aggregate_metrics,
            baseline=baseline.aggregate_metrics,
            gate_config=effective_gate_config,
        )
        return CompareResult(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            baseline_metrics=baseline.aggregate_metrics,
            candidate_metrics=candidate.aggregate_metrics,
            deltas=compute_metric_deltas(candidate.aggregate_metrics, baseline.aggregate_metrics),
            gate_decision=gate_decision,
            threshold_overlay=build_threshold_overlay(
                deltas=compute_metric_deltas(candidate.aggregate_metrics, baseline.aggregate_metrics),
                allowed_drops=effective_gate_config.max_drop_from_baseline,
            ),
        )

    def load_gate_config_file(self, path: Path) -> GateConfig:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "gates" in payload:
            payload = payload["gates"]
        return GateConfig.model_validate(payload)

    def schema_version(self) -> int:
        return get_schema_version(self.engine)

    def list_local_models(self) -> list[str]:
        return self.runner.list_local_models()

    def get_run_trends(self, run_id: str) -> DriftSummary:
        run = self.repository.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found.")
        history = self.repository.list_runs_by_dataset(run.dataset_name, run.dataset_version)
        trends, volatility = summarize_trends(history)
        persisted_alerts = self.repository.list_drift_alerts(run_id)
        alerts = (
            [alert.model_dump(mode="json") for alert in persisted_alerts]
            if persisted_alerts
            else (run.metadata or {}).get("drift_alerts", [])
        )
        return DriftSummary(
            run_id=run_id,
            dataset_name=run.dataset_name,
            dataset_version=run.dataset_version,
            trends=trends,
            volatility=volatility,
            alerts=alerts,
        )

    def get_failure_analysis(self, run_id: str, limit: int = 10, offset: int = 0) -> dict:
        results = self.repository.list_item_results(run_id)
        ranked = worst_failures(results, limit=max(len(results), 0))
        sliced = ranked[offset : offset + limit]
        return {
            "run_id": run_id,
            "worst_samples": [row.model_dump(mode="json") for row in sliced],
            "clusters": cluster_failures(results),
            "total": len(ranked),
            "offset": offset,
            "limit": limit,
            "has_more": (offset + limit) < len(ranked),
        }

    def get_alert_timeline(self, run_id: str) -> dict:
        return self.get_alert_timeline_paginated(run_id=run_id, limit=50, offset=0)

    def get_alert_timeline_paginated(
        self,
        *,
        run_id: str,
        limit: int,
        offset: int,
        severity: str | None = None,
        metric: str | None = None,
    ) -> dict:
        run = self.repository.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found.")
        run_alerts = [row.model_dump(mode="json") for row in self.repository.list_drift_alerts(run_id)]
        dataset_alerts_rows = self.repository.list_drift_alerts_for_dataset_paginated(
            dataset_name=run.dataset_name,
            dataset_version=run.dataset_version,
            limit=limit,
            offset=offset,
            severity=severity,
            metric_contains=metric,
        )
        dataset_alerts = [row.model_dump(mode="json") for row in dataset_alerts_rows]
        total = self.repository.count_drift_alerts_for_dataset(
            dataset_name=run.dataset_name,
            dataset_version=run.dataset_version,
            severity=severity,
            metric_contains=metric,
        )
        return {
            "run_id": run_id,
            "run_alerts": run_alerts,
            "dataset_alert_timeline": dataset_alerts,
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": (offset + limit) < total,
        }

    def get_tag_metrics_paginated(self, run_id: str, limit: int, offset: int) -> dict:
        rows = self.repository.list_tag_metrics_paginated(run_id, limit=limit, offset=offset)
        total = self.repository.count_tag_metrics(run_id)
        return {
            "run_id": run_id,
            "tag_metrics": [row.model_dump(mode="json") for row in rows],
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": (offset + limit) < total,
        }
