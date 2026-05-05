"""Safe HTTP fetcher for visitor-supplied URLs.

Used by the research step to fetch a company's homepage. Visitor input
flows through here, so we have to be paranoid:

  1. Only http/https schemes
  2. Reject hosts that resolve to private/loopback/link-local IPs
     (SSRF protection -- we don't want a visitor pasting
     http://169.254.169.254 to read EC2 metadata, etc.)
  3. Hard cap on response size (default 5 MB)
  4. Hard cap on connection + read time (default 30 s)
  5. Drop binary content types -- we only want HTML/text

Returns the raw bytes plus a few cheap-to-derive metadata fields.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)


# ─── Errors ──────────────────────────────────────────────────────


class FetchError(Exception):
    """Base class for fetch-time failures with a user-safe message."""


class InvalidURLError(FetchError):
    pass


class BlockedHostError(FetchError):
    pass


class TooLargeError(FetchError):
    pass


# ─── Result ──────────────────────────────────────────────────────


@dataclass
class FetchResult:
    url:           str          # final URL after redirects
    status_code:   int
    content:       bytes
    content_type:  str
    fetched_bytes: int
    elapsed_ms:    int


# ─── URL validation ──────────────────────────────────────────────


_ALLOWED_SCHEMES = {"http", "https"}


def _validate_url(raw: str) -> str:
    """Normalize a URL and reject obvious nonsense.

    Returns the normalized URL string. Raises InvalidURLError on bad
    input.
    """
    raw = raw.strip()
    if not raw:
        raise InvalidURLError("URL is empty")

    # If the user typed an explicit scheme, honor it (and reject if
    # it's something other than http/https). Otherwise, prepend https.
    # Without this branch, "file:///etc/passwd" would get mangled into
    # "https://file:///etc/passwd" and then fail at DNS time.
    if "://" in raw:
        explicit = raw.split("://", 1)[0].lower()
        if explicit not in _ALLOWED_SCHEMES:
            raise InvalidURLError(f"unsupported URL scheme: {explicit!r}")
    else:
        raw = "https://" + raw

    parsed = urlparse(raw)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise InvalidURLError(f"unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise InvalidURLError("URL is missing a hostname")
    return raw


# ─── SSRF guard ──────────────────────────────────────────────────


async def _resolve_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a hostname to all of its IPs (sync DNS, run in a thread)."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.run_in_executor(
            None, lambda: socket.getaddrinfo(host, None, type=socket.SOCK_STREAM),
        )
    except socket.gaierror as exc:
        raise BlockedHostError(f"could not resolve host: {host!r} ({exc})") from exc

    out: list = []
    for family, _socktype, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if family in (socket.AF_INET, socket.AF_INET6):
            out.append(ip)
    return out


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True if this IP must NOT be fetched server-side."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def _ensure_safe_host(url: str) -> None:
    host = urlparse(url).hostname
    if host is None:
        raise InvalidURLError("URL is missing a hostname")

    # Localhost short-circuit -- don't even bother with DNS.
    if host.lower() in {"localhost", "ip6-localhost", "ip6-loopback"}:
        raise BlockedHostError(f"blocked host: {host}")

    ips = await _resolve_ips(host)
    if not ips:
        raise BlockedHostError(f"could not resolve host: {host}")
    bad = [ip for ip in ips if _is_blocked_ip(ip)]
    if bad:
        raise BlockedHostError(
            f"host {host} resolves to blocked IP(s): {', '.join(str(b) for b in bad)}"
        )


# ─── Public API ──────────────────────────────────────────────────


def normalize_domain(url: str) -> str:
    """Extract a canonical domain from a URL: 'https://www.Stripe.com/' -> 'stripe.com'."""
    host = urlparse(url).hostname or ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


async def fetch(url: str) -> FetchResult:
    """Fetch ``url`` with size + time caps and SSRF protection.

    Raises FetchError subclasses on validation / network failures.
    """
    import time as _time

    normalized = _validate_url(url)
    await _ensure_safe_host(normalized)

    headers = {"User-Agent": settings.http_user_agent, "Accept": "text/html,*/*;q=0.5"}
    timeout = httpx.Timeout(settings.fetch_timeout_seconds)
    limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)

    started = _time.perf_counter()
    async with httpx.AsyncClient(
        headers=headers, timeout=timeout, limits=limits, follow_redirects=True,
        max_redirects=5,
    ) as client:
        try:
            async with client.stream("GET", normalized) as resp:
                content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                # Only allow text-y content. Reject videos, PDFs, etc.
                if content_type and not (
                    content_type.startswith("text/") or content_type in {
                        "application/xhtml+xml", "application/xml", "application/json",
                    }
                ):
                    raise InvalidURLError(
                        f"unsupported content type: {content_type!r}",
                    )

                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > settings.max_fetch_bytes:
                        raise TooLargeError(
                            f"response exceeded {settings.max_fetch_bytes} bytes",
                        )

                final_url = str(resp.url)
                # If the final URL hostname differs from the initial (e.g.
                # via a redirect), re-check the safe-host rule.
                if urlparse(final_url).hostname != urlparse(normalized).hostname:
                    await _ensure_safe_host(final_url)

                return FetchResult(
                    url=final_url,
                    status_code=resp.status_code,
                    content=bytes(buf),
                    content_type=content_type or "text/html",
                    fetched_bytes=len(buf),
                    elapsed_ms=int((_time.perf_counter() - started) * 1000),
                )
        except (httpx.HTTPError, httpx.NetworkError) as exc:
            raise FetchError(f"network error: {exc}") from exc
