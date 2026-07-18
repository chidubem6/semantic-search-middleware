-- Runs ONCE, the first time the container initialises an empty data volume.
-- At this point psql is connected to the default database (semantic_search).

-- 1. Enable pgvector in the index database, where our `documents` table (with the
--    embedding vector column) will live. Plain Postgres cannot store/search
--    vectors; this extension is what adds that ability.
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create a SEPARATE "source" database. This stands in for an external system's
--    database that the middleware reads from (read-only). Keeping the source data
--    apart from our embeddings index mirrors how this runs in the real world.
CREATE DATABASE source_data;
