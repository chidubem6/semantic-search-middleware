# Milestone 1 — Grounded Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `/api/v1/chat` placeholder into a real RAG endpoint: retrieve rows, assemble a grounded prompt, call Ollama, return an answer with citations — or abstain without calling the LLM when retrieval is empty.

**Architecture:** A new `LlmClient` port in `domain/ports.py` with an `OllamaClient` adapter in a new `llm/` package. `ChatService` composes the existing `SearchService` and the `LlmClient`, so retrieval logic stays written once. Prompt assembly lives in `rag/prompts.py` next to the system prompt.

**Tech Stack:** Python 3.12 · FastAPI · httpx (already a dependency) · Ollama · pytest · Pydantic v2.

**Spec:** `docs/superpowers/specs/2026-07-20-milestone-1-grounded-chat-design.md`

## Global Constraints

- **Teaching project.** Tasks marked ✍️ CHIDUBEM give the failing test plus guidance — **do not write the implementation for him.** Tasks marked 🔧 CLAUDE include complete code. This overrides the writing-plans default of "complete code in every step".
- Every task ends with `ruff check . && ruff format --check . && mypy src && pytest` green before committing.
- Commit messages: no `Co-Authored-By` trailer, no "Generated with Claude Code" footer.
- One complete thought per commit. If the message needs an "and", split it.
- `mypy` runs `strict` over `packages = ["semantic_search_middleware"]` only — tests are not type-checked, so test fakes stay unannotated, matching `tests/unit/test_indexer.py`.
- Line length 100 (ruff).
- No test may contact Ollama or Postgres.

## File Structure

**Created:**

| Path | Responsibility |
|---|---|
| `src/semantic_search_middleware/domain/errors.py` | `LlmError` — domain-level failure the API maps to 503 |
| `src/semantic_search_middleware/llm/__init__.py` | package marker (empty) |
| `src/semantic_search_middleware/llm/ollama.py` | the only file that knows Ollama exists |
| `src/semantic_search_middleware/services/chat_service.py` | the use case: retrieve → abstain-or-generate |
| `tests/unit/test_ollama_client.py` | adapter behaviour via `httpx.MockTransport` |
| `tests/unit/test_prompts.py` | context builder contract |
| `tests/unit/test_chat_service.py` | orchestration + the zero-LLM-calls assertion |
| `tests/integration/test_chat.py` | HTTP wiring via dependency overrides |

**Modified:** `domain/ports.py` (+`LlmClient`), `domain/models.py` (+`ChatAnswer`), `rag/prompts.py` (+`build_context_prompt`, +refusal constant), `config/settings.py` (+`llm_timeout_seconds`), `.env.example`, `api/dependencies.py` (+`get_chat_service`), `api/routes/chat.py`, `README.md`, `docs/ROADMAP.md`.

> **Note vs. the earlier walkthrough:** this adds a sixth new source file, `domain/errors.py`. `LlmError` must be raised by the adapter and caught by the route, and both may import from `domain/` — but the route must not import from `llm/`. Putting the error in the domain keeps the arrows pointing inward.

---

### Task 1: `LlmClient` port and `OllamaClient` adapter 🔧 CLAUDE

**Files:**
- Create: `src/semantic_search_middleware/domain/errors.py`
- Create: `src/semantic_search_middleware/llm/__init__.py` (empty)
- Create: `src/semantic_search_middleware/llm/ollama.py`
- Modify: `src/semantic_search_middleware/domain/ports.py`
- Modify: `src/semantic_search_middleware/config/settings.py:27`
- Modify: `.env.example`
- Test: `tests/unit/test_ollama_client.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `LlmClient` protocol with `complete(system_prompt: str, user_prompt: str) -> str`; `OllamaClient(base_url: str, model: str, timeout_seconds: float)`; `LlmError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_ollama_client.py`:

```python
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
```

Add `import json` at the top of the file alongside the other imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ollama_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'semantic_search_middleware.domain.errors'`

- [ ] **Step 3: Write `domain/errors.py`**

```python
class LlmError(RuntimeError):
    """The language model could not be reached or returned an unusable response.

    Defined in the domain (not in `llm/`) so the API layer can catch it without
    importing an adapter. The rule holds: arrows point inward.
    """
```

- [ ] **Step 4: Add the `LlmClient` port**

Append to `src/semantic_search_middleware/domain/ports.py`:

```python
class LlmClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...
```

- [ ] **Step 5: Write the adapter**

`src/semantic_search_middleware/llm/ollama.py`:

```python
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
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

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
```

- [ ] **Step 6: Add the timeout setting**

In `src/semantic_search_middleware/config/settings.py`, after line 27 (`ollama_base_url`):

```python
    llm_timeout_seconds: float = 60.0
```

In `.env.example`, after the `OLLAMA_BASE_URL` line:

```
# Local models can be slow on first load; raise this if you see 503s.
LLM_TIMEOUT_SECONDS=60
```

- [ ] **Step 7: Run the checks**

Run: `pytest tests/unit/test_ollama_client.py -v && ruff check . && ruff format --check . && mypy src`
Expected: 3 passed, no lint or type errors.

- [ ] **Step 8: Commit**

```bash
git add src/semantic_search_middleware/domain/errors.py src/semantic_search_middleware/domain/ports.py src/semantic_search_middleware/llm src/semantic_search_middleware/config/settings.py .env.example tests/unit/test_ollama_client.py
git commit -m "feat(milestone-1): add LlmClient port and Ollama adapter"
```

---

### Task 2: Context builder ✍️ CHIDUBEM

**Files:**
- Modify: `src/semantic_search_middleware/rag/prompts.py`
- Test: `tests/unit/test_prompts.py`

**Interfaces:**
- Consumes: `SearchResult` from `domain/models.py`.
- Produces: `build_context_prompt(question: str, results: Sequence[SearchResult]) -> str` and `INSUFFICIENT_CONTEXT_ANSWER: str`.

**Teach before he writes:** what a prompt actually is (one string — there is no magic), why the retrieved rows must be *labelled* with table and primary key (the model can only cite what it can see identified), and why determinism matters (a prompt that varies run-to-run makes every downstream bug irreproducible). Relate it back to the verbaliser: both turn structured data into text a model can read, but the verbaliser optimises for *embedding* and this optimises for *reading*.

- [ ] **Step 1: Add the test (Claude provides — it defines the contract)**

`tests/unit/test_prompts.py`:

```python
from semantic_search_middleware.domain.models import (
    IndexedDocument,
    SearchResult,
    SourceReference,
)
from semantic_search_middleware.rag.prompts import build_context_prompt


def make_result(pk_value, text, score):
    return SearchResult(
        document=IndexedDocument(
            document_id=f"support_tickets:{pk_value}",
            text=text,
            source=SourceReference(
                table="support_tickets", primary_key="id", primary_key_value=pk_value
            ),
        ),
        score=score,
    )


RESULTS = [
    make_result("42", "subject: password reset fails", 0.91),
    make_result("88", "subject: reset link expired", 0.72),
]


def test_prompt_contains_the_question() -> None:
    prompt = build_context_prompt("how do I fix a failed reset?", RESULTS)

    assert "how do I fix a failed reset?" in prompt


def test_prompt_contains_every_row_and_its_source_labels() -> None:
    prompt = build_context_prompt("how do I fix a failed reset?", RESULTS)

    for result in RESULTS:
        assert result.document.text in prompt
        assert result.document.source.table in prompt
        assert result.document.source.primary_key_value in prompt


def test_prompt_is_deterministic() -> None:
    question = "how do I fix a failed reset?"

    assert build_context_prompt(question, RESULTS) == build_context_prompt(question, RESULTS)
```

Note the assertions check *presence*, not exact equality — the formatting is Chidubem's design decision, and the test deliberately doesn't dictate it.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_prompts.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_context_prompt'`

- [ ] **Step 3: ✍️ Chidubem writes `build_context_prompt` in `rag/prompts.py`**

**Do not write this for him.** Guidance to give if asked:

- Signature: `def build_context_prompt(question: str, results: Sequence[SearchResult]) -> str:`
- Shape to aim for: a labelled context block, then the question last. Models attend well to the end of a prompt, so the question goes after the context, not before it.
- Each result needs a label the model can quote back — something like `[<table>:<pk_value>]` followed by the row text.
- Build a list of lines and `"\n".join(...)` them; don't concatenate in a loop.
- Hint if stuck: iterate `results`, reach `result.document.text` and `result.document.source` for each.
- Ask him: *why does the question go last, and what would break if two rows had identical text but different primary keys?*

Also add the refusal constant, used by Task 3:

```python
INSUFFICIENT_CONTEXT_ANSWER = (
    "I could not find any records relevant to that question, so I cannot answer it."
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_prompts.py -v`
Expected: 3 passed

- [ ] **Step 5: Print a real prompt and read it**

Run:
```bash
python -c "
from tests.unit.test_prompts import RESULTS
from semantic_search_middleware.rag.prompts import build_context_prompt
print(build_context_prompt('how do I fix a failed reset?', RESULTS))
"
```
Expected: a readable context block ending in the question. **Read it as if you were the model** — if a row's origin is ambiguous to you, it's ambiguous to llama3.2.

- [ ] **Step 6: Run the checks and commit**

```bash
ruff check . && ruff format --check . && mypy src && pytest
git add src/semantic_search_middleware/rag/prompts.py tests/unit/test_prompts.py
git commit -m "feat(milestone-1): assemble grounded prompts from retrieved rows"
```

---

### Task 3: `ChatService` ✍️ CHIDUBEM

**Files:**
- Create: `src/semantic_search_middleware/services/chat_service.py`
- Modify: `src/semantic_search_middleware/domain/models.py`
- Test: `tests/unit/test_chat_service.py`

**Interfaces:**
- Consumes: `SearchService.search(query, top_k, filters=None) -> list[SearchResult]`; `LlmClient.complete(system_prompt, user_prompt) -> str`; `build_context_prompt`, `GROUNDED_SYSTEM_PROMPT`, `INSUFFICIENT_CONTEXT_ANSWER` from `rag/prompts.py`.
- Produces: `ChatAnswer(answer: str, citations: list[Citation], supported: bool)`; `ChatService(search_service, llm, top_k)` with `answer(message: str) -> ChatAnswer`.

**Teach before he writes:** that a service orchestrates and never implements — no HTTP, no SQL, no vector maths in this file. And the point of the abstention branch: refusing costs nothing and cannot hallucinate, whereas calling the model with empty context invites a confident fabrication.

- [ ] **Step 1: Add the `ChatAnswer` domain model 🔧 CLAUDE**

Append to `src/semantic_search_middleware/domain/models.py`:

```python
class ChatAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    supported: bool
```

Why a domain model rather than returning `ChatResponse` directly: `ChatResponse` carries `conversation_id`, which is an HTTP-transport concern. The service shouldn't know that HTTP has sessions.

- [ ] **Step 2: Add the test (Claude provides — it defines the contract)**

`tests/unit/test_chat_service.py`:

```python
from semantic_search_middleware.domain.models import (
    IndexedDocument,
    SearchResult,
    SourceReference,
)
from semantic_search_middleware.services.chat_service import ChatService


class FakeSearchService:
    def __init__(self, results):
        self._results = results
        self.calls = []

    def search(self, query, top_k, filters=None):
        self.calls.append((query, top_k))
        return self._results


class RecordingLlm:
    def __init__(self, reply="The reset failed because SMTP was rate-limiting."):
        self._reply = reply
        self.calls = []

    def complete(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self._reply


def make_result(pk_value, score):
    return SearchResult(
        document=IndexedDocument(
            document_id=f"support_tickets:{pk_value}",
            text=f"subject: ticket {pk_value}",
            source=SourceReference(
                table="support_tickets", primary_key="id", primary_key_value=pk_value
            ),
        ),
        score=score,
    )


def test_abstains_without_calling_the_llm_when_retrieval_is_empty() -> None:
    llm = RecordingLlm()
    service = ChatService(FakeSearchService([]), llm, top_k=5)

    result = service.answer("what is the capital of France?")

    assert result.supported is False
    assert result.citations == []
    # The point of this test: refusing must be free. If this ever fails we are
    # paying a model to answer questions we already know we cannot ground.
    assert llm.calls == []


def test_returns_the_llm_answer_when_rows_are_retrieved() -> None:
    llm = RecordingLlm(reply="SMTP was rate-limiting.")
    service = ChatService(FakeSearchService([make_result("42", 0.9)]), llm, top_k=5)

    result = service.answer("why did the reset fail?")

    assert result.supported is True
    assert result.answer == "SMTP was rate-limiting."
    assert len(llm.calls) == 1


def test_cites_every_retrieved_row() -> None:
    results = [make_result("42", 0.9), make_result("88", 0.7)]
    service = ChatService(FakeSearchService(results), RecordingLlm(), top_k=5)

    result = service.answer("why did the reset fail?")

    assert [c.primary_key_value for c in result.citations] == ["42", "88"]
    assert result.citations[0].table == "support_tickets"


def test_passes_the_question_and_configured_top_k_to_retrieval() -> None:
    search = FakeSearchService([make_result("42", 0.9)])
    service = ChatService(search, RecordingLlm(), top_k=3)

    service.answer("why did the reset fail?")

    assert search.calls == [("why did the reset fail?", 3)]


def test_sends_the_grounded_system_prompt_and_a_context_prompt() -> None:
    llm = RecordingLlm()
    service = ChatService(FakeSearchService([make_result("42", 0.9)]), llm, top_k=5)

    service.answer("why did the reset fail?")

    system_prompt, user_prompt = llm.calls[0]
    assert "only the supplied database records" in system_prompt
    assert "why did the reset fail?" in user_prompt
    assert "42" in user_prompt
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_chat_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'semantic_search_middleware.services.chat_service'`

- [ ] **Step 4: ✍️ Chidubem writes `ChatService`**

**Do not write this for him.** Guidance to give if asked:

- Constructor mirrors `SearchService`: store collaborators on `self._…`. Signature: `def __init__(self, search_service: SearchService, llm: LlmClient, top_k: int) -> None:`
- One public method: `def answer(self, message: str) -> ChatAnswer:`
- The body is five lines, in this order: search → early-return if empty → build prompt → call llm → return `ChatAnswer`.
- The early return is a guard clause: `if not results:` … return immediately. Guard first, happy path unindented after — same shape as `if not documents: return 0` in his own `IndexingService`.
- A `Citation` is built from a `SourceReference`; the fields line up one-for-one.
- Ask him: *what would go wrong if we moved the abstention check to after the LLM call?* (Cost, latency, and a fabricated answer we'd then have to throw away.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_chat_service.py -v`
Expected: 5 passed

- [ ] **Step 6: Run the checks and commit**

```bash
ruff check . && ruff format --check . && mypy src && pytest
git add src/semantic_search_middleware/services/chat_service.py src/semantic_search_middleware/domain/models.py tests/unit/test_chat_service.py
git commit -m "feat(milestone-1): add ChatService with retrieval-gated abstention"
```

---

### Task 4: Wire the `/chat` endpoint 🔧 CLAUDE

**Files:**
- Modify: `src/semantic_search_middleware/api/dependencies.py`
- Modify: `src/semantic_search_middleware/api/routes/chat.py`
- Test: `tests/integration/test_chat.py`

**Interfaces:**
- Consumes: `ChatService.answer(message) -> ChatAnswer` (Task 3); `OllamaClient` (Task 1); existing `get_search_service()`.
- Produces: `get_chat_service() -> ChatService`; `POST /api/v1/chat` returning `ChatResponse`.

- [ ] **Step 1: Write the failing test**

`tests/integration/test_chat.py`:

```python
import pytest
from fastapi.testclient import TestClient

from semantic_search_middleware.api.dependencies import get_chat_service
from semantic_search_middleware.api.main import app
from semantic_search_middleware.domain.errors import LlmError
from semantic_search_middleware.domain.models import ChatAnswer, Citation


class FakeChatService:
    def __init__(self, result):
        self._result = result

    def answer(self, message):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_chat_returns_answer_and_citations() -> None:
    answer = ChatAnswer(
        answer="SMTP was rate-limiting.",
        citations=[Citation(table="support_tickets", primary_key="id", primary_key_value="42")],
        supported=True,
    )
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(answer)

    response = TestClient(app).post("/api/v1/chat", json={"message": "why did the reset fail?"})

    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == "SMTP was rate-limiting."
    assert body["supported"] is True
    assert body["citations"][0]["primary_key_value"] == "42"
    assert body["conversation_id"]


def test_chat_echoes_the_supplied_conversation_id() -> None:
    answer = ChatAnswer(answer="…", citations=[], supported=False)
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(answer)

    response = TestClient(app).post(
        "/api/v1/chat", json={"message": "hello", "conversation_id": "abc-123"}
    )

    assert response.json()["conversation_id"] == "abc-123"


def test_chat_returns_503_when_the_model_is_unreachable() -> None:
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(LlmError("down"))

    response = TestClient(app).post("/api/v1/chat", json={"message": "why did the reset fail?"})

    # Never degrade to an ungrounded or empty answer — fail visibly.
    assert response.status_code == 503
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_chat.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_chat_service'`

- [ ] **Step 3: Add the dependency**

Append to `src/semantic_search_middleware/api/dependencies.py` (and add the two imports at the top):

```python
from semantic_search_middleware.llm.ollama import OllamaClient
from semantic_search_middleware.services.chat_service import ChatService


@lru_cache
def get_chat_service() -> ChatService:
    settings = get_settings()
    # The one place the Ollama adapter is named. Swapping providers is a
    # one-line change here; nothing downstream knows the difference.
    return ChatService(
        get_search_service(),
        OllamaClient(
            settings.ollama_base_url,
            settings.llm_model,
            settings.llm_timeout_seconds,
        ),
        settings.top_k,
    )
```

- [ ] **Step 4: Replace the placeholder route**

`src/semantic_search_middleware/api/routes/chat.py` in full:

```python
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from semantic_search_middleware.api.dependencies import get_chat_service
from semantic_search_middleware.api.schemas import ChatRequest, ChatResponse
from semantic_search_middleware.domain.errors import LlmError
from semantic_search_middleware.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    try:
        result = service.answer(request.message)
    except LlmError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(
        answer=result.answer,
        citations=result.citations,
        supported=result.supported,
        conversation_id=request.conversation_id or str(uuid4()),
    )
```

- [ ] **Step 5: Run the checks**

Run: `pytest -v && ruff check . && ruff format --check . && mypy src`
Expected: all tests pass (including the pre-existing search, health, indexer, verbaliser tests).

- [ ] **Step 6: Commit**

```bash
git add src/semantic_search_middleware/api/dependencies.py src/semantic_search_middleware/api/routes/chat.py tests/integration/test_chat.py
git commit -m "feat(milestone-1): serve grounded answers from /api/v1/chat"
```

---

### Task 5: Manual verification against real Ollama 🔧 CLAUDE + ✍️ CHIDUBEM

**Files:** none changed unless a defect surfaces.

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: nothing. This is the gate before the docs commit.

- [ ] **Step 1: Ensure the model is pulled and the index is populated**

```bash
ollama pull llama3.2
docker compose up -d db
python scripts/index_source.py
```
Expected: the indexer prints a non-zero document count.

- [ ] **Step 2: Start the API**

```bash
uvicorn semantic_search_middleware.api.main:app --reload
```

- [ ] **Step 3: Ask a question the index can answer**

```bash
curl -s -X POST localhost:8000/api/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message": "how do I fix a failed password reset?"}'
```
Expected: `"supported": true`, a grounded answer, and citations whose `primary_key_value`s are real ticket IDs. **Spot-check one** — open that ticket in the source database and confirm the answer reflects it.

- [ ] **Step 4: Ask a question the index cannot answer**

```bash
curl -s -X POST localhost:8000/api/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message": "what is the capital of France?"}'
```
Expected: `"supported": false`, `"citations": []`, the refusal text. The uvicorn log should show **no** outbound Ollama request.

If this returns an answer instead, the retrieval gate is leaking: check `MIN_SIMILARITY_SCORE` — the threshold may be too low for the embedding model in use.

- [ ] **Step 5: Kill Ollama and confirm we fail loudly**

Stop Ollama, then repeat Step 3.
Expected: HTTP 503 with a clear detail message — **not** a fabricated answer, not an empty string.

- [ ] **Step 6: Reflection (Feynman check)**

Chidubem explains back, unprompted by notes: what RAG is, why abstention happens before the LLM call, and where the boundary sits between `ChatService` and `OllamaClient`. Gaps here mean re-teach, not move on.

---

### Task 6: Update the docs 🔧 CLAUDE

**Files:**
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Create: `docs/learning/05-milestone-1-grounded-chat.md` (gitignored — do not commit)

**Interfaces:**
- Consumes: the verified behaviour from Task 5.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Document the endpoint in `README.md`**

Add a `/api/v1/chat` section mirroring the existing `/api/v1/search` one: request body (`message`, optional `conversation_id`), response body (`answer`, `citations`, `conversation_id`, `supported`), a worked example, and a note that Ollama must be running and the index populated.

- [ ] **Step 2: Mark Milestone 1 complete in `docs/ROADMAP.md`**

Under "Milestone 1 — Grounded chat", note that prompt assembly, the Ollama adapter, retrieval-gated abstention, and citations are done, and that **post-generation faithfulness checking is deferred to Milestone 5**, where an eval set can measure it.

- [ ] **Step 3: Write the learning note (gitignored)**

`docs/learning/05-milestone-1-grounded-chat.md`, following the shape of `04-milestone-0-vertical-slice.md`: the 30-second pitch, the 2-minute architecture story, RAG vs fine-tuning, why abstention is a retrieval gate, what's weak about the system, and a confidence audit.

Per CLAUDE.md this file is gitignored study material — **do not commit or push it**.

- [ ] **Step 4: Commit the docs only**

```bash
git add README.md docs/ROADMAP.md
git commit -m "docs: describe the grounded chat endpoint"
git status
```
Expected: `git status` shows `docs/learning/` untracked-and-ignored, never staged.

---

## Deferred (explicitly not in this chunk)

- Post-generation faithfulness / citation validation → Milestone 5.
- Multi-turn conversation history → `conversation_id` is echoed, not used.
- Streaming responses, hosted-LLM adapters, `retrieval/hybrid.py` → Milestone 3.
- Streamlit chat UI.
