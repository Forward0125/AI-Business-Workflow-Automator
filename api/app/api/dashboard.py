"""Dashboard summary endpoint.

Single ``GET /dashboard/summary`` rolls up everything the dashboard
needs in one round-trip: KPIs, 7-day timeseries, top recent leads,
alerts feed.

Polling pattern is fine here -- no per-event semantics, so SSE would
be overkill.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app import db


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ─── Schemas ─────────────────────────────────────────────────────


class KPIs(BaseModel):
    leads_24h:       int
    leads_total:     int
    runs_total:      int
    runs_last_7d:    int
    active_runs:     int
    avg_cost_usd:    float | None = None       # over successful runs (7d)
    qualified_rate:  float | None = None       # 0..1, all-time


class TimeseriesPoint(BaseModel):
    day:        str          # 'YYYY-MM-DD'
    runs:       int
    qualified:  int
    avg_cost:   float | None = None


class TopLead(BaseModel):
    lead_id:        int
    domain:         str | None
    industry:       str | None
    input_url:      str
    run_id:         int | None
    run_status:     str | None
    qualified:      bool | None
    composite:      float | None
    email_subject:  str | None
    created_at:     Any | None


class AlertRow(BaseModel):
    id:         int
    severity:   str
    title:      str
    body:       str | None
    source:     str | None
    created_at: Any | None


class DashboardSummary(BaseModel):
    kpis:       KPIs
    timeseries: list[TimeseriesPoint]
    top_leads:  list[TopLead]
    alerts:     list[AlertRow]


# ─── Endpoint ────────────────────────────────────────────────────


@router.get("/summary", response_model=DashboardSummary)
async def get_summary() -> DashboardSummary:
    async with db.get_conn() as conn:
        # KPIs ─────────────────────────────────────────────────
        kpi_row = await conn.fetchrow(
            """
            WITH recent_runs AS (
                SELECT id, status, total_cost_usd
                FROM workflow_runs
                WHERE created_at > NOW() - INTERVAL '7 days'
            ),
            qual AS (
                SELECT q.qualified
                FROM qualifications q
                JOIN workflow_runs wr ON wr.id = q.run_id
            )
            SELECT
                (SELECT count(*) FROM leads
                    WHERE created_at > NOW() - INTERVAL '24 hours')::int     AS leads_24h,
                (SELECT count(*) FROM leads)::int                            AS leads_total,
                (SELECT count(*) FROM workflow_runs)::int                    AS runs_total,
                (SELECT count(*) FROM recent_runs)::int                      AS runs_last_7d,
                (SELECT count(*) FROM workflow_runs
                    WHERE status = 'running')::int                           AS active_runs,
                (SELECT avg(total_cost_usd)::float FROM recent_runs
                    WHERE status = 'success')                                AS avg_cost_usd,
                (SELECT count(*) FILTER (WHERE qualified)::float
                        / NULLIF(count(*), 0)
                    FROM qual)                                               AS qualified_rate
            """,
        )
        kpis = KPIs(**dict(kpi_row))

        # Timeseries ────────────────────────────────────────────
        ts_rows = await conn.fetch(
            """
            WITH days AS (
                SELECT generate_series(
                    date_trunc('day', NOW()) - INTERVAL '6 days',
                    date_trunc('day', NOW()),
                    INTERVAL '1 day'
                )::date AS day
            )
            SELECT
                d.day::text AS day,
                count(wr.id)::int                          AS runs,
                count(*) FILTER (WHERE q.qualified IS TRUE)::int AS qualified,
                avg(wr.total_cost_usd)::float              AS avg_cost
            FROM days d
            LEFT JOIN workflow_runs wr
                ON date_trunc('day', wr.created_at)::date = d.day
            LEFT JOIN qualifications q ON q.run_id = wr.id
            GROUP BY d.day
            ORDER BY d.day
            """,
        )
        timeseries = [TimeseriesPoint(**dict(r)) for r in ts_rows]

        # Top recent leads ──────────────────────────────────────
        top_rows = await conn.fetch(
            """
            SELECT
                l.id            AS lead_id,
                l.input_url     AS input_url,
                l.created_at    AS created_at,
                c.domain        AS domain,
                c.industry      AS industry,
                wr.id           AS run_id,
                wr.status::text AS run_status,
                q.composite_score AS composite,
                q.qualified     AS qualified,
                ed.subject      AS email_subject
            FROM leads l
            LEFT JOIN companies c ON c.id = l.company_id
            LEFT JOIN LATERAL (
                SELECT id, status FROM workflow_runs
                WHERE lead_id = l.id ORDER BY created_at DESC LIMIT 1
            ) wr ON TRUE
            LEFT JOIN qualifications q ON q.run_id = wr.id
            LEFT JOIN LATERAL (
                SELECT subject FROM email_drafts
                WHERE run_id = wr.id ORDER BY created_at DESC LIMIT 1
            ) ed ON TRUE
            ORDER BY l.created_at DESC
            LIMIT 10
            """,
        )
        top_leads = [
            TopLead(
                lead_id=r["lead_id"],
                input_url=r["input_url"],
                domain=r["domain"],
                industry=r["industry"],
                run_id=r["run_id"],
                run_status=r["run_status"],
                composite=float(r["composite"]) if r["composite"] is not None else None,
                qualified=r["qualified"],
                email_subject=r["email_subject"],
                created_at=r["created_at"],
            )
            for r in top_rows
        ]

        # Alerts ────────────────────────────────────────────────
        alert_rows = await conn.fetch(
            """
            SELECT id, severity::text AS severity,
                   title, body, source, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 10
            """,
        )
        alerts = [AlertRow(**dict(r)) for r in alert_rows]

    return DashboardSummary(
        kpis=kpis,
        timeseries=timeseries,
        top_leads=top_leads,
        alerts=alerts,
    )
