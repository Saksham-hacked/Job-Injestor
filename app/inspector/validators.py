"""Validation helpers for inspector layer."""
from __future__ import annotations
from urllib.parse import urlparse
from app.config import BLOCK_PAGE_TITLE_HINTS, STATIC_ASSET_EXTENSIONS, NETWORK_HINTS


def is_block_page_title(title: str) -> bool:
    """Return True if page title suggests a block/protection page."""
    t = title.lower()
    return any(hint in t for hint in BLOCK_PAGE_TITLE_HINTS)


def is_static_asset_url(url: str) -> bool:
    """Return True if URL points to a static asset."""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in STATIC_ASSET_EXTENSIONS)


def is_api_like_url(url: str) -> bool:
    """Return True if URL looks like an API or XHR endpoint."""
    low = url.lower()
    return any(hint in low for hint in NETWORK_HINTS)


def looks_like_job_json(data: dict | list) -> bool:
    """Return True if parsed JSON looks like job data."""
    JOB_KEYS = {
        "title", "jobtitle", "jobTitle", "position", "name",
        "requisitionid", "reqid", "jobid", "description",
        "location", "department", "applyurl", "apply_url",
        "detailurl", "job_url", "postingurl",
    }
    if isinstance(data, list):
        if not data:
            return False
        sample = data[0] if isinstance(data[0], dict) else {}
    elif isinstance(data, dict):
        # Maybe it's a wrapper object
        sample = data
        # Check nested lists
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return looks_like_job_json(v)
    else:
        return False

    keys_lower = {k.lower() for k in sample.keys()}
    return bool(keys_lower & {k.lower() for k in JOB_KEYS})


def classify_confidence(signals: dict) -> float:
    """Compute a confidence score 0.0-1.0 from inspection signals."""
    score = 0.0
    if signals.get("confirmed_api"):
        score += 0.9
    elif signals.get("suspected_api"):
        score += 0.5
    if signals.get("embedded_json_markers"):
        score += 0.7
    if signals.get("job_card_count", 0) >= 3:
        score += 0.6
    elif signals.get("job_card_count", 0) >= 1:
        score += 0.3
    if signals.get("job_links_count", 0) >= 5:
        score += 0.4
    elif signals.get("job_links_count", 0) >= 1:
        score += 0.2
    if signals.get("block_detected"):
        score = 0.0
    return min(round(score, 2), 1.0)
