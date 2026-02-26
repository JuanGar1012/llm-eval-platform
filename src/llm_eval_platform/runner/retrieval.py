from __future__ import annotations

from llm_eval_platform.domain.models import DatasetItem


def build_retrieval_context(item: DatasetItem) -> str:
    domain = item.tags.get("domain", "general")
    difficulty = item.tags.get("difficulty", "unknown")
    return f"[retrieval-context] domain={domain}; difficulty={difficulty}"

