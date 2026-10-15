"""Small shared HTTP helpers for connectors."""

import re
from typing import Optional
from urllib.parse import quote

import httpx

from app.services.platform.errors import RateLimitedError, UpstreamUnavailableError

USER_AGENT = "KnowledgeMesh/1.0 (+https://github.com/mohittzz2008/knowledge-mesh)"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Conservative superset of what Codewars / GeeksforGeeks / CodeChef accept as handles.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")


def clean_handle(identifier: Optional[str]) -> Optional[str]:
    """Return a trimmed handle that is safe to put in a URL path, or None."""
    if not identifier:
        return None
    handle = identifier.strip()
    return handle if _HANDLE_RE.match(handle) else None


def path_segment(value: str) -> str:
    """Percent-encode a value for use as a single URL path segment."""
    return quote(value, safe="")


def make_client(
    transport: Optional[httpx.AsyncBaseTransport] = None,
    headers: Optional[dict[str, str]] = None,
) -> httpx.AsyncClient:
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    return httpx.AsyncClient(
        headers=merged,
        timeout=DEFAULT_TIMEOUT,
        transport=transport,
        follow_redirects=True,
    )


async def get(
    client: httpx.AsyncClient, url: str, *, platform: str, **kwargs
) -> httpx.Response:
    """GET with failures mapped to typed connector errors.

    404 is returned to the caller (it usually means "no such user"); 429 and
    5xx and network failures raise.
    """
    try:
        response = await client.get(url, **kwargs)
    except httpx.TimeoutException as err:
        raise UpstreamUnavailableError(f"{platform} timed out.", platform=platform) from err
    except httpx.RequestError as err:
        raise UpstreamUnavailableError(
            f"Could not reach {platform}: {err.__class__.__name__}.", platform=platform
        ) from err

    if response.status_code == 429:
        raise RateLimitedError(
            f"{platform} rate limit reached. Please try again in a minute.",
            platform=platform,
        )
    if response.status_code >= 500:
        raise UpstreamUnavailableError(
            f"{platform} is temporarily unavailable (HTTP {response.status_code}).",
            platform=platform,
        )
    return response
