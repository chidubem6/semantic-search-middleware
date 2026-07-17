# ADR 0001: Use PostgreSQL with pgvector for the MVP

## Status
Accepted for the initial scaffold.

## Context
The project needs a vector store while retaining metadata that maps directly to relational source rows.

## Decision
Use PostgreSQL with pgvector for the MVP.

## Consequences
- One operational database can hold vectors and metadata.
- SQL filtering and vector retrieval can be combined.
- The project avoids introducing Qdrant or Weaviate before scale requires it.
- The VectorStore interface remains implementation-independent.
