from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DatasetItem(BaseModel):
    item_id: str
    prompt: str
    expected_answer: str | None = None
    keywords: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetRecord(BaseModel):
    dataset_name: str
    version: str
    path: str
    checksum: str
    item_count: int
    created_at: datetime


class VariantConfig(BaseModel):
    name: str
    dataset_name: str
    dataset_version: str
    model_name: str
    prompt_version: str
    prompt_template: str = "{prompt}"
    retrieval_enabled: bool = False
    llm_judge_enabled: bool = False
    llm_judge_model: str | None = None
    seed: int = 42
    temperature: float = 0.0


class GateConfig(BaseModel):
    baseline_run_id: str | None = None
    min_metric: dict[str, float] = Field(default_factory=dict)
    max_drop_from_baseline: dict[str, float] = Field(default_factory=dict)


class EvalRunConfig(BaseModel):
    variant: VariantConfig
    gates: GateConfig = Field(default_factory=GateConfig)


class ItemScore(BaseModel):
    exact_match: float
    keyword_coverage: float
    schema_valid: float
    llm_judge_score: float | None = None


class ItemResult(BaseModel):
    run_id: str
    item_id: str
    prompt: str
    output_text: str
    expected_answer: str | None = None
    keywords: list[str] = Field(default_factory=list)
    error: str | None = None
    latency_ms: float | None = None
    token_in_est: int | None = None
    token_out_est: int | None = None
    schema_error: str | None = None
    keyword_misses: list[str] = Field(default_factory=list)
    scores: ItemScore
    tags: dict[str, str] = Field(default_factory=dict)


class AggregateMetrics(BaseModel):
    exact_match: float
    keyword_coverage: float
    schema_valid: float
    llm_judge_score: float | None = None
    sample_count: int


class GateDecision(BaseModel):
    status: Literal["pass", "fail"]
    reasons: list[str] = Field(default_factory=list)
    checks: dict[str, dict[str, float | bool]] = Field(default_factory=dict)


class RunRecord(BaseModel):
    run_id: str
    run_key: str
    run_version: int
    variant_name: str
    dataset_name: str
    dataset_version: str
    model_name: str
    prompt_version: str
    retrieval_enabled: bool
    llm_judge_enabled: bool
    seed: int
    temperature: float
    dataset_fingerprint: str
    prompt_fingerprint: str
    config_fingerprint: str
    experiment_signature: str
    release_status: Literal["APPROVED", "DRIFT_WARNING", "BLOCKED"] = "BLOCKED"
    status: Literal["running", "completed", "failed"]
    duration_ms: float | None = None
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    token_in_est: int = 0
    token_out_est: int = 0
    cost_est_usd: float = 0.0
    started_at: datetime
    completed_at: datetime | None = None
    aggregate_metrics: AggregateMetrics | None = None
    gate_decision: GateDecision | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareResult(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    baseline_metrics: AggregateMetrics
    candidate_metrics: AggregateMetrics
    deltas: dict[str, float]
    gate_decision: GateDecision
    threshold_overlay: dict[str, dict[str, float | bool]] = Field(default_factory=dict)


class TagMetricRecord(BaseModel):
    run_id: str
    tag_key: str
    tag_value: str
    exact_match: float
    keyword_coverage: float
    schema_valid: float
    llm_judge_score: float | None = None
    sample_count: int


class DriftSummary(BaseModel):
    run_id: str
    dataset_name: str
    dataset_version: str
    trends: dict[str, list[float]]
    volatility: dict[str, float]
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class DriftAlertRecord(BaseModel):
    run_id: str
    dataset_name: str
    dataset_version: str
    scope: str
    metric: str | None = None
    severity: str
    delta: float | None = None
    threshold: float | None = None
    message: str
    created_at: datetime


class FailureSample(BaseModel):
    item_id: str
    severity: float
    expected_answer: str | None
    output_text: str
    error: str | None
    schema_error: str | None
    keyword_misses: list[str]
    scores: ItemScore
    tags: dict[str, str] = Field(default_factory=dict)
