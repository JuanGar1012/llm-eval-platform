from __future__ import annotations

from llm_eval_platform.domain.models import AggregateMetrics, GateConfig, GateDecision


def _metric_value(metrics: AggregateMetrics, metric_name: str) -> float | None:
    value = getattr(metrics, metric_name, None)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evaluate_gates(
    *,
    candidate: AggregateMetrics,
    gate_config: GateConfig,
    baseline: AggregateMetrics | None = None,
) -> GateDecision:
    reasons: list[str] = []
    checks: dict[str, dict[str, float | bool]] = {}

    for metric_name, threshold in gate_config.min_metric.items():
        value = _metric_value(candidate, metric_name)
        if value is None:
            reasons.append(f"Metric {metric_name} missing in candidate.")
            checks[f"min_metric.{metric_name}"] = {"passed": False, "value": -1.0, "threshold": threshold}
            continue
        passed = value >= threshold
        checks[f"min_metric.{metric_name}"] = {"passed": passed, "value": value, "threshold": threshold}
        if not passed:
            reasons.append(f"{metric_name}={value:.4f} below minimum {threshold:.4f}.")

    for metric_name, max_drop in gate_config.max_drop_from_baseline.items():
        cand_value = _metric_value(candidate, metric_name)
        base_value = _metric_value(baseline, metric_name) if baseline else None
        if cand_value is None or base_value is None:
            reasons.append(f"Metric {metric_name} missing for baseline comparison.")
            checks[f"max_drop.{metric_name}"] = {"passed": False, "drop": 999.0, "max_drop": max_drop}
            continue
        drop = base_value - cand_value
        passed = drop <= max_drop
        checks[f"max_drop.{metric_name}"] = {"passed": passed, "drop": drop, "max_drop": max_drop}
        if not passed:
            reasons.append(
                f"{metric_name} dropped by {drop:.4f} (allowed {max_drop:.4f}) vs baseline."
            )

    status = "pass" if not reasons else "fail"
    return GateDecision(status=status, reasons=reasons, checks=checks)

