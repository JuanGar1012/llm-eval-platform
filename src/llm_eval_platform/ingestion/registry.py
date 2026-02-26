from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from llm_eval_platform.domain.models import DatasetItem, DatasetRecord


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl_dataset(path: Path) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            item = DatasetItem.model_validate(
                {
                    "item_id": payload["item_id"],
                    "prompt": payload["prompt"],
                    "expected_answer": payload.get("expected_answer"),
                    "keywords": payload.get("keywords", []),
                    "tags": payload.get("tags", {}),
                    "output_schema": payload.get("output_schema"),
                    "metadata": payload.get("metadata", {}),
                }
            )
            items.append(item)
    if not items:
        raise ValueError(f"Dataset {path} has no valid rows.")
    return items


def build_dataset_record(dataset_name: str, version: str, path: Path, items: list[DatasetItem]) -> DatasetRecord:
    return DatasetRecord(
        dataset_name=dataset_name,
        version=version,
        path=str(path),
        checksum=checksum_file(path),
        item_count=len(items),
        created_at=datetime.now(tz=timezone.utc),
    )

