"""Draft a personalized outreach email with inline citation markers.

The model is asked to put `[research.<field>]` markers next to every
fact it references. Those markers are parsed server-side after the
response so we don't trust the model to *also* list them in a
separate field.

Citation markers are validated against the actual research payload's
top-level keys -- markers pointing at fields not in the payload are
treated as hallucinations and downscore the eval gate (step 12).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from openai import AsyncOpenAI

from app.logging import get_logger
from app.qualify.score import DEFAULT_PITCH
from app.settings import settings
from app.spend_tracker import calc_cost


log = get_logger(__name__)


Tone = Literal["technical", "executive", "casual"]
ALLOWED_TONES: tuple[Tone, ...] = ("technical", "executive", "casual")
DEFAULT_TONE: Tone = "executive"

# Top-level keys we expect in a research_results.payload. Markers
# referencing anything outside this list are flagged.
KNOWN_FIELDS = {
    "industry", "size_estimate", "tech_stack", "recent_news",
    "key_people", "headline", "summary",
}


# ─── Result ──────────────────────────────────────────────────────


@dataclass
class EmailDraft:
    subject:        str
    body:           str
    tone:           Tone
    cited_findings: list[str]      # ['research.headline', 'research.key_people', ...]
    unknown_citations: list[str]   # markers that referenced fields we don't expose
    model:          str
    tokens_in:      int
    tokens_out:     int
    cost_usd:       float


# ─── Prompts ─────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are a B2B SDR drafting cold outreach. You'll \
receive a research profile, a BANT qualification scorecard, our \
product pitch, and a target tone. Produce a personalized email.

CITATION RULES (strict):
- Reference specific facts from the research profile. After each \
fact, add an inline citation marker in this exact format:
  [research.<field>]
  where <field> is the JSON key that supports the claim. Valid fields:
  industry, size_estimate, tech_stack, recent_news, key_people, \
headline, summary.
- Multiple supporting fields: [research.headline][research.summary].
- Do NOT invent field names outside that list.
- Do NOT add other source notation (no [1], no parentheses, no \
"according to..."). Citations live ONLY in the [research.X] markers.

CONTENT RULES:
- Length: 3-4 short paragraphs. Under 150 words.
- Subject: 6-10 words. Reference ONE concrete fact (a metric, a \
named person, the headline).
- Tone variants:
    technical -- specific, engineer-friendly, lean on tech_stack and \
                 concrete numbers. Light on adjectives.
    executive -- direct, time-respecting, lead with a metric or a \
                 named person. No fluff.
    casual    -- warm, human, still business-appropriate.
- If the qualification scorecard shows NOT qualified \
(composite < 0.6), acknowledge the uncertainty in the email -- \
don't pretend the company is a perfect fit. A short, low-pressure \
"would this be useful?" framing is appropriate.
- Open with a fact from the research, NOT "I hope this finds you \
well" boilerplate.

Output JSON ONLY -- no commentary."""


_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "outreach_email",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["subject", "body"],
            "properties": {
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
        },
    },
}


def _build_user_prompt(
    *,
    profile:      dict[str, Any],
    qualification: dict[str, Any] | None,
    pitch:        str,
    tone:         Tone,
) -> str:
    parts: list[str] = []
    parts.append(f"PITCH:\n{pitch.strip()}")
    parts.append("")
    parts.append("RESEARCH PROFILE:")
    parts.append(json.dumps(profile, indent=2, ensure_ascii=False))
    parts.append("")
    if qualification is not None:
        parts.append("BANT QUALIFICATION:")
        parts.append(json.dumps(qualification, indent=2, ensure_ascii=False))
        parts.append("")
    parts.append(f"TONE: {tone}")
    parts.append("")
    parts.append("Write the email now.")
    return "\n".join(parts)


# ─── Citation parsing ───────────────────────────────────────────


_CITATION_RE = re.compile(r"\[research\.([a-z_][a-z0-9_]*)\]", re.IGNORECASE)


def parse_citations(body: str) -> tuple[list[str], list[str]]:
    """Pull `[research.<field>]` markers out of an email body.

    Returns ``(known, unknown)`` -- two lists of field names. ``known``
    are markers that match a top-level key in our research payload;
    ``unknown`` are model hallucinations we want to flag in eval.
    """
    seen: list[str] = []
    seen_lower: set[str] = set()
    for m in _CITATION_RE.finditer(body):
        field = m.group(1).lower()
        if field not in seen_lower:
            seen.append(field)
            seen_lower.add(field)

    known   = [f for f in seen if f in KNOWN_FIELDS]
    unknown = [f for f in seen if f not in KNOWN_FIELDS]
    return known, unknown


# ─── Public API ──────────────────────────────────────────────────


_async_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _async_client


async def draft_email(
    *,
    profile:       dict[str, Any],
    qualification: dict[str, Any] | None = None,
    pitch:         str | None = None,
    tone:          Tone = DEFAULT_TONE,
    model:         str | None = None,
) -> EmailDraft:
    """Generate one personalized outreach draft."""
    if tone not in ALLOWED_TONES:
        raise ValueError(f"unknown tone: {tone!r}; allowed: {ALLOWED_TONES}")

    pitch = pitch or DEFAULT_PITCH
    model = model or settings.generator_model

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_prompt(
                profile=profile, qualification=qualification,
                pitch=pitch, tone=tone,
            )},
        ],
        response_format=_RESPONSE_SCHEMA,
        temperature=0.4,
        max_tokens=600,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.error("personalize.bad_json", error=str(exc))
        data = {"subject": "(unable to draft)", "body": ""}

    body    = str(data.get("body", "")).strip()
    subject = str(data.get("subject", "")).strip()

    known, unknown = parse_citations(body)

    tokens_in  = (resp.usage.prompt_tokens     if resp.usage else 0) or 0
    tokens_out = (resp.usage.completion_tokens if resp.usage else 0) or 0

    return EmailDraft(
        subject=subject,
        body=body,
        tone=tone,
        cited_findings=[f"research.{f}" for f in known],
        unknown_citations=[f"research.{f}" for f in unknown],
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=calc_cost(model, tokens_in, tokens_out),
    )
