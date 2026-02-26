import json
from pathlib import Path
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from llm_eval_platform.api import create_app
from llm_eval_platform.config import AppConfig
from llm_eval_platform.domain.models import AggregateMetrics, ItemResult, ItemScore, RunRecord
from llm_eval_platform.service import EvalService


def _make_client(tmp_path: Path) -> TestClient:
    config = AppConfig(
        db_path=tmp_path / "test.db",
        report_dir=tmp_path / "reports",
        ollama_url="http://localhost:11434",
    )
    app = create_app(EvalService(config))
    return TestClient(app)


def test_health_includes_schema_version(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["schema_version"], int)


def test_ui_page_loads(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    response = client.get("/ui")
    assert response.status_code == 200
    assert "LLM Eval Control Panel" in response.text
    nested = client.get("/ui/runs/sample-run")
    assert nested.status_code == 200


def test_local_models_endpoint_shape(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    response = client.get("/models/local")
    assert response.status_code == 200
    payload = response.json()
    assert "models" in payload
    assert isinstance(payload["models"], list)


def test_register_dataset_and_missing_run(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    dataset = tmp_path / "mini.jsonl"
    dataset.write_text(
        '{"item_id":"1","prompt":"hello","expected_answer":"hello","keywords":["hello"],'
        '"tags":{"domain":"general","difficulty":"easy","safety":"low","format":"text"}}\n',
        encoding="utf-8",
    )
    register = client.post(
        "/datasets/register",
        json={"dataset_name": "mini", "version": "v1", "path": str(dataset)},
    )
    assert register.status_code == 200
    assert register.json()["dataset"]["item_count"] == 1

    missing_run = client.get("/runs/not-a-run-id")
    assert missing_run.status_code == 404


def _seed_completed_run(
    service: EvalService,
    *,
    run_id: str,
    metrics: AggregateMetrics,
    variant_name: str,
) -> None:
    service.repository.create_run(
        RunRecord(
            run_id=run_id,
            run_key=run_id.split("-")[0],
            run_version=1,
            variant_name=variant_name,
            dataset_name="mini",
            dataset_version="v1",
            model_name="local-model",
            prompt_version="p1",
            retrieval_enabled=False,
            llm_judge_enabled=False,
            seed=42,
            temperature=0.0,
            dataset_fingerprint="dfp",
            prompt_fingerprint="pfp",
            config_fingerprint="cfp",
            experiment_signature=f"sig-{run_id}",
            release_status="BLOCKED",
            status="running",
            started_at=datetime.now(tz=timezone.utc),
        )
    )
    service.repository.update_run_status(
        run_id=run_id,
        status="completed",
        aggregate_metrics=metrics,
    )


def test_compare_and_export_report(tmp_path: Path) -> None:
    config = AppConfig(
        db_path=tmp_path / "test.db",
        report_dir=tmp_path / "reports",
        ollama_url="http://localhost:11434",
    )
    service = EvalService(config)
    _seed_completed_run(
        service,
        run_id="baseline123-v1",
        variant_name="baseline",
        metrics=AggregateMetrics(
            exact_match=0.8,
            keyword_coverage=0.8,
            schema_valid=1.0,
            llm_judge_score=None,
            sample_count=2,
        ),
    )
    _seed_completed_run(
        service,
        run_id="candidate123-v1",
        variant_name="candidate",
        metrics=AggregateMetrics(
            exact_match=0.7,
            keyword_coverage=0.75,
            schema_valid=1.0,
            llm_judge_score=None,
            sample_count=2,
        ),
    )
    service.repository.insert_item_results(
        [
            ItemResult(
                run_id="candidate123-v1",
                item_id="1",
                prompt="p1",
                output_text="hello",
                scores=ItemScore(exact_match=1.0, keyword_coverage=1.0, schema_valid=1.0),
                tags={"domain": "general", "difficulty": "easy", "safety": "low", "format": "text"},
            ),
            ItemResult(
                run_id="candidate123-v1",
                item_id="2",
                prompt="p2",
                output_text="world",
                scores=ItemScore(exact_match=0.0, keyword_coverage=0.5, schema_valid=1.0),
                tags={"domain": "general", "difficulty": "hard", "safety": "medium", "format": "text"},
            ),
        ]
    )
    client = TestClient(create_app(service))

    compare = client.post(
        "/compare",
        json={
            "baseline_run_id": "baseline123-v1",
            "candidate_run_id": "candidate123-v1",
            "gate_config": {"max_drop_from_baseline": {"exact_match": 0.2}},
        },
    )
    assert compare.status_code == 200
    compare_payload = compare.json()["compare"]
    assert "deltas" in compare_payload
    assert compare_payload["gate_decision"]["status"] == "pass"

    export = client.post(
        "/reports/export",
        json={
            "run_id": "candidate123-v1",
            "baseline_run_id": "baseline123-v1",
            "output_dir": str(tmp_path / "exports"),
        },
    )
    assert export.status_code == 200
    artifacts = export.json()["artifacts"]
    assert Path(artifacts["markdown_report"]).exists()
    assert Path(artifacts["json_report"]).exists()
    assert Path(artifacts["metrics_snapshot"]).exists()
    exported_json = json.loads(Path(artifacts["json_report"]).read_text(encoding="utf-8"))
    assert "drift_alerts" in exported_json
    assert "dataset_alert_timeline" in exported_json

    runs = client.get("/runs")
    assert runs.status_code == 200
    assert len(runs.json()["runs"]) >= 2

    trends = client.get("/runs/candidate123-v1/trends")
    assert trends.status_code == 200
    assert "drift" in trends.json()

    failures = client.get("/runs/candidate123-v1/failures?limit=1&offset=1")
    assert failures.status_code == 200
    failures_payload = failures.json()
    assert "worst_samples" in failures_payload
    assert failures_payload["limit"] == 1
    assert failures_payload["offset"] == 1
    assert "total" in failures_payload
    assert "has_more" in failures_payload

    release = client.get("/runs/candidate123-v1/release-decision")
    assert release.status_code == 200
    assert "release_status" in release.json()

    alerts = client.get("/runs/candidate123-v1/alerts")
    assert alerts.status_code == 200
    payload = alerts.json()
    assert "run_alerts" in payload
    assert "dataset_alert_timeline" in payload
