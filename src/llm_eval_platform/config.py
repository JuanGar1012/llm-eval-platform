from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "llm_eval.db"
DEFAULT_REPORT_DIR = ROOT_DIR / "reports"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


@dataclass(frozen=True)
class AppConfig:
    db_path: Path = DEFAULT_DB_PATH
    report_dir: Path = DEFAULT_REPORT_DIR
    ollama_url: str = DEFAULT_OLLAMA_URL


def stable_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_run_key(
    *,
    dataset_name: str,
    dataset_version: str,
    prompt_version: str,
    model_name: str,
    retrieval_enabled: bool,
    llm_judge_enabled: bool,
    seed: int,
) -> str:
    base = {
        "dataset_name": dataset_name,
        "dataset_version": dataset_version,
        "prompt_version": prompt_version,
        "model_name": model_name,
        "retrieval_enabled": retrieval_enabled,
        "llm_judge_enabled": llm_judge_enabled,
        "seed": seed,
    }
    return stable_hash(base)[:16]


def build_fingerprints(
    *,
    dataset_name: str,
    dataset_version: str,
    dataset_checksum: str,
    prompt_version: str,
    prompt_template: str,
    model_name: str,
    retrieval_enabled: bool,
    llm_judge_enabled: bool,
    llm_judge_model: str | None,
    temperature: float,
    seed: int,
) -> dict[str, str]:
    dataset_fingerprint = stable_hash(
        {
            "dataset_name": dataset_name,
            "dataset_version": dataset_version,
            "dataset_checksum": dataset_checksum,
        }
    )
    prompt_fingerprint = stable_hash(
        {
            "prompt_version": prompt_version,
            "prompt_template": prompt_template,
        }
    )
    config_fingerprint = stable_hash(
        {
            "model_name": model_name,
            "retrieval_enabled": retrieval_enabled,
            "llm_judge_enabled": llm_judge_enabled,
            "llm_judge_model": llm_judge_model,
            "temperature": f"{temperature:.6f}",
            "seed": seed,
            "prompt_fingerprint": prompt_fingerprint,
            "dataset_fingerprint": dataset_fingerprint,
        }
    )
    experiment_signature = stable_hash(
        {
            "dataset_fingerprint": dataset_fingerprint,
            "prompt_fingerprint": prompt_fingerprint,
            "config_fingerprint": config_fingerprint,
            "platform_version": "1",
        }
    )
    return {
        "dataset_fingerprint": dataset_fingerprint,
        "prompt_fingerprint": prompt_fingerprint,
        "config_fingerprint": config_fingerprint,
        "experiment_signature": experiment_signature,
    }
