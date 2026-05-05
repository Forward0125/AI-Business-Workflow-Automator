"""Workflows endpoints.

  POST /workflows/runs                     -> kick off a pipeline,
                                              return run_id immediately
  GET  /workflows/runs/{run_id}            -> snapshot of run + steps
  GET  /workflows/runs/{run_id}/events     -> SSE stream of live events
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import pipeline
from app.jobs import END_EVENT, broker
from app.logging import get_logger
from app.personalize.draft import ALLOWED_TONES, DEFAULT_TONE
from app.rate_limit import leads_limiter
from app.runs import state
from app.spend_tracker import tracker as spend_tracker


log = get_logger(__name__)
router = APIRouter(prefix="/workflows", tags=["workflows"])


# ─── Schemas ─────────────────────────────────────────────────────


class CreateRunBody(BaseModel):
    url:   str = Field(..., min_length=4, max_length=2048)
    tone:  Literal["technical", "executive", "casual"] = DEFAULT_TONE
    pitch: str | None = Field(default=None, max_length=2000)


class CreateRunResponse(BaseModel):
    run_id: int


class StepInfo(BaseModel):
    name:         str
    status:       str
    progress_pct: int
    started_at:   Any | None = None
    finished_at:  Any | None = None
    metadata:     Any | None = None


class RunInfo(BaseModel):
    id:                int
    lead_id:           int | None = None
    status:            str
    triggered_by:      str | None = None
    started_at:        Any | None = None
    finished_at:       Any | None = None
    total_cost_usd:    float | None = None
    total_tokens_in:   int
    total_tokens_out:  int
    error_message:     str | None = None
    steps:             list[StepInfo]


# ─── Endpoints ───────────────────────────────────────────────────


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunBody, request: Request) -> CreateRunResponse:
    """Kick off a pipeline. Throttled per-IP, gated by daily spend cap."""
    if body.tone not in ALLOWED_TONES:
        raise HTTPException(400, f"unknown tone: {body.tone!r}")

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent")

    allowed, _remaining = leads_limiter.check(ip)
    if not allowed:
        raise HTTPException(
            429,
            "rate limit reached -- 5 workflow runs per hour per IP",
        )
    if not spend_tracker.under_cap():
        raise HTTPException(
            503,
            "daily OpenAI spend cap reached -- service resumes at UTC midnight",
        )

    run_id = await pipeline.start_pipeline(
        url=body.url, tone=body.tone, pitch=body.pitch,
        ip=ip, ua=ua, triggered_by="visitor",
    )
    log.info("workflows.run.created", run_id=run_id, url=body.url, ip=ip)
    return CreateRunResponse(run_id=run_id)


@router.get("/runs/{run_id}", response_model=RunInfo)
async def get_run(run_id: int) -> RunInfo:
    row = await state.get_run(run_id)
    if row is None:
        raise HTTPException(404, f"run {run_id} not found")

    # JSONB step.metadata may come back as str -- coerce to dict.
    for step in row["steps"]:
        meta = step.get("metadata")
        if isinstance(meta, str):
            try:
                step["metadata"] = json.loads(meta)
            except json.JSONDecodeError:
                pass
    if row.get("total_cost_usd") is not None:
        row["total_cost_usd"] = float(row["total_cost_usd"])
    return RunInfo(**row)


def _sse(event: dict[str, Any]) -> str:
    name = event.get("type", "message")
    return f"event: {name}\ndata: {json.dumps(event, default=str)}\n\n"


def _maybe_json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return v
    return v


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: int, request: Request) -> StreamingResponse:
    """SSE: replay current state on connect, then forward live events."""
    snapshot = await state.get_run(run_id)
    if snapshot is None:
        raise HTTPException(404, f"run {run_id} not found")

    queue = broker.subscribe(run_id)

    async def event_gen() -> AsyncGenerator[str, None]:
        # Replay state.
        yield _sse({
            "type": "snapshot",
            "run":  {**snapshot, "steps": [
                {**s, "metadata": _maybe_json(s.get("metadata"))}
                for s in snapshot["steps"]
            ]},
        })

        try:
            while True:
                if await request.is_disconnected():
                    log.info("workflows.sse.disconnected", run_id=run_id)
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                if event is END_EVENT or event.get("type") == "stream.end":
                    yield _sse({"type": "stream.end"})
                    break

                yield _sse(event)
        finally:
            broker.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
