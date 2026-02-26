from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm_eval_platform.config import AppConfig
from llm_eval_platform.domain.models import EvalRunConfig, GateConfig
from llm_eval_platform.ingestion.registry import build_dataset_record, load_jsonl_dataset
from llm_eval_platform.reporting.exporter import export_reports
from llm_eval_platform.service import EvalService


class RegisterDatasetRequest(BaseModel):
    dataset_name: str
    version: str
    path: str


class CompareRequest(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    gate_config: GateConfig = GateConfig(max_drop_from_baseline={})


class ExportReportRequest(BaseModel):
    run_id: str
    baseline_run_id: str | None = None
    output_dir: str | None = None


class RunFromConfigRequest(BaseModel):
    config_path: str
    model_name: str | None = None
    seed: int | None = None
    temperature: float | None = None
    baseline_run_id: str | None = None


class ResetApplicationRequest(BaseModel):
    clear_reports: bool = True


def create_app(service: EvalService | None = None) -> FastAPI:
    app = FastAPI(title="LLM Eval Platform", version="0.1.0")
    app.state.service = service or EvalService(AppConfig())
    web_root = Path(__file__).resolve().parent / "web"
    app.mount("/ui/static", StaticFiles(directory=str(web_root / "static")), name="ui-static")

    def get_service() -> EvalService:
        return app.state.service

    @app.get("/health")
    def health(svc: EvalService = Depends(get_service)) -> dict:
        return {"status": "ok", "schema_version": svc.schema_version()}

    @app.get("/ui", response_class=HTMLResponse)
    def ui_index() -> FileResponse:
        return FileResponse(web_root / "templates" / "index.html")

    @app.get("/ui/{path:path}", response_class=HTMLResponse)
    def ui_path(path: str) -> FileResponse:
        return FileResponse(web_root / "templates" / "index.html")

    @app.get("/runs")
    def list_runs(svc: EvalService = Depends(get_service)) -> dict:
        runs = svc.repository.list_runs()
        return {"runs": [run.model_dump(mode="json") for run in runs]}

    @app.get("/models/local")
    def list_local_models(svc: EvalService = Depends(get_service)) -> dict:
        try:
            return {"models": svc.list_local_models(), "source": "ollama"}
        except Exception:
            return {"models": [], "source": "ollama", "warning": "Unable to reach Ollama model registry."}

    @app.post("/datasets/register")
    def register_dataset(
        request: RegisterDatasetRequest, svc: EvalService = Depends(get_service)
    ) -> dict:
        dataset_path = Path(request.path)
        if not dataset_path.exists():
            raise HTTPException(status_code=404, detail=f"Dataset path not found: {dataset_path}")
        items = load_jsonl_dataset(dataset_path)
        record = build_dataset_record(
            dataset_name=request.dataset_name,
            version=request.version,
            path=dataset_path,
            items=items,
        )
        svc.repository.upsert_dataset(record)
        return {"status": "ok", "dataset": record.model_dump()}

    @app.post("/runs")
    def run_eval(config: EvalRunConfig, svc: EvalService = Depends(get_service)) -> dict:
        try:
            run = svc.runner.run(config)
            return {"status": "ok", "run": run.model_dump(mode="json")}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/runs/from-config")
    def run_eval_from_config(
        request: RunFromConfigRequest, svc: EvalService = Depends(get_service)
    ) -> dict:
        try:
            run = svc.run_from_config(
                Path(request.config_path),
                model_name=request.model_name,
                seed=request.seed,
                temperature=request.temperature,
                baseline_run_id=request.baseline_run_id,
            )
            return {"status": "ok", "run": run.model_dump(mode="json")}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/admin/reset")
    def reset_application(
        request: ResetApplicationRequest, svc: EvalService = Depends(get_service)
    ) -> dict:
        try:
            return svc.reset_application_data(clear_reports=request.clear_reports)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, svc: EvalService = Depends(get_service)) -> dict:
        run = svc.repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return {"run": run.model_dump(mode="json")}

    @app.get("/runs/{run_id}/results")
    def get_results(run_id: str, svc: EvalService = Depends(get_service)) -> dict:
        run = svc.repository.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        items = svc.repository.list_item_results(run_id)
        return {"run_id": run_id, "items": [item.model_dump(mode="json") for item in items]}

    @app.get("/runs/{run_id}/tag-metrics")
    def get_tag_metrics(
        run_id: str,
        limit: int = 50,
        offset: int = 0,
        svc: EvalService = Depends(get_service),
    ) -> dict:
        try:
            return svc.get_tag_metrics_paginated(run_id, limit=limit, offset=offset)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/runs/{run_id}/trends")
    def get_run_trends(run_id: str, svc: EvalService = Depends(get_service)) -> dict:
        try:
            return {"drift": svc.get_run_trends(run_id).model_dump(mode="json")}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/runs/{run_id}/failures")
    def get_run_failures(
        run_id: str,
        limit: int = 10,
        offset: int = 0,
        svc: EvalService = Depends(get_service),
    ) -> dict:
        try:
            return svc.get_failure_analysis(run_id, limit=limit, offset=offset)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/runs/{run_id}/release-decision")
    def get_release_decision(run_id: str, svc: EvalService = Depends(get_service)) -> dict:
        run = svc.repository.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        persisted_alerts = [row.model_dump(mode="json") for row in svc.repository.list_drift_alerts(run_id)]
        return {
            "run_id": run_id,
            "release_status": run.release_status,
            "gate_decision": run.gate_decision.model_dump(mode="json") if run.gate_decision else None,
            "drift_alerts": persisted_alerts if persisted_alerts else (run.metadata or {}).get("drift_alerts", []),
        }

    @app.get("/runs/{run_id}/alerts")
    def get_alert_timeline(
        run_id: str,
        limit: int = 50,
        offset: int = 0,
        severity: str | None = None,
        metric: str | None = None,
        svc: EvalService = Depends(get_service),
    ) -> dict:
        try:
            return svc.get_alert_timeline_paginated(
                run_id=run_id,
                limit=limit,
                offset=offset,
                severity=severity,
                metric=metric,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/compare")
    def compare_runs(request: CompareRequest, svc: EvalService = Depends(get_service)) -> dict:
        try:
            compare = svc.compare_runs(
                baseline_run_id=request.baseline_run_id,
                candidate_run_id=request.candidate_run_id,
                gate_config=request.gate_config,
            )
            return {"compare": compare.model_dump(mode="json")}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reports/export")
    def export_report(
        request: ExportReportRequest, svc: EvalService = Depends(get_service)
    ) -> dict:
        try:
            compare = None
            if request.baseline_run_id:
                compare = svc.compare_runs(
                    baseline_run_id=request.baseline_run_id,
                    candidate_run_id=request.run_id,
                    gate_config=GateConfig(max_drop_from_baseline={}),
                )
            output = export_reports(
                repository=svc.repository,
                run_id=request.run_id,
                output_dir=Path(request.output_dir) if request.output_dir else svc.app_config.report_dir,
                compare=compare,
            )
            return {"status": "ok", "artifacts": output}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
