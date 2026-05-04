-- ─────────────────────────────────────────────────────────────────
-- AI Business Workflow Automator -- Postgres extension bootstrap.
--
-- The pgvector docker image runs every .sql file in
-- /docker-entrypoint-initdb.d/ on first container init.
-- For Neon (or any managed Postgres), run this file once after
-- creating the database:
--   psql "$DATABASE_URL" -f infra/postgres/init/01-extensions.sql
-- ─────────────────────────────────────────────────────────────────

-- Dense vector retrieval (kept for parity with InsightFinder; not
-- strictly required for v1 but makes adding semantic features later
-- a one-line migration instead of an extension dance).
CREATE EXTENSION IF NOT EXISTS vector;

-- Trigram fuzzy matching -- useful for company-name dedup later.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Sanity check.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'pgvector extension failed to install';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    RAISE EXCEPTION 'pg_trgm extension failed to install';
  END IF;
END $$;
