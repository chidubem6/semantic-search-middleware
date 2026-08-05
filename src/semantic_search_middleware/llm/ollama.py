"""Ollama-backed LlmClient implementation.

This is the only module in the project that knows Ollama exists. Swapping to a
hosted model means adding a sibling adapter and changing one line of wiring in
`api/dependencies.py` — nothing else in the codebase refers to Ollama.
"""

import httpx

from semantic_search_middleware.domain.errors import LlmError


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        # `transport` exists so tests can inject httpx.MockTransport. Production
        # callers leave it as None and get real HTTP.
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # stream=False: we want one complete answer, not incremental tokens.
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # Fail loudly. Returning "" here would look like a valid empty answer
            # and silently destroy the grounding guarantee.
            raise LlmError(f"Ollama request failed: {exc}") from exc

        return str(content)
