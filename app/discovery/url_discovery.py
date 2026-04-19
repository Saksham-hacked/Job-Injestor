"""URL discovery for hospital_job_ingestor."""
from __future__ import annotations
from bs4 import BeautifulSoup
from app.config import CAREER_PATH_CANDIDATES, COMMON_JOB_HINTS
from app.utils.urls import normalize_url, join_url
from app.utils.http import fetch_text
from app.utils.logger import get_logger

log = get_logger(__name__)


def discover_candidate_urls(input_url: str) -> list[str]:
    """
    Given a URL (homepage or careers page), return ordered list of candidate job URLs.
    Tries common career paths and parses homepage links.
    """
    base = normalize_url(input_url)
    candidates: list[str] = [base]

    # If it already looks like a careers/jobs page, return it first
    low = base.lower()
    if any(h in low for h in ["career", "job", "vacancy", "opening", "recruit"]):
        return [base]

    # Probe common paths
    from urllib.parse import urlparse
    parsed = urlparse(base)
    root = f"{parsed.scheme}://{parsed.netloc}"

    for path in CAREER_PATH_CANDIDATES:
        candidates.append(root + path)

    # Parse homepage links
    try:
        html, _ = fetch_text(base)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            text = (a.get_text() or "").lower()
            if any(h in href.lower() or h in text for h in COMMON_JOB_HINTS + ["career"]):
                full = join_url(base, href)
                if full not in candidates:
                    candidates.append(full)
    except Exception as e:
        log.warning(f"Homepage fetch failed for {base}: {e}")

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result
