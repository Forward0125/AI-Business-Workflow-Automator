"""Initial schema -- companies, leads, workflow_runs, workflow_steps,
research_results, qualifications, email_drafts, mocked_actions, alerts.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op


# Alembic identifiers.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the full workflow-automator schema in one migration."""

    # ─── Extensions (idempotent) ─────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # ─── Enums ───────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE workflow_status AS ENUM (
            'queued', 'running', 'success', 'failed', 'cancelled'
        );
    """)
    op.execute("""
        CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'error');
    """)

    # ─── Companies (cached lookups derived from research) ────────────
    op.execute("""
        CREATE TABLE companies (
            id            SERIAL PRIMARY KEY,
            domain        TEXT NOT NULL UNIQUE,
            name          TEXT,
            industry      TEXT,
            size_estimate TEXT,
            metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_companies_industry ON companies(industry);")

    # ─── Leads (one per visitor-submitted URL) ───────────────────────
    op.execute("""
        CREATE TABLE leads (
            id          BIGSERIAL PRIMARY KEY,
            company_id  INTEGER REFERENCES companies(id) ON DELETE SET NULL,
            input_url   TEXT NOT NULL,
            input_kind  TEXT NOT NULL DEFAULT 'url',
            ip_address  INET,
            user_agent  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_leads_company  ON leads(company_id);")
    op.execute("CREATE INDEX idx_leads_created  ON leads(created_at DESC);")

    # ─── Workflow Runs (each pipeline execution) ─────────────────────
    op.execute("""
        CREATE TABLE workflow_runs (
            id                BIGSERIAL PRIMARY KEY,
            lead_id           BIGINT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            status            workflow_status NOT NULL DEFAULT 'queued',
            triggered_by      TEXT,
            started_at        TIMESTAMPTZ,
            finished_at       TIMESTAMPTZ,
            total_cost_usd    NUMERIC(10, 6) NOT NULL DEFAULT 0,
            total_tokens_in   INTEGER NOT NULL DEFAULT 0,
            total_tokens_out  INTEGER NOT NULL DEFAULT 0,
            error_message     TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_runs_lead    ON workflow_runs(lead_id);")
    op.execute("CREATE INDEX idx_runs_status  ON workflow_runs(status);")
    op.execute("CREATE INDEX idx_runs_created ON workflow_runs(created_at DESC);")

    # ─── Workflow Steps (DAG nodes for live viz) ─────────────────────
    op.execute("""
        CREATE TABLE workflow_steps (
            id            BIGSERIAL PRIMARY KEY,
            run_id        BIGINT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            -- 'fetch' / 'web_search' / 'research' / 'qualify' /
            -- 'personalize' / 'crm' / 'calendar' / 'email'
            status        workflow_status NOT NULL DEFAULT 'queued',
            progress_pct  INTEGER NOT NULL DEFAULT 0,
            started_at    TIMESTAMPTZ,
            finished_at   TIMESTAMPTZ,
            metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (run_id, name)
        );
    """)
    op.execute("CREATE INDEX idx_steps_run ON workflow_steps(run_id);")

    # ─── Research Results (structured company profile) ──────────────
    op.execute("""
        CREATE TABLE research_results (
            id                    BIGSERIAL PRIMARY KEY,
            run_id                BIGINT NOT NULL UNIQUE
                                  REFERENCES workflow_runs(id) ON DELETE CASCADE,
            payload               JSONB NOT NULL,
            -- payload keys:
            --   industry, size_estimate, recent_news[],
            --   key_people[], tech_stack[], headline, summary, ...
            summary               TEXT,
            search_results_count  INTEGER,
            fetched_bytes         INTEGER,
            model                 TEXT,
            tokens_in             INTEGER,
            tokens_out            INTEGER,
            cost_usd              NUMERIC(10, 6),
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX idx_research_payload_gin
        ON research_results USING GIN (payload jsonb_path_ops);
    """)

    # ─── Qualifications (BANT scoring) ──────────────────────────────
    op.execute("""
        CREATE TABLE qualifications (
            id                BIGSERIAL PRIMARY KEY,
            run_id            BIGINT NOT NULL UNIQUE
                              REFERENCES workflow_runs(id) ON DELETE CASCADE,
            budget_score      REAL,
            authority_score   REAL,
            need_score        REAL,
            timing_score      REAL,
            composite_score   REAL,                  -- avg of the four
            qualified         BOOLEAN,
            reasoning         TEXT,
            model             TEXT,
            tokens_in         INTEGER,
            tokens_out        INTEGER,
            cost_usd          NUMERIC(10, 6),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_qualifications_qualified ON qualifications(qualified);")

    # ─── Email Drafts (regeneratable per tone) ──────────────────────
    op.execute("""
        CREATE TABLE email_drafts (
            id              BIGSERIAL PRIMARY KEY,
            run_id          BIGINT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
            tone            TEXT NOT NULL,           -- 'technical' / 'executive' / 'casual'
            subject         TEXT NOT NULL,
            body            TEXT NOT NULL,
            cited_findings  JSONB NOT NULL DEFAULT '[]'::jsonb,
            -- list of `[research.<field>]` markers found in the body
            model           TEXT,
            tokens_in       INTEGER,
            tokens_out      INTEGER,
            cost_usd        NUMERIC(10, 6),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_email_drafts_run ON email_drafts(run_id);")

    # ─── Mocked Actions (CRM / calendar / email "sends") ────────────
    op.execute("""
        CREATE TABLE mocked_actions (
            id            BIGSERIAL PRIMARY KEY,
            run_id        BIGINT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
            action        TEXT NOT NULL,             -- 'crm_update' / 'calendar_book' / 'email_send'
            payload       JSONB NOT NULL,            -- visible in the UI as a believable fake
            simulated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_mocked_actions_run ON mocked_actions(run_id);")

    # ─── Alerts (system status feed) ─────────────────────────────────
    op.execute("""
        CREATE TABLE alerts (
            id              BIGSERIAL PRIMARY KEY,
            severity        alert_severity NOT NULL,
            title           TEXT NOT NULL,
            body            TEXT,
            source          TEXT,
            metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
            acknowledged_at TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_alerts_created  ON alerts(created_at DESC);")
    op.execute("CREATE INDEX idx_alerts_severity ON alerts(severity);")


def downgrade() -> None:
    """Drop everything in reverse order."""
    op.execute("DROP TABLE IF EXISTS alerts CASCADE;")
    op.execute("DROP TABLE IF EXISTS mocked_actions CASCADE;")
    op.execute("DROP TABLE IF EXISTS email_drafts CASCADE;")
    op.execute("DROP TABLE IF EXISTS qualifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS research_results CASCADE;")
    op.execute("DROP TABLE IF EXISTS workflow_steps CASCADE;")
    op.execute("DROP TABLE IF EXISTS workflow_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS leads CASCADE;")
    op.execute("DROP TABLE IF EXISTS companies CASCADE;")
    op.execute("DROP TYPE IF EXISTS alert_severity;")
    op.execute("DROP TYPE IF EXISTS workflow_status;")
    # Don't drop extensions -- they may be used by other databases.
