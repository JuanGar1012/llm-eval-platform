from llm_eval_platform.domain.models import DatasetItem
from llm_eval_platform.scoring.metrics import (
    aggregate_scores,
    exact_match_score,
    keyword_coverage_score,
    schema_validity_score,
    score_item,
)


def test_exact_match_score() -> None:
    assert exact_match_score("Hello", "hello") == 1.0
    assert exact_match_score("Hello", "world") == 0.0


def test_keyword_coverage_score() -> None:
    assert keyword_coverage_score(["alpha", "beta"], "alpha only") == 0.5
    assert keyword_coverage_score([], "anything") == 1.0


def test_schema_validity_score() -> None:
    schema = {"type": "object", "required": ["status"], "properties": {"status": {"type": "string"}}}
    assert schema_validity_score(schema, '{"status":"ok"}') == 1.0
    assert schema_validity_score(schema, '{"wrong":"x"}') == 0.0


def test_aggregate_scores() -> None:
    item = DatasetItem(item_id="1", prompt="p", expected_answer="ok", keywords=["ok"], output_schema=None)
    scores = [score_item(item=item, output_text="ok"), score_item(item=item, output_text="bad")]
    aggregate = aggregate_scores(scores)
    assert aggregate.exact_match == 0.5
    assert aggregate.keyword_coverage == 0.5
    assert aggregate.sample_count == 2

