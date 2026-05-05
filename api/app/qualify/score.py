"""BANT scoring with LLM-as-judge.

Single gpt-4o-mini call with strict JSON-schema response format. The
prompt tells the model to err LOW when evidence is weak -- this is a
pre-sales qualifier, not a marketing tool, so false positives waste
the rep's time.

Composite score is computed in Python (equal-weighted mean). Threshold
for ``qualified`` defaults to 0.6 -- tunable via the keyword arg.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.logging import get_logger
from app.settings import settings
from app.spend_tracker import calc_cost


log = get_logger(__name__)


# v1 hardcoded pitch. In step 11 the visitor will be able to override
# this from the lead form (so the demo can show "vs. our actual product"
# fit, not just our default).
DEFAULT_PITCH = (
    "We sell sales-automation tooling that turns inbound leads into "
    "qualified pipeline: automated research, BANT scoring, and "
    "personalized outreach drafts. Target customers are mid-market and "
    "enterprise B2B SaaS sales orgs of 50+ reps."
)

DEFAULT_QUALIFIED_THRESHOLD = 0.6


# ─── Result ──────────────────────────────────────────────────────


@dataclass
class BANTScore:
    budget:    float
    authority: float
    need:      float
    timing:    float
    composite: float
    qualified: bool
    reasoning: str
    model:     str
    tokens_in: int
    tokens_out: int
    cost_usd:  float


# ─── Prompt ──────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are a B2B sales qualifier. Given a company \
profile (extracted from the company's homepage and possibly web \
search) and a vendor's product pitch, score how qualified this lead \
is on the BANT framework:

- BUDGET (B):    Can the company plausibly afford the product? \
                 Look at company size, funding signals, paid \
                 platforms they advertise.
- AUTHORITY (A): Can a decision-maker be reached or identified? \
                 Look at named executives in the profile, public \
                 contact info, role mentions.
- NEED (N):      Does the vendor's pitch solve a problem this \
                 company likely has? Look at industry, tech_stack, \
                 mentioned use cases.
- TIMING (T):    Is now a likely buying window? Look at recent_news \
                 (funding, hiring, launches, expansion) -- if no \
                 timing signal, score low.

Each score is 0.0 - 1.0. Be HONEST and ERR LOW when the profile \
doesn't directly support the score. 1.0 means "compelling evidence \
in the profile", not "plausible". 0.5 is "weak signal both ways". \
0.0 is "evidence against".

reasoning: 2-3 sentences. Cite specific findings from the profile \
when scoring. Do NOT generalize from outside knowledge.

Output JSON ONLY -- no commentary."""


_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "bant_scoring",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["budget", "authority", "need", "timing", "reasoning"],
            "properties": {
                "budget":    {"type": "number"},
                "authority": {"type": "number"},
                "need":      {"type": "number"},
                "timing":    {"type": "number"},
                "reasoning": {"type": "string"},
            },
        },
    },
}


def _build_user_prompt(profile: dict[str, Any], pitch: str) -> str:
    parts: list[str] = []
    parts.append("VENDOR PITCH:")
    parts.append(pitch.strip())
    parts.append("")
    parts.append("COMPANY PROFILE (from research):")
    parts.append(json.dumps(profile, indent=2, ensure_ascii=False))
    parts.append("")
    parts.append("Score this lead on BANT.")
    return "\n".join(parts)


# ─── Public API ──────────────────────────────────────────────────


_async_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _async_client


def _clamp(x: Any) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


async def score_bant(
    *,
    profile: dict[str, Any],
    pitch:   str | None = None,
    model:   str | None = None,
    threshold: float = DEFAULT_QUALIFIED_THRESHOLD,
) -> BANTScore:
    """Score a lead's research profile against a pitch using LLM-as-judge."""
    pitch = pitch or DEFAULT_PITCH
    model = model or settings.generator_model

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_prompt(profile, pitch)},
        ],
        response_format=_RESPONSE_SCHEMA,
        temperature=0.0,
        max_tokens=400,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.error("qualify.bad_json", error=str(exc))
        data = {
            "budget": 0.0, "authority": 0.0, "need": 0.0, "timing": 0.0,
            "reasoning": f"scoring failed: {exc}",
        }

    b, a, n, t = (
        _clamp(data.get("budget")),
        _clamp(data.get("authority")),
        _clamp(data.get("need")),
        _clamp(data.get("timing")),
    )
    composite = round((b + a + n + t) / 4, 4)

    tokens_in  = (resp.usage.prompt_tokens     if resp.usage else 0) or 0
    tokens_out = (resp.usage.completion_tokens if resp.usage else 0) or 0

    return BANTScore(
        budget=b, authority=a, need=n, timing=t,
        composite=composite,
        qualified=composite >= threshold,
        reasoning=str(data.get("reasoning", ""))[:1000],
        model=model,
        tokens_in=tokens_in, tokens_out=tokens_out,
        cost_usd=calc_cost(model, tokens_in, tokens_out),
    )
