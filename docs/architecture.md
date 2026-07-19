# Architecture

## Design principles

1. **Traceability first:** every indexed document retains its source table, primary key name, and primary key value.
2. **Read-only source access:** the middleware never writes to the source database.
3. **Provider boundaries:** database connectors, embedders, vector stores, and LLM clients implement replaceable interfaces.
4. **Deterministic ingestion:** the same source row and configuration should produce the same document.
5. **Abstention by default:** unsupported answers are rejected rather than guessed.

## MVP request flow

1. `/search` receives query text and optional metadata filters.
2. The embedding provider produces a normalised query vector.
3. The vector store returns the top-k documents and source metadata.
4. `/chat` passes those documents to the RAG service.
5. The RAG service generates an answer constrained to the records.
6. The response contains source-row citations and a support flag.

## Deferred decisions

- Exact source dataset and schema.
- Hosted model versus Ollama.
- Whether PostgreSQL full-text search is sufficient for lexical retrieval.
- Change-data-capture versus scheduled incremental sync.
