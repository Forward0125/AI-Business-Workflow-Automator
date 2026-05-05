"""DB operations for ``workflow_runs`` and ``workflow_steps``.

Each pipeline run creates one ``workflow_runs`` row + 8 child rows
in ``workflow_steps``, one per step in the DAG. The frontend's
Workflows view subscribes to SSE for step transitions and reads
these tables to paint the DAG.
"""

from __future__ import annotations

import json
from typing import Any

from app import db


# Step names match the screenshot's DAG. Order matters here -- the
# pipeline runs them in this order and the UI lays them out the
# same way.
STEP_NAMES: tuple[str, ...] = (
    "fetch",
    "web_search",
    "research",
    "qualify",
    "personalize",
    "crm",
    "calendar",
    "email",
)


# ─── Runs ────────────────────────────────────────────────────────


async def create_run(
    *,
    triggered_by: str,
    ip_address:   str | None = None,
) -> int:
    """Create a workflow_run + 8 step rows. Returns the run id.

    lead_id stays NULL until the fetch step writes it (see
    ``set_lead_id`` below).
    """
    async with db.get_conn() as conn, conn.transaction():
        run_id = await conn.fetchval(
            """
            INSERT INTO workflow_runs (
                lead_id, status, triggered_by, started_at, created_at
            )
            VALUES (NULL, 'running', $1, NOW(), NOW())
            RETURNING id
            """,
            triggered_by,
        )
        await conn.executemany(
            """
            INSERT INTO workflow_steps (run_id, name, status)
            VALUES ($1, $2, 'queued')
            """,
            [(run_id, name) for name in STEP_NAMES],
        )
    return run_id


async def set_lead_id(run_id: int, lead_id: int) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            "UPDATE workflow_runs SET lead_id = $2 WHERE id = $1",
            run_id, lead_id,
        )


async def complete_run(
    run_id: int,
    *,
    total_cost_usd:   float = 0.0,
    total_tokens_in:  int   = 0,
    total_tokens_out: int   = 0,
) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE workflow_runs
               SET status            = 'success',
                   finished_at       = NOW(),
                   total_cost_usd    = $2,
                   total_tokens_in   = $3,
                   total_tokens_out  = $4
             WHERE id = $1
            """,
            run_id, total_cost_usd, total_tokens_in, total_tokens_out,
        )


async def fail_run(run_id: int, error: str) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE workflow_runs
               SET status        = 'failed',
                   finished_at   = NOW(),
                   error_message = $2
             WHERE id = $1
            """,
            run_id, error[:1000],
        )


async def get_run(run_id: int) -> dict | None:
    """Return the run + its 8 steps. Steps come back ordered as written."""
    async with db.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, lead_id, status, triggered_by,
                   started_at, finished_at,
                   total_cost_usd, total_tokens_in, total_tokens_out,
                   error_message, created_at
            FROM workflow_runs
            WHERE id = $1
            """,
            run_id,
        )
        if row is None:
            return None
        steps = await conn.fetch(
            """
            SELECT name, status, progress_pct,
                   started_at, finished_at, metadata
            FROM workflow_steps
            WHERE run_id = $1
            ORDER BY id
            """,
            run_id,
        )
    return {**dict(row), "steps": [dict(s) for s in steps]}


# ─── Steps ───────────────────────────────────────────────────────


async def start_step(run_id: int, name: str) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE workflow_steps
               SET status       = 'running',
                   started_at   = NOW(),
                   progress_pct = 0
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name,
        )


async def complete_step(
    run_id: int,
    name:   str,
    metadata: dict[str, Any] | None = None,
) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE workflow_steps
               SET status       = 'success',
                   progress_pct = 100,
                   finished_at  = NOW(),
                   metadata     = $3::jsonb
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name, json.dumps(metadata or {}),
        )


async def fail_step(run_id: int, name: str, error: str) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE workflow_steps
               SET status      = 'failed',
                   finished_at = NOW(),
                   metadata    = $3::jsonb
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name, json.dumps({"error": error[:500]}),
        )
