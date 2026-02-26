from __future__ import annotations

import logging

import httpx


logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float = 0.0,
    ) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(f"{self._base_url}/api/generate", json=payload)
                response.raise_for_status()
            body = response.json()
            return str(body.get("response", "")).strip()
        except Exception:
            logger.exception("Ollama request failed for model=%s", model)
            raise

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
            body = response.json()
            models = body.get("models", [])
            names: list[str] = []
            for model in models:
                name = model.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
            return names
        except Exception:
            logger.exception("Failed to list local Ollama models")
            raise
