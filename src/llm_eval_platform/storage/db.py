from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Engine


metadata = MetaData()
DB_SCHEMA_VERSION = 3

schema_metadata_table = Table(
    "schema_metadata",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("schema_version", Integer, nullable=False),
)

datasets_table = Table(
    "datasets",
    metadata,
    Column("dataset_name", String, primary_key=True),
    Column("version", String, primary_key=True),
    Column("path", String, nullable=False),
    Column("checksum", String, nullable=False),
    Column("item_count", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

runs_table = Table(
    "runs",
    metadata,
    Column("run_id", String, primary_key=True),
    Column("run_key", String, nullable=False, index=True),
    Column("run_version", Integer, nullable=False),
    Column("variant_name", String, nullable=False),
    Column("dataset_name", String, nullable=False),
    Column("dataset_version", String, nullable=False),
    Column("model_name", String, nullable=False),
    Column("prompt_version", String, nullable=False),
    Column("retrieval_enabled", Boolean, nullable=False),
    Column("llm_judge_enabled", Boolean, nullable=False),
    Column("seed", Integer, nullable=False),
    Column("temperature", Float, nullable=False, server_default=text("0.0")),
    Column("dataset_fingerprint", String, nullable=False, server_default=text("''")),
    Column("prompt_fingerprint", String, nullable=False, server_default=text("''")),
    Column("config_fingerprint", String, nullable=False, server_default=text("''")),
    Column("experiment_signature", String, nullable=False, server_default=text("''")),
    Column("release_status", String, nullable=False, server_default=text("'BLOCKED'")),
    Column("status", String, nullable=False),
    Column("duration_ms", Float, nullable=True),
    Column("avg_latency_ms", Float, nullable=True),
    Column("p95_latency_ms", Float, nullable=True),
    Column("token_in_est", Integer, nullable=False, server_default=text("0")),
    Column("token_out_est", Integer, nullable=False, server_default=text("0")),
    Column("cost_est_usd", Float, nullable=False, server_default=text("0.0")),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("aggregate_metrics", JSON, nullable=True),
    Column("gate_decision", JSON, nullable=True),
    Column("metadata", JSON, nullable=False, server_default=text("'{}'")),
)

item_results_table = Table(
    "item_results",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String, nullable=False, index=True),
    Column("item_id", String, nullable=False),
    Column("prompt", String, nullable=False),
    Column("output_text", String, nullable=False),
    Column("expected_answer", String, nullable=True),
    Column("keywords", JSON, nullable=False, server_default=text("'[]'")),
    Column("error", String, nullable=True),
    Column("latency_ms", Float, nullable=True),
    Column("token_in_est", Integer, nullable=True),
    Column("token_out_est", Integer, nullable=True),
    Column("schema_error", String, nullable=True),
    Column("keyword_misses", JSON, nullable=False, server_default=text("'[]'")),
    Column("exact_match", Float, nullable=False),
    Column("keyword_coverage", Float, nullable=False),
    Column("schema_valid", Float, nullable=False),
    Column("llm_judge_score", Float, nullable=True),
    Column("tags", JSON, nullable=False, server_default=text("'{}'")),
)

run_tag_metrics_table = Table(
    "run_tag_metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String, nullable=False, index=True),
    Column("tag_key", String, nullable=False),
    Column("tag_value", String, nullable=False),
    Column("exact_match", Float, nullable=False),
    Column("keyword_coverage", Float, nullable=False),
    Column("schema_valid", Float, nullable=False),
    Column("llm_judge_score", Float, nullable=True),
    Column("sample_count", Integer, nullable=False),
)

run_drift_alerts_table = Table(
    "run_drift_alerts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String, nullable=False, index=True),
    Column("dataset_name", String, nullable=False),
    Column("dataset_version", String, nullable=False),
    Column("scope", String, nullable=False),
    Column("metric", String, nullable=True),
    Column("severity", String, nullable=False),
    Column("delta", Float, nullable=True),
    Column("threshold", Float, nullable=True),
    Column("message", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def create_db_engine(db_path: Path) -> Engine:
    return create_engine(f"sqlite+pysqlite:///{db_path}", future=True)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    _migrate_additive_columns(engine)
    with engine.begin() as conn:
        row = conn.execute(
            select(schema_metadata_table.c.schema_version).where(schema_metadata_table.c.id == 1)
        ).first()
        if row is None:
            conn.execute(
                insert(schema_metadata_table).values(id=1, schema_version=DB_SCHEMA_VERSION)
            )
            return
        existing_version = int(row[0])
        if existing_version > DB_SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported DB schema version {existing_version}. Expected <= {DB_SCHEMA_VERSION}."
            )
        if existing_version < DB_SCHEMA_VERSION:
            conn.execute(
                schema_metadata_table.update()
                .where(schema_metadata_table.c.id == 1)
                .values(schema_version=DB_SCHEMA_VERSION)
            )


def get_schema_version(engine: Engine) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            select(schema_metadata_table.c.schema_version).where(schema_metadata_table.c.id == 1)
        ).first()
    if row is None:
        raise RuntimeError("Schema metadata not initialized.")
    return int(row[0])


def _migrate_additive_columns(engine: Engine) -> None:
    _ensure_columns(
        engine=engine,
        table_name="runs",
        columns={
            "temperature": "FLOAT DEFAULT 0.0",
            "dataset_fingerprint": "TEXT DEFAULT ''",
            "prompt_fingerprint": "TEXT DEFAULT ''",
            "config_fingerprint": "TEXT DEFAULT ''",
            "experiment_signature": "TEXT DEFAULT ''",
            "release_status": "TEXT DEFAULT 'BLOCKED'",
            "duration_ms": "FLOAT",
            "avg_latency_ms": "FLOAT",
            "p95_latency_ms": "FLOAT",
            "token_in_est": "INTEGER DEFAULT 0",
            "token_out_est": "INTEGER DEFAULT 0",
            "cost_est_usd": "FLOAT DEFAULT 0.0",
        },
    )
    _ensure_columns(
        engine=engine,
        table_name="item_results",
        columns={
            "expected_answer": "TEXT",
            "keywords": "JSON DEFAULT '[]'",
            "latency_ms": "FLOAT",
            "token_in_est": "INTEGER",
            "token_out_est": "INTEGER",
            "schema_error": "TEXT",
            "keyword_misses": "JSON DEFAULT '[]'",
        },
    )


def _ensure_columns(engine: Engine, table_name: str, columns: dict[str, str]) -> None:
    with engine.begin() as conn:
        current = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        names = {row[1] for row in current}
        for col_name, col_type in columns.items():
            if col_name in names:
                continue
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
