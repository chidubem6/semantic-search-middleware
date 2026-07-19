# Product Requirements Document (PRD)

## Semantic Search Middleware for Relational Databases with Chatbot Integration

|Field           |Value             |
|----------------|------------------|
|Document version|1.0               |
|Status          |Draft             |
|Owner           |Intern / Developer|
|Last updated    |June 2026         |

-----

## 1. Overview

### 1.1 Problem statement

Relational databases store the majority of structured enterprise data but are built around exact-match, structured queries (SQL). They cannot natively answer questions phrased in natural language or retrieve records by *meaning* rather than literal value. As LLM-powered chatbots become common interfaces, this gap forces a choice between rigid SQL front-ends and ungrounded LLMs that hallucinate answers.

### 1.2 Solution summary

A middleware layer that sits between a relational database and a chatbot. It converts structured records into vector embeddings, stores them in a vector database, and serves a semantic-retrieval API. A chatbot consumes this API through a retrieval-augmented generation (RAG) flow so that every answer is grounded in actual database records, traceable to its source rows, and far less prone to hallucination.

### 1.3 Goals

- Enable natural-language, meaning-based querying over relational data.
- Keep chatbot answers grounded in and traceable to source records.
- Measurably reduce hallucination versus an ungrounded LLM baseline.
- Deliver acceptable accuracy and response time on a realistic dataset.

### 1.4 Non-goals (out of scope for MVP)

- Production-grade authentication, multi-tenancy, and access control.
- Support for every database engine (target one or two, e.g. PostgreSQL/MySQL).
- Write-back to the database (system is read-only).
- Full-scale horizontal scaling; the focus is a correct, evaluated prototype.

-----

## 2. Users & use cases

|Persona               |Need                                     |Example query                                           |
|----------------------|-----------------------------------------|--------------------------------------------------------|
|Business/end user     |Ask questions without knowing SQL        |“Which customers complained about late delivery?”       |
|Analyst               |Explore data by meaning, then drill in   |“Show orders similar to the ones flagged as fraudulent.”|
|Developer (integrator)|Embed semantic search into an app via API|Calls `/search` and `/chat` endpoints                   |

Primary use case: a user types a question in the chat interface; the system retrieves the most relevant records and returns a grounded, cited answer.

-----

## 3. Functional requirements (features that must be in the end product)

### 3.1 Data ingestion & connector

- **FR-1** Connect to a relational database (PostgreSQL as primary target) and read schema and table data.
- **FR-2** Support selecting which tables/columns are indexed via configuration.
- **FR-3** Preserve a link from every generated document back to its source table and primary key.

### 3.2 Verbalisation / representation

- **FR-4** Convert each record into an embeddable text “document” using a configurable strategy (row serialisation and/or template-based natural-language verbalisation).
- **FR-5** Support relationship-aware documents that follow foreign keys, so joined context (e.g. an order + its customer + line items) is embedded together rather than as isolated fragments.

### 3.3 Embedding & vector storage

- **FR-6** Generate vector embeddings for all documents using a configurable embedding model.
- **FR-7** Store embeddings plus metadata (source table, primary key, original field values) in a vector database.
- **FR-8** Support incremental re-indexing: when source rows change, the affected vectors are regenerated (scheduled or triggered sync) to avoid stale results.

### 3.4 Semantic retrieval API

- **FR-9** Expose a search endpoint: query text → top-k most relevant records with similarity scores and metadata.
- **FR-10** Support metadata filtering (e.g. restrict to a table, date range, or category).
- **FR-11** Support hybrid retrieval (keyword + vector) to handle exact entity names that pure vector search misses.

### 3.5 Chatbot & RAG

- **FR-12** Provide a chat interface accepting natural-language questions.
- **FR-13** Implement a RAG flow: retrieve relevant records, inject them as context, and generate an answer constrained to that context.
- **FR-14** Maintain conversation context for follow-up questions.

### 3.6 Grounding & hallucination control

- **FR-15** Instruct the model to answer only from retrieved context and to respond “I don’t know / not enough information” when context is insufficient.
- **FR-16** Provide citations: every answer references the source rows/primary keys it was derived from.
- **FR-17** Flag or suppress answers that are not supported by the retrieved context (faithfulness check).

### 3.7 Stretch / optional

- **FR-18 (stretch)** Hybrid query router that sends precise/aggregate questions (“how many”, “total revenue”) to a generated-SQL path and meaning-based questions to semantic retrieval. *(Recommended because pure vector search cannot count or aggregate reliably.)*

-----

## 4. Non-functional requirements

- **NFR-1 Accuracy** — Retrieval and answer correctness measured against a fixed question set; target defined during evaluation (e.g. retrieval recall@5 and answer-correctness baselines).
- **NFR-2 Response time** — End-to-end latency tracked and reported, broken down by embedding, retrieval, and generation stages.
- **NFR-3 Robustness** — Graceful handling of paraphrased, ambiguous, and out-of-scope questions (refuses instead of fabricating).
- **NFR-4 Reliability/grounding** — Demonstrable reduction in hallucination versus an ungrounded LLM baseline.
- **NFR-5 Configurability** — Embedding model, vector store, and indexed tables are swappable via config.
- **NFR-6 Reproducibility** — Deterministic ingestion and an evaluation script that can be re-run.

-----

## 5. System architecture

```
Relational DB ──► Connector ──► Verbaliser ──► Embedding ──► Vector DB
                                                                 │
User ──► Chat UI ──► RAG Orchestrator ──► Retrieval API ◄────────┘
                          │
                          └──► LLM (grounded prompt + citations) ──► Answer
```

Components:

1. **Connector layer** — reads schema/rows from the relational DB.
1. **Verbalisation layer** — turns rows into embeddable documents with source references.
1. **Embedding service** — produces vectors.
1. **Vector store** — holds vectors + metadata; serves similarity search.
1. **Retrieval API** — query → ranked records with filters.
1. **RAG orchestrator** — assembles context, calls the LLM, enforces grounding.
1. **Chat interface** — user-facing front end.
1. **Sync job** — keeps vectors consistent with the source DB.

-----

## 6. Technologies (proposed stack)

|Layer        |Technology                                                        |Rationale                                                                                                  |
|-------------|------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
|Language     |Python                                                            |Dominant ecosystem for ML/RAG tooling                                                                      |
|Relational DB|PostgreSQL (primary), MySQL (optional)                            |Common, well-documented                                                                                    |
|Vector store |pgvector *or* Qdrant / Chroma / Weaviate                          |pgvector keeps vectors alongside relational data, simplifying sync; standalone stores (Qdrant) scale better|
|Embeddings   |sentence-transformers (e.g. local model) or a hosted embedding API|Local = free/offline; hosted = higher quality                                                              |
|Orchestration|LangChain or LlamaIndex                                           |Prebuilt RAG, retrieval, and connector abstractions                                                        |
|LLM          |Open-source (e.g. via Ollama) or a hosted chat model              |Open = cost/privacy; hosted = quality                                                                      |
|Chat UI      |Streamlit (or a lightweight web app)                              |Fast to build for a prototype                                                                              |
|Evaluation   |RAGAS + custom scripts                                            |Standard RAG metrics (faithfulness, relevancy, context precision/recall)                                   |
|API          |FastAPI                                                           |Clean, typed endpoints for search/chat                                                                     |

*The exact embedding model, vector store, and LLM should be finalized in Phase 0 and recorded here as decisions.*

-----

## 7. Key concepts & techniques used

- **Vector embeddings** — numerical representations capturing semantic meaning of text.
- **Semantic / similarity search** — retrieval by vector distance (cosine/dot product) rather than exact match.
- **Data verbalisation** — converting structured rows into natural-language text suitable for embedding.
- **Relationship-aware chunking** — following foreign keys so embedded documents retain relational context.
- **Retrieval-Augmented Generation (RAG)** — grounding LLM answers in retrieved context.
- **Hybrid search** — combining keyword (lexical) and vector (semantic) retrieval.
- **Grounding & citation** — tying answers to source records to enable verification.
- **Hallucination mitigation** — constrained prompting, faithfulness checks, and abstention on low context.
- **Incremental indexing / sync** — keeping the vector store consistent with a changing database.
- **(Stretch) Text-to-SQL routing** — directing precise/aggregate queries to generated SQL.
- **Evaluation metrics** — retrieval precision/recall@k, faithfulness, answer relevancy, latency.

-----

## 8. Success metrics

- **Hallucination reduction** — grounded system vs. ungrounded LLM baseline on the question set (headline result).
- **Retrieval quality** — precision/recall@k against labelled expected records.
- **Answer correctness** — judged accuracy on the fixed question set.
- **Latency** — median and tail end-to-end response time, with per-stage breakdown.
- **Robustness rate** — share of ambiguous/out-of-scope questions handled gracefully.

-----

## 9. Deliverables

1. Functional middleware (connector → verbaliser → embeddings → vector store → retrieval API).
1. Chatbot interface with grounded, cited answers.
1. Vector database populated from a realistic relational dataset.
1. Evaluation report (accuracy, response time, robustness, hallucination reduction).
1. Documentation (architecture, setup, design decisions) and final presentation.

-----

## 10. Risks & assumptions

|Risk                                                 |Mitigation                                             |
|-----------------------------------------------------|-------------------------------------------------------|
|Pure vector search fails on aggregate/numeric queries|Add the text-to-SQL hybrid path (FR-18)                |
|Stale embeddings after DB changes                    |Incremental sync (FR-8)                                |
|Poor verbalisation → poor retrieval                  |Compare strategies early; iterate (FR-4/FR-5)          |
|Embedding/LLM cost or latency                        |Prefer local models for the prototype; cache embeddings|
|Evaluation set too small/biased                      |Build 30–50 representative questions up front          |

**Assumptions:** read-only access to a representative dataset is available; a single domain/schema is sufficient for the prototype; the internship runs roughly 12 weeks.