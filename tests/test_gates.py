from llm_eval_platform.domain.models import AggregateMetrics, GateConfig
from llm_eval_platform.scoring.gates import evaluate_gates


def test_gate_min_metric_pass() -> None:
    candidate = AggregateMetrics(
        exact_match=0.6,
        keyword_coverage=0.7,
        schema_valid=1.0,
        llm_judge_score=None,
        sample_count=10,
    )
    gate = GateConfig(min_metric={"exact_match": 0.5})
    decision = evaluate_gates(candidate=candidate, gate_config=gate)
    assert decision.status == "pass"


def test_gate_drop_fail() -> None:
    baseline = AggregateMetrics(
        exact_match=0.8,
        keyword_coverage=0.8,
        schema_valid=1.0,
        llm_judge_score=None,
        sample_count=10,
    )
    candidate = AggregateMetrics(
        exact_match=0.6,
        keyword_coverage=0.7,
        schema_valid=1.0,
        llm_judge_score=None,
        sample_count=10,
    )
    gate = GateConfig(max_drop_from_baseline={"exact_match": 0.1})
    decision = evaluate_gates(candidate=candidate, baseline=baseline, gate_config=gate)
    assert decision.status == "fail"
    assert decision.reasons

