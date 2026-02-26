from __future__ import annotations

import json
from statistics import mean

from jsonschema import ValidationError, validate

from llm_eval_platform.domain.models import AggregateMetrics, DatasetItem, ItemScore


def exact_match_score(expected: str | None, output: str) -> float:
    if expected is None:
        return 0.0
    return 1.0 if expected.strip().lower() == output.strip().lower() else 0.0


def keyword_coverage_score(keywords: list[str], output: str) -> float:
    if not keywords:
        return 1.0
    output_lower = output.lower()
    matches = sum(1 for keyword in keywords if keyword.lower() in output_lower)
    return matches / len(keywords)


def schema_validity_score(schema: dict | None, output: str) -> float:
    if schema is None:
        return 1.0
    try:
        parsed = json.loads(output)
        validate(instance=parsed, schema=schema)
        return 1.0
    except (json.JSONDecodeError, ValidationError):
        return 0.0


def llm_judge_from_text(judge_output: str) -> float:
    cleaned = judge_output.strip()
    try:
        value = float(cleaned)
        return min(1.0, max(0.0, value))
    except ValueError:
        lower = cleaned.lower()
        if "pass" in lower or "good" in lower:
            return 1.0
        if "fail" in lower or "bad" in lower:
            return 0.0
        return 0.5


def score_item(
    *,
    item: DatasetItem,
    output_text: str,
    llm_judge_score: float | None = None,
) -> ItemScore:
    return ItemScore(
        exact_match=exact_match_score(item.expected_answer, output_text),
        keyword_coverage=keyword_coverage_score(item.keywords, output_text),
        schema_valid=schema_validity_score(item.output_schema, output_text),
        llm_judge_score=llm_judge_score,
    )


def aggregate_scores(scores: list[ItemScore]) -> AggregateMetrics:
    if not scores:
        raise ValueError("No scores were provided to aggregate.")
    judge_values = [score.llm_judge_score for score in scores if score.llm_judge_score is not None]
    return AggregateMetrics(
        exact_match=mean(score.exact_match for score in scores),
        keyword_coverage=mean(score.keyword_coverage for score in scores),
        schema_valid=mean(score.schema_valid for score in scores),
        llm_judge_score=mean(judge_values) if judge_values else None,
        sample_count=len(scores),
    )

