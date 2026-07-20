import json

import httpx
import pytest

from semantic_search_middleware.domain.errors import LlmError
from semantic_search_middleware.llm.ollama import OllamaClient


def build_client(handler):
    # MockTransport intercepts requests in-process: no Ollama, no network.
    return OllamaClient(
        base_url="http://ollama.test",
        model="llama3.2",
        timeout_seconds=5.0,
        transport=httpx.MockTransport(handler),
    )


def test_complete_returns_message_content() -> None:
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["model"] == "llama3.2"
        assert payload["stream"] is False
        assert payload["messages"] == [
            {"role": "system", "content": "be grounded"},
            {"role": "user", "content": "what is ticket 42?"},
        ]
        return httpx.Response(200, json={"message": {"content": "Ticket 42 is resolved."}})

    client = build_client(handler)

    assert client.complete("be grounded", "what is ticket 42?") == "Ticket 42 is resolved."


def test_complete_raises_llm_error_on_http_error() -> None:
    client = build_client(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(LlmError):
        client.complete("system", "user")


def test_complete_raises_llm_error_on_transport_failure() -> None:
    def handler(request):
        raise httpx.ConnectError("connection refused")

    client = build_client(handler)

    with pytest.raises(LlmError):
        client.complete("system", "user")
