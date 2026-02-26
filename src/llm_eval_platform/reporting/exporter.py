from __future__ import annotations

from pathlib import Path

from llm_eval_platform.domain.models import CompareResult, RunRecord
from llm_eval_platform.runner.experiment import metrics_snapshot_payload, per_tag_breakdown, serialize_json
from llm_eval_platform.storage.repository import EvalRepository


def build_markdown_report(
    *,
    run: RunRecord,
    compare: CompareResult | None,
    tag_breakdown: dict[str, dict[str, float]],
    drift_alerts: list[dict] | None = None,
    dataset_alert_timeline: list[dict] | None = None,
) -> str:
    agg = run.aggregate_metrics
    if agg is None:
        raise ValueError(f"Run {run.run_id} has no aggregate metrics.")
    lines = [
        f"# LLM Eval Report: {run.run_id}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| exact_match | {agg.exact_match:.4f} |",
        f"| keyword_coverage | {agg.keyword_coverage:.4f} |",
        f"| schema_valid | {agg.schema_valid:.4f} |",
    ]
    if agg.llm_judge_score is not None:
        lines.append(f"| llm_judge_score | {agg.llm_judge_score:.4f} |")

    if run.gate_decision:
        lines.extend(
            [
                "",
                "## Gate Status",
                "",
                f"- status: **{run.gate_decision.status.upper()}**",
            ]
        )
        if run.gate_decision.reasons:
            lines.append("- reasons:")
            for reason in run.gate_decision.reasons:
                lines.append(f"  - {reason}")

    degraded_slices = _degraded_slices(tag_breakdown)

    if compare:
        lines.extend(
            [
                "",
                "## Baseline Comparison",
                "",
                "| Metric | Delta (candidate - baseline) |",
                "|---|---:|",
            ]
        )
        for metric, delta in compare.deltas.items():
            lines.append(f"| {metric} | {delta:.4f} |")
        if compare.threshold_overlay:
            lines.extend(
                [
                    "",
                    "### Threshold Overlay",
                    "",
                    "| Metric | Delta | Allowed Drop | Actual Drop | Breach | Passed |",
                    "|---|---:|---:|---:|---:|---|",
                ]
            )
            for metric, row in compare.threshold_overlay.items():
                lines.append(
                    f"| {metric} | {row.get('delta', 0):.4f} | {row.get('allowed_drop', 0):.4f} | "
                    f"{row.get('actual_drop', 0):.4f} | {row.get('breach', 0):.4f} | {row.get('passed', False)} |"
                )

    if degraded_slices:
        lines.extend(
            [
                "",
                "## Top Degraded Slices",
                "",
                "| Slice | Degradation Score | exact_match | keyword_coverage | schema_valid |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in degraded_slices[:10]:
            lines.append(
                f"| {row['slice']} | {row['degradation_score']:.4f} | {row['exact_match']:.4f} | "
                f"{row['keyword_coverage']:.4f} | {row['schema_valid']:.4f} |"
            )

    if drift_alerts:
        lines.extend(["", "## Drift Alerts", ""])
        for alert in drift_alerts:
            lines.append(f"- [{alert.get('severity', 'warning')}] {alert.get('message', '')}")

    if dataset_alert_timeline:
        lines.extend(["", "## Alert Timeline", ""])
        for alert in dataset_alert_timeline[:20]:
            created = str(alert.get("created_at", ""))[:19].replace("T", " ")
            lines.append(
                f"- {created} | {alert.get('severity', '')} | {alert.get('metric', 'global')} | {alert.get('message', '')}"
            )

    lines.extend(["", "## Per-Tag Breakdown", "", "| Tag | exact_match | keyword_coverage | schema_valid |", "|---|---:|---:|---:|"])
    for tag, metrics in sorted(tag_breakdown.items()):
        lines.append(
            f"| {tag} | {metrics.get('exact_match', 0.0):.4f} | "
            f"{metrics.get('keyword_coverage', 0.0):.4f} | {metrics.get('schema_valid', 0.0):.4f} |"
        )
    return "\n".join(lines)


def export_reports(
    *,
    repository: EvalRepository,
    run_id: str,
    output_dir: Path,
    compare: CompareResult | None = None,
) -> dict[str, str]:
    run = repository.get_run(run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found.")
    item_results = repository.list_item_results(run_id)
    tags = per_tag_breakdown(item_results)
    run_alerts = [row.model_dump(mode="json") for row in repository.list_drift_alerts(run_id)]
    dataset_alert_timeline = [
        row.model_dump(mode="json")
        for row in repository.list_drift_alerts_for_dataset(run.dataset_name, run.dataset_version)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)

    report_json = {
        "run": run.model_dump(mode="json"),
        "compare": compare.model_dump(mode="json") if compare else None,
        "tag_breakdown": tags,
        "degraded_slices": _degraded_slices(tags),
        "drift_alerts": run_alerts,
        "dataset_alert_timeline": dataset_alert_timeline,
    }
    deltas = compare.deltas if compare else None
    gate = compare.gate_decision if compare else run.gate_decision
    snapshot = metrics_snapshot_payload(run=run, deltas=deltas, gate=gate)

    md_path = output_dir / f"{run_id}.report.md"
    json_path = output_dir / f"{run_id}.report.json"
    snapshot_path = output_dir / f"{run_id}.metrics_snapshot.json"
    md_path.write_text(
        build_markdown_report(
            run=run,
            compare=compare,
            tag_breakdown=tags,
            drift_alerts=run_alerts,
            dataset_alert_timeline=dataset_alert_timeline,
        ),
        encoding="utf-8",
    )
    json_path.write_text(serialize_json(report_json), encoding="utf-8")
    snapshot_path.write_text(serialize_json(snapshot), encoding="utf-8")

    return {
        "markdown_report": str(md_path),
        "json_report": str(json_path),
        "metrics_snapshot": str(snapshot_path),
    }


def _degraded_slices(tag_breakdown: dict[str, dict[str, float]]) -> list[dict]:
    rows: list[dict] = []
    for tag, metrics in tag_breakdown.items():
        exact_match = float(metrics.get("exact_match", 0.0))
        keyword_coverage = float(metrics.get("keyword_coverage", 0.0))
        schema_valid = float(metrics.get("schema_valid", 0.0))
        score = (1 - exact_match) * 0.4 + (1 - keyword_coverage) * 0.4 + (1 - schema_valid) * 0.2
        rows.append(
            {
                "slice": tag,
                "degradation_score": score,
                "exact_match": exact_match,
                "keyword_coverage": keyword_coverage,
                "schema_valid": schema_valid,
            }
        )
    rows.sort(key=lambda row: row["degradation_score"], reverse=True)
    return rows
