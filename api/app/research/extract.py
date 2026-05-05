"""LLM extraction of a structured company profile.

Single OpenAI call with a strict JSON-schema response format. The
prompt is explicit about ONLY using the supplied content -- no general
knowledge, no fabrication. The schema requires every field so
``additionalProperties: false`` doesn't bite us at decode time.

Public entry: ``extract_profile(domain, url, page_text, search_hits)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import re
import tiktoken
from openai import AsyncOpenAI
from selectolax.parser import HTMLParser

from app.logging import get_logger
from app.settings import settings
from app.spend_tracker import calc_cost


log = get_logger(__name__)

# Approx token budget for the user prompt (page text + search snippets).
# gpt-4o-mini handles 128k context; capping keeps cost per call sub-cent.
_MAX_PROMPT_TOKENS = 8_000

_encoder = tiktoken.get_encoding("o200k_base")  # matches gpt-4o family


# ─── Result ──────────────────────────────────────────────────────


@dataclass
class ResearchResult:
    payload:    dict[str, Any]
    summary:    str | None
    model:      str
    tokens_in:  int
    tokens_out: int
    cost_usd:   float
    raw_text:   str          # text the LLM saw (for debugging / replay)


# ─── HTML -> readable text ───────────────────────────────────────


_NOISE_TAGS = ("script", "style", "noscript", "head", "meta", "link")


def html_to_text(html: bytes) -> str:
    """Strip noisy tags, return readable text with paragraph breaks."""
    text = html.decode("utf-8", errors="replace")
    tree = HTMLParser(text)
    for sel in _NOISE_TAGS:
        for n in tree.css(sel):
            n.decompose()
    body = tree.body or tree.root
    raw = body.text(separator="\n", deep=True) if body else ""

    raw = re.sub(r"[ \t\xa0]+", " ", raw)
    raw = re.sub(r" *\n *", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Cut a string down to a token budget. Cheap O(n) -- no recursion."""
    ids = _encoder.encode(text)
    if len(ids) <= max_tokens:
        return text
    return _encoder.decode(ids[:max_tokens])


# ─── Prompts ─────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are a B2B research analyst. Given a company's \
homepage content (and optionally supplementary web-search results), \
extract a structured profile that a sales rep would use to qualify and \
personalize outreach.

Rules:
- Use ONLY facts visible in the supplied content. If a field isn't \
supported, return null (or [] for arrays). Do not guess, do not use \
general knowledge about the company.
- "industry" is a concise category like 'fintech', 'devtools', \
'enterprise SaaS', 'hardware'. NOT a marketing tagline.
- "size_estimate" is one of: '1-10', '11-50', '51-200', '201-1000', \
'1000+', or null if there's no signal.
- "tech_stack": only technologies explicitly mentioned (e.g. job \
postings naming React, "Powered by Stripe" badges, public SDK names). \
Don't infer.
- "recent_news": items mentioned in the page (press, blog highlights, \
"in the news" sections). Each item needs title, url, summary.
- "key_people": founders / executives mentioned by NAME and ROLE.
- "headline": ONE sentence describing what the company does.
- "summary": 2-3 sentences a sales rep would actually use as context.

Output JSON ONLY -- no commentary."""


_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "company_profile",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "industry", "size_estimate", "tech_stack",
                "recent_news", "key_people", "headline", "summary",
            ],
            "properties": {
                "industry":      {"type": ["string", "null"]},
                "size_estimate": {"type": ["string", "null"]},
                "tech_stack":    {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "recent_news": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title", "url", "summary"],
                        "properties": {
                            "title":   {"type": "string"},
                            "url":     {"type": ["string", "null"]},
                            "summary": {"type": ["string", "null"]},
                        },
                    },
                },
                "key_people": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name", "role"],
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": ["string", "null"]},
                        },
                    },
                },
                "headline": {"type": ["string", "null"]},
                "summary":  {"type": ["string", "null"]},
            },
        },
    },
}


def _build_user_prompt(
    domain: str,
    url: str,
    page_text: str,
    search_hits: list,
) -> str:
    parts: list[str] = [f"COMPANY: {domain}", f"URL: {url}", ""]
    parts.append("PAGE CONTENT:")
    parts.append(page_text)
    parts.append("")
    if search_hits:
        parts.append("SEARCH RESULTS (supplementary):")
        for i, h in enumerate(search_hits, 1):
            parts.append(f"[{i}] {h.title}")
            parts.append(f"    {h.url}")
            if h.description:
                parts.append(f"    {h.description}")
        parts.append("")
    return "\n".join(parts)


# ─── Public API ──────────────────────────────────────────────────


_async_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _async_client


async def extract_profile(
    *,
    domain:      str,
    url:         str,
    page_text:   str,
    search_hits: list,
    model:       str | None = None,
) -> ResearchResult:
    """Run the LLM extraction. Caller has already done web fetch + search."""
    model = model or settings.generator_model

    # Reserve some budget for the system prompt + JSON output.
    user_prompt = _build_user_prompt(domain, url, page_text, search_hits)
    user_prompt = _truncate_to_tokens(user_prompt, _MAX_PROMPT_TOKENS)

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        response_format=_RESPONSE_SCHEMA,
        temperature=0.0,
        max_tokens=1500,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        log.error("research.bad_json", error=str(exc))
        payload = {
            "industry": None, "size_estimate": None, "tech_stack": [],
            "recent_news": [], "key_people": [],
            "headline": None, "summary": f"extraction failed: {exc}",
        }

    tokens_in  = (resp.usage.prompt_tokens     if resp.usage else 0) or 0
    tokens_out = (resp.usage.completion_tokens if resp.usage else 0) or 0
    cost = calc_cost(model, tokens_in, tokens_out)

    return ResearchResult(
        payload=payload,
        summary=payload.get("summary"),
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        raw_text=user_prompt,
    )
