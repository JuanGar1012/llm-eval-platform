from llm_eval_platform.analysis import build_threshold_overlay


def test_threshold_overlay_pass_and_breach() -> None:
    overlay = build_threshold_overlay(
        deltas={"keyword_coverage": -0.04, "exact_match": -0.2, "schema_valid": 0.1},
        allowed_drops={"keyword_coverage": 0.05, "exact_match": 0.1, "schema_valid": 0.02},
    )
    assert overlay["keyword_coverage"]["passed"] is True
    assert overlay["keyword_coverage"]["breach"] == 0.0
    assert overlay["exact_match"]["passed"] is False
    assert abs(float(overlay["exact_match"]["breach"]) - 0.1) < 1e-9
    assert overlay["schema_valid"]["actual_drop"] == 0.0
