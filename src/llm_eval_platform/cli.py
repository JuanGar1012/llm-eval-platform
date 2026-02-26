from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from llm_eval_platform.config import AppConfig
from llm_eval_platform.domain.models import GateConfig
from llm_eval_platform.ingestion.registry import build_dataset_record, load_jsonl_dataset
from llm_eval_platform.logging import configure_logging
from llm_eval_platform.reporting.exporter import export_reports
from llm_eval_platform.service import EvalService


app = typer.Typer(no_args_is_help=True, help="Local-first LLM evaluation platform CLI.")


def _service(db_path: Optional[Path], report_dir: Optional[Path], ollama_url: Optional[str]) -> EvalService:
    defaults = AppConfig()
    config = AppConfig(
        db_path=db_path or defaults.db_path,
        report_dir=report_dir or defaults.report_dir,
        ollama_url=ollama_url or defaults.ollama_url,
    )
    configure_logging()
    return EvalService(config)


@app.command("register-dataset")
def register_dataset(
    dataset_name: str = typer.Option(..., "--dataset-name"),
    version: str = typer.Option(..., "--version"),
    path: Path = typer.Option(..., "--path"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    items = load_jsonl_dataset(path)
    record = build_dataset_record(dataset_name=dataset_name, version=version, path=path, items=items)
    service.repository.upsert_dataset(record)
    typer.echo(f"registered dataset {dataset_name}:{version} ({len(items)} items)")


@app.command("run-eval")
def run_eval(
    config_path: Path = typer.Option(..., "--config"),
    db_path: Path | None = typer.Option(None, "--db-path"),
    ollama_url: str | None = typer.Option(None, "--ollama-url"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=ollama_url)
    run = service.run_from_config(config_path)
    typer.echo(f"completed run {run.run_id} status={run.status}")
    if run.aggregate_metrics:
        typer.echo(json.dumps(run.aggregate_metrics.model_dump(), indent=2))
    if run.gate_decision:
        typer.echo(json.dumps(run.gate_decision.model_dump(), indent=2))


@app.command("compare-runs")
def compare_runs(
    baseline_run_id: str = typer.Option(..., "--baseline-run-id"),
    candidate_run_id: str = typer.Option(..., "--candidate-run-id"),
    gate_config_path: Path | None = typer.Option(None, "--gate-config"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    gate_config: GateConfig | None = None
    if gate_config_path:
        gate_config = service.load_gate_config_file(gate_config_path)
    result = service.compare_runs(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        gate_config=gate_config,
    )
    typer.echo(json.dumps(result.model_dump(), indent=2))


@app.command("export-report")
def export_report(
    run_id: str = typer.Option(..., "--run-id"),
    baseline_run_id: str | None = typer.Option(None, "--baseline-run-id"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=output_dir, ollama_url=None)
    compare = None
    if baseline_run_id:
        compare = service.compare_runs(
            baseline_run_id=baseline_run_id,
            candidate_run_id=run_id,
            gate_config=GateConfig(max_drop_from_baseline={}),
        )
    out_paths = export_reports(
        repository=service.repository,
        run_id=run_id,
        output_dir=output_dir or service.app_config.report_dir,
        compare=compare,
    )
    typer.echo(json.dumps(out_paths, indent=2))


@app.command("db-check")
def db_check(
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    typer.echo(
        json.dumps(
            {
                "db_path": str(service.app_config.db_path),
                "schema_version": service.schema_version(),
            },
            indent=2,
        )
    )


@app.command("run-trends")
def run_trends(
    run_id: str = typer.Option(..., "--run-id"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    payload = service.get_run_trends(run_id).model_dump(mode="json")
    typer.echo(json.dumps(payload, indent=2))


@app.command("run-failures")
def run_failures(
    run_id: str = typer.Option(..., "--run-id"),
    limit: int = typer.Option(10, "--limit"),
    offset: int = typer.Option(0, "--offset"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    payload = service.get_failure_analysis(run_id, limit=limit, offset=offset)
    typer.echo(json.dumps(payload, indent=2))


@app.command("run-release-decision")
def run_release_decision(
    run_id: str = typer.Option(..., "--run-id"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    run = service.repository.get_run(run_id)
    if run is None:
        raise typer.BadParameter(f"Run not found: {run_id}")
    payload = {
        "run_id": run_id,
        "release_status": run.release_status,
        "gate_decision": run.gate_decision.model_dump(mode="json") if run.gate_decision else None,
        "drift_alerts": [row.model_dump(mode="json") for row in service.repository.list_drift_alerts(run_id)],
    }
    typer.echo(json.dumps(payload, indent=2))


@app.command("run-alerts")
def run_alerts(
    run_id: str = typer.Option(..., "--run-id"),
    db_path: Path | None = typer.Option(None, "--db-path"),
) -> None:
    service = _service(db_path=db_path, report_dir=None, ollama_url=None)
    payload = service.get_alert_timeline(run_id)
    typer.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    app()
