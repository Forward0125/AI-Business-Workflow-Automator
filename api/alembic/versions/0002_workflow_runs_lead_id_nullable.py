"""Allow workflow_runs.lead_id to be NULL.

The pipeline orchestrator creates a workflow_run BEFORE the fetch step
runs (so the SSE stream has a stable run_id to subscribe to), and only
fills in lead_id once the lead is created. lead_id stays a real FK --
just relaxed to nullable.

Revision ID: 0002_lead_nullable
Revises: 0001_initial
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op


revision = "0002_lead_nullable"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE workflow_runs ALTER COLUMN lead_id DROP NOT NULL;")


def downgrade() -> None:
    # Failing rows would have to be deleted before re-applying NOT NULL,
    # but for a fresh local DB this is reversible.
    op.execute("DELETE FROM workflow_runs WHERE lead_id IS NULL;")
    op.execute("ALTER TABLE workflow_runs ALTER COLUMN lead_id SET NOT NULL;")
