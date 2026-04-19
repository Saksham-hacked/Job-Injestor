"""HTTP utilities for hospital_job_ingestor."""
from __future__ import annotations
from typing import Any, Optional
import httpx
from app.config import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT


def get_default_headers() -> dict[str, str]:
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def fetch_text(url: str, headers: Optional[dict] = None) -> tuple[str, str]:
    """Fetch a URL and return (text, final_url). Raises on non-2xx."""
    hdrs = {**get_default_headers(), **(headers or {})}
    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, headers=hdrs)
        resp.raise_for_status()
        return resp.text, str(resp.url)


def fetch_json(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    json_body: Optional[Any] = None,
) -> tuple[Any, str]:
    """Fetch JSON from a URL. Returns (parsed_json, final_url). Raises on non-2xx."""
    hdrs = {**get_default_headers(), "Accept": "application/json", **(headers or {})}
    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        resp = client.request(
            method.upper(), url, headers=hdrs,
            params=params, data=data, json=json_body,
        )
        resp.raise_for_status()
        return resp.json(), str(resp.url)
