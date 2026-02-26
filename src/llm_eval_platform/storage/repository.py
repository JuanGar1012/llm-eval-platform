from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Engine

from llm_eval_platform.domain.models import (
    AggregateMetrics,
    DatasetRecord,
    DriftAlertRecord,
    GateDecision,
    ItemResult,
    RunRecord,
    TagMetricRecord,
)
from llm_eval_platform.storage.db import (
    datasets_table,
    item_results_table,
    run_drift_alerts_table,
    run_tag_metrics_table,
    runs_table,
)


logger = logging.getLogger(__name__)


class EvalRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert_dataset(self, record: DatasetRecord) -> None:
        payload = record.model_dump()
        with self._engine.begin() as conn:
            conn.execute(
                delete(datasets_table).where(
                    (datasets_table.c.dataset_name == record.dataset_name)
                    & (datasets_table.c.version == record.version)
                )
            )
            conn.execute(insert(datasets_table).values(**payload))

    def get_dataset(self, dataset_name: str, version: str) -> DatasetRecord | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(datasets_table).where(
                    (datasets_table.c.dataset_name == dataset_name)
                    & (datasets_table.c.version == version)
                )
            ).mappings().first()
        if not row:
            return None
        return DatasetRecord.model_validate(dict(row))

    def next_run_version(self, run_key: str) -> int:
        with self._engine.begin() as conn:
            current = conn.execute(
                select(func.max(runs_table.c.run_version)).where(runs_table.c.run_key == run_key)
            ).scalar_one_or_none()
        return (current or 0) + 1

    def create_run(self, run: RunRecord) -> None:
        payload = run.model_dump()
        with self._engine.begin() as conn:
            conn.execute(insert(runs_table).values(**payload))

    def update_run_status(
        self,
        *,
        run_id: str,
        status: str,
        aggregate_metrics: AggregateMetrics | None = None,
        gate_decision: GateDecision | None = None,
        metadata: dict[str, Any] | None = None,
        release_status: str | None = None,
        duration_ms: float | None = None,
        avg_latency_ms: float | None = None,
        p95_latency_ms: float | None = None,
        token_in_est: int | None = None,
        token_out_est: int | None = None,
        cost_est_usd: float | None = None,
    ) -> None:
        payload: dict[str, Any] = {"status": status}
        if status in {"completed", "failed"}:
            payload["completed_at"] = datetime.now(tz=timezone.utc)
        if aggregate_metrics is not None:
            payload["aggregate_metrics"] = aggregate_metrics.model_dump()
        if gate_decision is not None:
            payload["gate_decision"] = gate_decision.model_dump()
        if metadata is not None:
            payload["metadata"] = metadata
        if release_status is not None:
            payload["release_status"] = release_status
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if avg_latency_ms is not None:
            payload["avg_latency_ms"] = avg_latency_ms
        if p95_latency_ms is not None:
            payload["p95_latency_ms"] = p95_latency_ms
        if token_in_est is not None:
            payload["token_in_est"] = token_in_est
        if token_out_est is not None:
            payload["token_out_est"] = token_out_est
        if cost_est_usd is not None:
            payload["cost_est_usd"] = cost_est_usd
        with self._engine.begin() as conn:
            conn.execute(update(runs_table).where(runs_table.c.run_id == run_id).values(**payload))

    def insert_item_results(self, results: list[ItemResult]) -> None:
        if not results:
            return
        payload = []
        for result in results:
            entry = result.model_dump()
            scores = entry.pop("scores")
            entry["exact_match"] = scores["exact_match"]
            entry["keyword_coverage"] = scores["keyword_coverage"]
            entry["schema_valid"] = scores["schema_valid"]
            entry["llm_judge_score"] = scores["llm_judge_score"]
            payload.append(entry)
        with self._engine.begin() as conn:
            conn.execute(insert(item_results_table), payload)

    def list_item_results(self, run_id: str) -> list[ItemResult]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(item_results_table).where(item_results_table.c.run_id == run_id)
            ).mappings().all()
        result_items: list[ItemResult] = []
        for row in rows:
            result_items.append(
                ItemResult.model_validate(
                    {
                        "run_id": row["run_id"],
                        "item_id": row["item_id"],
                        "prompt": row["prompt"],
                        "output_text": row["output_text"],
                        "expected_answer": row.get("expected_answer"),
                        "keywords": row.get("keywords") or [],
                        "error": row["error"],
                        "latency_ms": row.get("latency_ms"),
                        "token_in_est": row.get("token_in_est"),
                        "token_out_est": row.get("token_out_est"),
                        "schema_error": row.get("schema_error"),
                        "keyword_misses": row.get("keyword_misses") or [],
                        "scores": {
                            "exact_match": row["exact_match"],
                            "keyword_coverage": row["keyword_coverage"],
                            "schema_valid": row["schema_valid"],
                            "llm_judge_score": row["llm_judge_score"],
                        },
                        "tags": row["tags"] or {},
                    }
                )
            )
        return result_items

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._engine.begin() as conn:
            row = conn.execute(select(runs_table).where(runs_table.c.run_id == run_id)).mappings().first()
        if not row:
            return None
        return RunRecord.model_validate(dict(row))

    def list_runs(self) -> list[RunRecord]:
        with self._engine.begin() as conn:
            rows = conn.execute(select(runs_table).order_by(runs_table.c.started_at.desc())).mappings().all()
        return [RunRecord.model_validate(dict(row)) for row in rows]

    def list_runs_by_dataset(self, dataset_name: str, dataset_version: str) -> list[RunRecord]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(runs_table)
                .where(
                    (runs_table.c.dataset_name == dataset_name)
                    & (runs_table.c.dataset_version == dataset_version)
                )
                .order_by(runs_table.c.started_at.asc())
            ).mappings().all()
        return [RunRecord.model_validate(dict(row)) for row in rows]

    def replace_tag_metrics(self, run_id: str, metrics: list[TagMetricRecord]) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(run_tag_metrics_table).where(run_tag_metrics_table.c.run_id == run_id))
            if metrics:
                conn.execute(insert(run_tag_metrics_table), [metric.model_dump() for metric in metrics])

    def list_tag_metrics(self, run_id: str) -> list[TagMetricRecord]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(run_tag_metrics_table).where(run_tag_metrics_table.c.run_id == run_id)
            ).mappings().all()
        return [TagMetricRecord.model_validate(dict(row)) for row in rows]

    def list_tag_metrics_paginated(self, run_id: str, limit: int, offset: int) -> list[TagMetricRecord]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(run_tag_metrics_table)
                .where(run_tag_metrics_table.c.run_id == run_id)
                .order_by(run_tag_metrics_table.c.sample_count.desc(), run_tag_metrics_table.c.id.asc())
                .limit(limit)
                .offset(offset)
            ).mappings().all()
        return [TagMetricRecord.model_validate(dict(row)) for row in rows]

    def count_tag_metrics(self, run_id: str) -> int:
        with self._engine.begin() as conn:
            total = conn.execute(
                select(func.count()).select_from(run_tag_metrics_table).where(run_tag_metrics_table.c.run_id == run_id)
            ).scalar_one()
        return int(total)

    def replace_drift_alerts(self, run_id: str, alerts: list[DriftAlertRecord]) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(run_drift_alerts_table).where(run_drift_alerts_table.c.run_id == run_id))
            if alerts:
                conn.execute(insert(run_drift_alerts_table), [alert.model_dump() for alert in alerts])

    def list_drift_alerts(self, run_id: str) -> list[DriftAlertRecord]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(run_drift_alerts_table)
                .where(run_drift_alerts_table.c.run_id == run_id)
                .order_by(run_drift_alerts_table.c.created_at.desc())
            ).mappings().all()
        return [DriftAlertRecord.model_validate(dict(row)) for row in rows]

    def list_drift_alerts_for_dataset(self, dataset_name: str, dataset_version: str) -> list[DriftAlertRecord]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(run_drift_alerts_table)
                .where(
                    (run_drift_alerts_table.c.dataset_name == dataset_name)
                    & (run_drift_alerts_table.c.dataset_version == dataset_version)
                )
                .order_by(run_drift_alerts_table.c.created_at.desc())
            ).mappings().all()
        return [DriftAlertRecord.model_validate(dict(row)) for row in rows]

    def list_drift_alerts_for_dataset_paginated(
        self,
        *,
        dataset_name: str,
        dataset_version: str,
        limit: int,
        offset: int,
        severity: str | None = None,
        metric_contains: str | None = None,
    ) -> list[DriftAlertRecord]:
        stmt = select(run_drift_alerts_table).where(
            (run_drift_alerts_table.c.dataset_name == dataset_name)
            & (run_drift_alerts_table.c.dataset_version == dataset_version)
        )
        if severity:
            stmt = stmt.where(run_drift_alerts_table.c.severity == severity)
        if metric_contains:
            stmt = stmt.where(run_drift_alerts_table.c.metric.like(f"%{metric_contains}%"))
        stmt = stmt.order_by(run_drift_alerts_table.c.created_at.desc()).limit(limit).offset(offset)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [DriftAlertRecord.model_validate(dict(row)) for row in rows]

    def count_drift_alerts_for_dataset(
        self,
        *,
        dataset_name: str,
        dataset_version: str,
        severity: str | None = None,
        metric_contains: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(run_drift_alerts_table).where(
            (run_drift_alerts_table.c.dataset_name == dataset_name)
            & (run_drift_alerts_table.c.dataset_version == dataset_version)
        )
        if severity:
            stmt = stmt.where(run_drift_alerts_table.c.severity == severity)
        if metric_contains:
            stmt = stmt.where(run_drift_alerts_table.c.metric.like(f"%{metric_contains}%"))
        with self._engine.begin() as conn:
            total = conn.execute(stmt).scalar_one()
        return int(total)
