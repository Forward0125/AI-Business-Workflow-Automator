"""Lead intake.

Given a visitor-supplied URL, this module:

  1. Validates the URL and ensures it doesn't resolve to a private IP
     (SSRF guard lives in app.fetch).
  2. Fetches the homepage with size + time caps.
  3. Pulls a few cheap-to-extract fields (page title, meta description,
     canonical URL) -- the LLM-driven structured extraction comes
     later in the research step.
  4. Upserts a row into ``companies`` keyed by domain.
  5. Inserts a row into ``leads`` referencing the company.
  6. Caches the raw HTML to ``data/raw/<domain>/<sha256>.html`` so
     step 7's research can re-read it without a second fetch.

Returns a small summary dict the API hands back to the caller.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selectolax.parser import HTMLParser

from app import db
from app.fetch import FetchResult, fetch, normalize_domain
from app.logging import get_logger
from app.settings import PROJECT_ROOT


log = get_logger(__name__)


CACHE_DIR = PROJECT_ROOT / "data" / "raw"


# ─── Result ──────────────────────────────────────────────────────


@dataclass
class LeadIntakeResult:
    lead_id:       int
    company_id:    int
    domain:        str
    final_url:     str
    title:         str | None
    description:   str | None
    fetched_bytes: int
    elapsed_ms:    int
    cache_path:    str           # repo-relative


# ─── Cheap HTML field extraction ─────────────────────────────────


def _extract_metadata(html: bytes) -> tuple[str | None, str | None, str | None]:
    """Return (title, description, canonical) -- all optional."""
    try:
        # Decode best-effort. The LLM step will deal with text proper.
        text = html.decode("utf-8", errors="replace")
    except Exception:
        return None, None, None

    tree = HTMLParser(text)

    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else None

    description: str | None = None
    for sel in ('meta[name="description"]', 'meta[property="og:description"]'):
        node = tree.css_first(sel)
        if node:
            content = (node.attributes.get("content") or "").strip()
            if content:
                description = content
                break

    canonical: str | None = None
    canon_node = tree.css_first('link[rel="canonical"]')
    if canon_node:
        canonical = (canon_node.attributes.get("href") or "").strip() or None

    return title, description, canonical


# ─── Cache to disk ───────────────────────────────────────────────


def _cache_html(domain: str, content: bytes) -> Path:
    """Write the raw HTML to data/raw/<domain>/<sha>.html. Returns the path."""
    digest = hashlib.sha256(content).hexdigest()[:16]
    out_dir = CACHE_DIR / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{digest}.html"
    if not path.exists():
        path.write_bytes(content)
    return path


# ─── DB upserts ──────────────────────────────────────────────────


async def _upsert_company(domain: str, *, name: str | None) -> int:
    async with db.get_conn() as conn:
        return await conn.fetchval(
            """
            INSERT INTO companies (domain, name)
            VALUES ($1, $2)
            ON CONFLICT (domain) DO UPDATE SET
                name       = COALESCE(companies.name, EXCLUDED.name),
                updated_at = NOW()
            RETURNING id
            """,
            domain, name,
        )


async def _insert_lead(
    *,
    company_id: int,
    input_url:  str,
    ip_address: str | None,
    user_agent: str | None,
) -> int:
    async with db.get_conn() as conn:
        return await conn.fetchval(
            """
            INSERT INTO leads (company_id, input_url, input_kind, ip_address, user_agent)
            VALUES ($1, $2, 'url', $3, $4)
            RETURNING id
            """,
            company_id, input_url, ip_address, user_agent,
        )


# ─── Public API ──────────────────────────────────────────────────


async def intake_lead(
    url:        str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LeadIntakeResult:
    """Run the full lead-intake flow on ``url``."""
    # 1. Fetch with caps + SSRF guard.
    fetched: FetchResult = await fetch(url)

    # 2. Pull cheap metadata.
    title, description, _canonical = _extract_metadata(fetched.content)

    # 3. Normalize domain.
    domain = normalize_domain(fetched.url)
    if not domain:
        domain = normalize_domain(url) or "unknown.invalid"

    # 4. Cache to disk so step 7 doesn't re-fetch.
    cache_path = _cache_html(domain, fetched.content)

    # 5. Upsert company (name will be improved by the research step).
    company_id = await _upsert_company(domain, name=title)

    # 6. Insert lead row.
    lead_id = await _insert_lead(
        company_id=company_id,
        input_url=url,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    rel = str(cache_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    log.info(
        "lead.ingested",
        lead_id=lead_id, company_id=company_id, domain=domain,
        bytes=fetched.fetched_bytes, ms=fetched.elapsed_ms,
    )

    return LeadIntakeResult(
        lead_id=lead_id,
        company_id=company_id,
        domain=domain,
        final_url=fetched.url,
        title=title,
        description=description,
        fetched_bytes=fetched.fetched_bytes,
        elapsed_ms=fetched.elapsed_ms,
        cache_path=rel,
    )


# Tiny convenience for the API layer.
def to_summary(r: LeadIntakeResult) -> dict[str, Any]:
    return {
        "lead_id":       r.lead_id,
        "company_id":    r.company_id,
        "domain":        r.domain,
        "final_url":     r.final_url,
        "title":         r.title,
        "description":   r.description,
        "fetched_bytes": r.fetched_bytes,
        "elapsed_ms":    r.elapsed_ms,
        "cache_path":    r.cache_path,
    }
