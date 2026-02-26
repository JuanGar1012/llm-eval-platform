from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from llm_eval_platform.domain.models import (
    AggregateMetrics,
    FailureSample,
    GateDecision,
    ItemResult,
    RunRecord,
    TagMetricRecord,
)


def compute_release_status(gate_decision: GateDecision, drift_alerts: list[dict[str, Any]]) -> str:
    if gate_decision.status == "fail":
        return "BLOCKED"
    if drift_alerts:
        return "DRIFT_WARNING"
    return "APPROVED"


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(math.ceil(0.95 * len(ordered))) - 1
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def build_tag_metrics(run_id: str, results: list[ItemResult]) -> list[TagMetricRecord]:
    grouped: dict[tuple[str, str], list[ItemResult]] = defaultdict(list)
    for result in results:
        for k, v in result.tags.items():
            grouped[(k, v)].append(result)
    output: list[TagMetricRecord] = []
    for (tag_key, tag_value), rows in grouped.items():
        output.append(
            TagMetricRecord(
                run_id=run_id,
                tag_key=tag_key,
                tag_value=tag_value,
                exact_match=mean(row.scores.exact_match for row in rows),
                keyword_coverage=mean(row.scores.keyword_coverage for row in rows),
                schema_valid=mean(row.scores.schema_valid for row in rows),
                llm_judge_score=(
                    mean(row.scores.llm_judge_score for row in rows if row.scores.llm_judge_score is not None)
                    if any(row.scores.llm_judge_score is not None for row in rows)
                    else None
                ),
                sample_count=len(rows),
            )
        )
    return output


def summarize_trends(runs: list[RunRecord]) -> tuple[dict[str, list[float]], dict[str, float]]:
    metrics = ["exact_match", "keyword_coverage", "schema_valid"]
    trends: dict[str, list[float]] = {name: [] for name in metrics}
    for run in runs:
        if not run.aggregate_metrics:
            continue
        for metric in metrics:
            trends[metric].append(float(getattr(run.aggregate_metrics, metric)))
    volatility: dict[str, float] = {}
    for metric, values in trends.items():
        volatility[metric] = pstdev(values) if len(values) >= 2 else 0.0
    return trends, volatility


def build_drift_alerts(
    *,
    baseline: AggregateMetrics | None,
    candidate: AggregateMetrics,
    volatility: dict[str, float],
    max_drop_from_baseline: dict[str, float],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for metric, threshold in max_drop_from_baseline.items():
        if baseline is None:
            continue
        base = float(getattr(baseline, metric))
        cand = float(getattr(candidate, metric))
        drop = base - cand
        if drop > threshold:
            alerts.append(
                {
                    "scope": "global",
                    "metric": metric,
                    "severity": "critical",
                    "delta": -drop,
                    "threshold": -threshold,
                    "message": f"{metric} dropped by {drop:.4f}, allowed {threshold:.4f}",
                }
            )
        elif drop > threshold * 0.7:
            alerts.append(
                {
                    "scope": "global",
                    "metric": metric,
                    "severity": "warning",
                    "delta": -drop,
                    "threshold": -threshold,
                    "message": f"{metric} nearing threshold with drop {drop:.4f}",
                }
            )
    for metric, std in volatility.items():
        if std > 0.15:
            alerts.append(
                {
                    "scope": "global",
                    "metric": metric,
                    "severity": "warning",
                    "message": f"High volatility for {metric}: std={std:.4f}",
                }
            )
    return alerts


def worst_failures(results: list[ItemResult], limit: int = 10) -> list[FailureSample]:
    ranked: list[FailureSample] = []
    for row in results:
        severity = 0.0
        if row.error:
            severity += 4.0
        if row.schema_error:
            severity += 3.0
        severity += (1.0 - row.scores.exact_match) * 2.0
        severity += (1.0 - row.scores.keyword_coverage) * 2.0
        severity += (1.0 - row.scores.schema_valid) * 3.0
        ranked.append(
            FailureSample(
                item_id=row.item_id,
                severity=severity,
                expected_answer=row.expected_answer,
                output_text=row.output_text,
                error=row.error,
                schema_error=row.schema_error,
                keyword_misses=row.keyword_misses,
                scores=row.scores,
                tags=row.tags,
            )
        )
    ranked.sort(key=lambda row: row.severity, reverse=True)
    return ranked[:limit]


def cluster_failures(results: list[ItemResult]) -> dict[str, list[dict[str, Any]]]:
    schema_groups: dict[str, int] = defaultdict(int)
    keyword_groups: dict[str, int] = defaultdict(int)
    for row in results:
        if row.schema_error:
            schema_groups[row.schema_error] += 1
        for miss in row.keyword_misses:
            keyword_groups[miss] += 1
    return {
        "schema_violations": [
            {"error": key, "count": value} for key, value in sorted(schema_groups.items(), key=lambda x: x[1], reverse=True)
        ],
        "keyword_misses": [
            {"keyword": key, "count": value} for key, value in sorted(keyword_groups.items(), key=lambda x: x[1], reverse=True)
        ],
    }


def build_threshold_overlay(
    *,
    deltas: dict[str, float],
    allowed_drops: dict[str, float],
) -> dict[str, dict[str, float | bool]]:
    overlay: dict[str, dict[str, float | bool]] = {}
    for metric, delta in deltas.items():
        allowed_drop = float(allowed_drops.get(metric, 0.0))
        actual_drop = max(0.0, -float(delta))
        breach = max(0.0, actual_drop - allowed_drop)
        overlay[metric] = {
            "delta": float(delta),
            "allowed_drop": allowed_drop,
            "actual_drop": actual_drop,
            "breach": breach,
            "passed": breach == 0.0,
        }
    return overlay
