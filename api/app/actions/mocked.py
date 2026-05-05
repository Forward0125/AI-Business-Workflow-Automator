"""Mocked SaaS actions -- believable fake JSON, no real API calls.

Each action sleeps ~300-700ms before returning so the UI's DAG
animation doesn't snap through these instantly. The payload looks
like what HubSpot / Calendly / SendGrid would actually return, with
``demo_mode: true`` flags so a viewer is never misled.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app import db
from app.logging import get_logger


log = get_logger(__name__)


@dataclass
class ActionResult:
    action:      str           # 'crm_update' / 'calendar_book' / 'email_send'
    payload:     dict[str, Any]
    duration_ms: int


# ─── Persistence ────────────────────────────────────────────────


async def persist(run_id: int, result: ActionResult) -> int:
    async with db.get_conn() as conn:
        return await conn.fetchval(
            """
            INSERT INTO mocked_actions (run_id, action, payload)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id
            """,
            run_id, result.action, json.dumps(result.payload),
        )


# ─── Helpers ─────────────────────────────────────────────────────


def _hash_id(*parts: str, length: int = 10) -> str:
    h = hashlib.sha1("|".join(parts).encode()).hexdigest()
    return h[:length]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# ─── Actions ────────────────────────────────────────────────────


async def crm_update(
    *,
    company_id:   int,
    domain:       str,
    qualified:    bool,
    composite:    float,
    industry:     str | None,
    size_estimate: str | None,
) -> ActionResult:
    """Pretend to push the lead into a HubSpot-shaped CRM."""
    duration_ms = 300 + random.randint(0, 200)
    await asyncio.sleep(duration_ms / 1000)

    contact_id = f"hubspot_contact_{_hash_id(domain, 'contact')}"
    deal_id    = f"hubspot_deal_{_hash_id(domain, 'deal')}"

    return ActionResult(
        action="crm_update",
        payload={
            "demo_mode":   True,
            "platform":    "HubSpot (simulated)",
            "contact_id":  contact_id,
            "deal_id":     deal_id,
            "company": {
                "domain":     domain,
                "industry":   industry,
                "size":       size_estimate,
            },
            "deal_stage":  "qualified" if qualified else "research",
            "score":       round(composite * 100),
            "owner":       "demo-rep@outreachlab.dev",
            "fields_set":  ["industry", "size", "qualification_score", "stage"],
            "synced_at":   _utc_now().isoformat(),
        },
        duration_ms=duration_ms,
    )


async def calendar_book(
    *,
    domain:        str,
    primary_contact: str | None,
) -> ActionResult:
    """Pretend to drop a Calendly-style 30-min slot on the rep's calendar."""
    duration_ms = 500 + random.randint(0, 300)
    await asyncio.sleep(duration_ms / 1000)

    # 7 business days out, 14:00 UTC -- a believable "intro call" slot.
    when = _utc_now() + timedelta(days=7)
    when = when.replace(hour=14, minute=0, second=0)

    invite_id = f"calendly_evt_{_hash_id(domain, 'cal')}"

    return ActionResult(
        action="calendar_book",
        payload={
            "demo_mode":        True,
            "platform":         "Calendly (simulated)",
            "event_id":         invite_id,
            "event_type":       "30min-intro-call",
            "scheduled_at":     when.isoformat(),
            "duration_minutes": 30,
            "attendees": [
                {"email": "demo-rep@outreachlab.dev", "role": "host"},
                {"email": primary_contact or f"contact@{domain}", "role": "guest"},
            ],
            "calendar_url":     f"https://calendly.example/sim/{invite_id}",
        },
        duration_ms=duration_ms,
    )


async def email_send(
    *,
    domain:           str,
    primary_contact:  str | None,
    subject:          str,
    body_preview:     str,
) -> ActionResult:
    """Pretend to enqueue the email through SendGrid for delayed send."""
    duration_ms = 400 + random.randint(0, 200)
    await asyncio.sleep(duration_ms / 1000)

    msg_id = f"sg_{_hash_id(domain, subject, 'email')}"
    scheduled = _utc_now() + timedelta(minutes=5)

    return ActionResult(
        action="email_send",
        payload={
            "demo_mode":     True,
            "platform":      "SendGrid (simulated)",
            "message_id":    msg_id,
            "to":            primary_contact or f"founder@{domain}",
            "from":          "demo-rep@outreachlab.dev",
            "subject":       subject,
            "preview":       (body_preview or "")[:200],
            "scheduled_at":  scheduled.isoformat(),
            "status":        "queued",
        },
        duration_ms=duration_ms,
    )
