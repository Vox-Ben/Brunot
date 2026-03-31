from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

import httpx


@dataclass
class HttpResponse:
    status_code: int
    reason_phrase: str
    headers: Mapping[str, str]
    body: str
    elapsed_ms: float


def send_request(
    method: str,
    url: str,
    headers: Optional[Mapping[str, str]] = None,
    params: Optional[Mapping[str, str]] = None,
    body: Optional[str] = None,
    timeout: float = 30.0,
) -> HttpResponse:
    """Execute a basic HTTP request and return a simplified response."""
    headers = dict(headers or {})
    params = dict(params or {})

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.request(method=method.upper(), url=url, headers=headers, params=params, content=body)

    return HttpResponse(
        status_code=resp.status_code,
        reason_phrase=resp.reason_phrase,
        headers=dict(resp.headers),
        body=resp.text,
        elapsed_ms=resp.elapsed.total_seconds() * 1000.0,
    )

