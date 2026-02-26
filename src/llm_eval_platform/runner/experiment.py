from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import ValidationError, validate

from llm_eval_platform.analysis import (
    build_drift_alerts,
    build_tag_metrics,
    compute_release_status,
    p95,
    summarize_trends,
)
from llm_eval_platform.config import build_fingerprints, build_run_key
from llm_eval_platform.domain.models import (
    AggregateMetrics,
    DriftAlertRecord,
    EvalRunConfig,
    GateDecision,
    ItemResult,
    RunRecord,
)
from llm_eval_platform.ingestion.registry import load_jsonl_dataset
from llm_eval_platform.runner.ollama_client import OllamaClient
from llm_eval_platform.runner.retrieval import build_retrieval_context
from llm_eval_platform.scoring.gates import evaluate_gates
from llm_eval_platform.scoring.metrics import aggregate_scores, llm_judge_from_text, score_item
from llm_eval_platform.storage.repository import EvalRepository


logger = logging.getLogger(__name__)
_TOKEN_ENCODINGS: dict[str, object] = {}


class ExperimentRunner:
    def __init__(self, repository: EvalRepository, ollama_client: OllamaClient) -> None:
        self._repository = repository
        self._ollama_client = ollama_client

    def list_local_models(self) -> list[str]:
        return self._ollama_client.list_models()

    def run(self, config: EvalRunConfig) -> RunRecord:
        dataset_record = self._repository.get_dataset(
            dataset_name=config.variant.dataset_name,
            version=config.variant.dataset_version,
        )
        if dataset_record is None:
            raise ValueError(
                f"Dataset {config.variant.dataset_name}:{config.variant.dataset_version} not registered."
            )
        items = load_jsonl_dataset(path=Path(dataset_record.path))
        fingerprints = build_fingerprints(
            dataset_name=config.variant.dataset_name,
            dataset_version=config.variant.dataset_version,
            dataset_checksum=dataset_record.checksum,
            prompt_version=config.variant.prompt_version,
            prompt_template=config.variant.prompt_template,
            model_name=config.variant.model_name,
            retrieval_enabled=config.variant.retrieval_enabled,
            llm_judge_enabled=config.variant.llm_judge_enabled,
            llm_judge_model=config.variant.llm_judge_model,
            temperature=config.variant.temperature,
            seed=config.variant.seed,
        )
        run_key = build_run_key(
            dataset_name=config.variant.dataset_name,
            dataset_version=config.variant.dataset_version,
            prompt_version=config.variant.prompt_version,
            model_name=config.variant.model_name,
            retrieval_enabled=config.variant.retrieval_enabled,
            llm_judge_enabled=config.variant.llm_judge_enabled,
            seed=config.variant.seed,
        )
        run_version = self._repository.next_run_version(run_key)
        run_id = f"{run_key}-v{run_version}"
        run_record = RunRecord(
            run_id=run_id,
            run_key=run_key,
            run_version=run_version,
            variant_name=config.variant.name,
            dataset_name=config.variant.dataset_name,
            dataset_version=config.variant.dataset_version,
            model_name=config.variant.model_name,
            prompt_version=config.variant.prompt_version,
            retrieval_enabled=config.variant.retrieval_enabled,
            llm_judge_enabled=config.variant.llm_judge_enabled,
            seed=config.variant.seed,
            temperature=config.variant.temperature,
            dataset_fingerprint=fingerprints["dataset_fingerprint"],
            prompt_fingerprint=fingerprints["prompt_fingerprint"],
            config_fingerprint=fingerprints["config_fingerprint"],
            experiment_signature=fingerprints["experiment_signature"],
            status="running",
            started_at=datetime.now(tz=timezone.utc),
        )
        self._repository.create_run(run_record)

        results: list[ItemResult] = []
        started_perf = time.perf_counter()
        try:
            for item in items:
                rendered_prompt = config.variant.prompt_template.replace("{prompt}", item.prompt)
                if config.variant.retrieval_enabled:
                    rendered_prompt = f"{build_retrieval_context(item)}\n\n{rendered_prompt}"

                output_text = ""
                error: str | None = None
                judge_score: float | None = None
                schema_error: str | None = None
                latency_ms: float | None = None
                t0 = time.perf_counter()
                try:
                    output_text = self._ollama_client.generate(
                        model=config.variant.model_name,
                        prompt=rendered_prompt,
                        temperature=config.variant.temperature,
                    )
                    if config.variant.llm_judge_enabled and config.variant.llm_judge_model:
                        judge_prompt = (
                            "Score this response from 0 to 1.\n"
                            f"Prompt: {item.prompt}\n"
                            f"Response: {output_text}\n"
                            "Return only a numeric score."
                        )
                        judge_output = self._ollama_client.generate(
                            model=config.variant.llm_judge_model,
                            prompt=judge_prompt,
                            temperature=0.0,
                        )
                        judge_score = llm_judge_from_text(judge_output)
                except Exception as exc:
                    error = str(exc)
                    logger.exception("Error generating output for item_id=%s", item.item_id)
                finally:
                    latency_ms = (time.perf_counter() - t0) * 1000.0

                scores = score_item(item=item, output_text=output_text, llm_judge_score=judge_score)
                if item.output_schema is not None:
                    schema_error = _schema_error_message(item.output_schema, output_text)
                keyword_misses = [
                    keyword for keyword in item.keywords if keyword.lower() not in output_text.lower()
                ]
                results.append(
                    ItemResult(
                        run_id=run_id,
                        item_id=item.item_id,
                        prompt=rendered_prompt,
                        output_text=output_text,
                        expected_answer=item.expected_answer,
                        keywords=item.keywords,
                        error=error,
                        latency_ms=latency_ms,
                        token_in_est=_estimate_tokens(rendered_prompt, model_name=config.variant.model_name),
                        token_out_est=_estimate_tokens(output_text, model_name=config.variant.model_name),
                        schema_error=schema_error,
                        keyword_misses=keyword_misses,
                        scores=scores,
                        tags=item.tags,
                    )
                )

            self._repository.insert_item_results(results)
            aggregate = aggregate_scores([item.scores for item in results])
            baseline_metrics = _load_baseline_metrics(self._repository, config.gates.baseline_run_id)
            gate_decision = evaluate_gates(
                candidate=aggregate,
                baseline=baseline_metrics,
                gate_config=config.gates,
            )
            tag_metrics = build_tag_metrics(run_id=run_id, results=results)
            self._repository.replace_tag_metrics(run_id, tag_metrics)
            historical_runs = self._repository.list_runs_by_dataset(
                config.variant.dataset_name, config.variant.dataset_version
            )
            trends, volatility = summarize_trends(historical_runs + [run_record.model_copy(update={"aggregate_metrics": aggregate})])
            drift_alerts = build_drift_alerts(
                baseline=baseline_metrics,
                candidate=aggregate,
                volatility=volatility,
                max_drop_from_baseline=config.gates.max_drop_from_baseline,
            )
            drift_records = [
                DriftAlertRecord(
                    run_id=run_id,
                    dataset_name=config.variant.dataset_name,
                    dataset_version=config.variant.dataset_version,
                    scope=str(alert.get("scope", "global")),
                    metric=alert.get("metric"),
                    severity=str(alert.get("severity", "warning")),
                    delta=alert.get("delta"),
                    threshold=alert.get("threshold"),
                    message=str(alert.get("message", "")),
                    created_at=datetime.now(tz=timezone.utc),
                )
                for alert in drift_alerts
            ]
            self._repository.replace_drift_alerts(run_id, drift_records)
            release_status = compute_release_status(gate_decision, drift_alerts)
            duration_ms = (time.perf_counter() - started_perf) * 1000.0
            latencies = [row.latency_ms for row in results if row.latency_ms is not None]
            avg_latency_ms = sum(latencies) / len(latencies) if latencies else None
            p95_latency_ms = p95([float(v) for v in latencies]) if latencies else None
            token_in_est = sum(row.token_in_est or 0 for row in results)
            token_out_est = sum(row.token_out_est or 0 for row in results)
            self._repository.update_run_status(
                run_id=run_id,
                status="completed",
                aggregate_metrics=aggregate,
                gate_decision=gate_decision,
                release_status=release_status,
                duration_ms=duration_ms,
                avg_latency_ms=avg_latency_ms,
                p95_latency_ms=p95_latency_ms,
                token_in_est=token_in_est,
                token_out_est=token_out_est,
                cost_est_usd=0.0,
                metadata={
                    "errors": sum(1 for result in results if result.error),
                    "drift_alerts": drift_alerts,
                    "trends": trends,
                    "volatility": volatility,
                },
            )
            updated = self._repository.get_run(run_id)
            if updated is None:
                raise RuntimeError(f"Run {run_id} missing after completion.")
            return updated
        except Exception:
            self._repository.update_run_status(run_id=run_id, status="failed")
            raise


def _load_baseline_metrics(repository: EvalRepository, baseline_run_id: str | None) -> AggregateMetrics | None:
    if baseline_run_id is None:
        return None
    baseline = repository.get_run(baseline_run_id)
    if baseline is None or baseline.aggregate_metrics is None:
        raise ValueError(f"Baseline run {baseline_run_id} not found or has no metrics.")
    return baseline.aggregate_metrics


def compute_metric_deltas(candidate: AggregateMetrics, baseline: AggregateMetrics) -> dict[str, float]:
    deltas: dict[str, float] = {
        "exact_match": candidate.exact_match - baseline.exact_match,
        "keyword_coverage": candidate.keyword_coverage - baseline.keyword_coverage,
        "schema_valid": candidate.schema_valid - baseline.schema_valid,
    }
    if candidate.llm_judge_score is not None and baseline.llm_judge_score is not None:
        deltas["llm_judge_score"] = candidate.llm_judge_score - baseline.llm_judge_score
    return deltas


def per_tag_breakdown(results: list[ItemResult]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = {}
    for result in results:
        for tag_name, tag_value in result.tags.items():
            key = f"{tag_name}:{tag_value}"
            grouped.setdefault(
                key,
                {"exact_match": [], "keyword_coverage": [], "schema_valid": [], "llm_judge_score": []},
            )
            grouped[key]["exact_match"].append(result.scores.exact_match)
            grouped[key]["keyword_coverage"].append(result.scores.keyword_coverage)
            grouped[key]["schema_valid"].append(result.scores.schema_valid)
            if result.scores.llm_judge_score is not None:
                grouped[key]["llm_judge_score"].append(result.scores.llm_judge_score)
    output: dict[str, dict[str, float]] = {}
    for key, metrics in grouped.items():
        breakdown = {
            "exact_match": sum(metrics["exact_match"]) / len(metrics["exact_match"]),
            "keyword_coverage": sum(metrics["keyword_coverage"]) / len(metrics["keyword_coverage"]),
            "schema_valid": sum(metrics["schema_valid"]) / len(metrics["schema_valid"]),
        }
        if metrics["llm_judge_score"]:
            breakdown["llm_judge_score"] = sum(metrics["llm_judge_score"]) / len(metrics["llm_judge_score"])
        output[key] = breakdown
    return output


def metrics_snapshot_payload(
    *,
    run: RunRecord,
    deltas: dict[str, float] | None,
    gate: GateDecision | None,
) -> dict:
    return {
        "run_id": run.run_id,
        "variant_name": run.variant_name,
        "dataset": f"{run.dataset_name}:{run.dataset_version}",
        "model_name": run.model_name,
        "prompt_version": run.prompt_version,
        "retrieval_enabled": run.retrieval_enabled,
        "llm_judge_enabled": run.llm_judge_enabled,
        "experiment_signature": run.experiment_signature,
        "release_status": run.release_status,
        "status": run.status,
        "duration_ms": run.duration_ms,
        "avg_latency_ms": run.avg_latency_ms,
        "p95_latency_ms": run.p95_latency_ms,
        "token_in_est": run.token_in_est,
        "token_out_est": run.token_out_est,
        "cost_est_usd": run.cost_est_usd,
        "metrics": run.aggregate_metrics.model_dump() if run.aggregate_metrics else {},
        "deltas_vs_baseline": deltas or {},
        "gate_status": gate.status if gate else "n/a",
        "gate_reasons": gate.reasons if gate else [],
    }


def serialize_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def _estimate_tokens(text_value: str, model_name: str | None = None) -> int:
    # Prefer real tokenization when tiktoken is available; fallback keeps local-only behavior deterministic.
    try:
        import tiktoken  # type: ignore

        key = model_name or "cl100k_base"
        encoding = _TOKEN_ENCODINGS.get(key)
        if encoding is None:
            try:
                encoding = tiktoken.encoding_for_model(model_name) if model_name else None
            except Exception:
                encoding = None
            if encoding is None:
                encoding = tiktoken.get_encoding("cl100k_base")
            _TOKEN_ENCODINGS[key] = encoding
        return len(encoding.encode(text_value))  # type: ignore[attr-defined]
    except Exception:
        return max(0, len(text_value) // 4)


def _schema_error_message(schema: dict, output_text: str) -> str | None:
    try:
        parsed = json.loads(output_text)
        validate(instance=parsed, schema=schema)
        return None
    except (json.JSONDecodeError, ValidationError) as exc:
        return str(exc)
