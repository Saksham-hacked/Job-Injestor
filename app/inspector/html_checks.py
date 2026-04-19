"""HTML-based inspection checks."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from app.config import EMBEDDED_JSON_MARKERS, COMMON_JOB_HINTS
from app.utils.urls import join_url

GENERIC_CAREER_HINTS = [
    "life at", "employee", "benefits", "culture", "why join",
    "perks", "about us", "our team", "diversity", "wellbeing",
]

JOB_CARD_SELECTORS = [
    ".job-card", ".job", ".job-listing", ".job-item",
    ".opening", ".career-item", "li.job",
    "div[class*='job']", "div[class*='career']",
    "div[class*='opening']", "div[class*='vacancy']",
    "tr.job", ".position-item",
]


def detect_embedded_json_markers(html: str) -> list[str]:
    """Return list of embedded JSON markers found in page HTML."""
    found = []
    for marker in EMBEDDED_JSON_MARKERS:
        if marker in html:
            found.append(marker)
    return found


def _is_generic_career_link(text: str, href: str) -> bool:
    t = text.lower()
    h = href.lower()
    return any(g in t or g in h for g in GENERIC_CAREER_HINTS)


def detect_job_links_from_html(html: str, base_url: str) -> list[dict]:
    """Return list of likely job listing links (not generic career content)."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        text = clean_text(a.get_text())
        full = join_url(base_url, href)
        if full in seen:
            continue
        href_low = href.lower()
        # Must have job hint in href or text
        has_job_hint = any(h in href_low or h in text.lower() for h in COMMON_JOB_HINTS)
        if not has_job_hint:
            continue
        if _is_generic_career_link(text, href):
            continue
        seen.add(full)
        results.append({"url": full, "text": text})
    return results


def detect_html_card_candidates(html: str) -> list[tuple[str, int]]:
    """Return list of (selector, count) for card-like job elements."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    for sel in JOB_CARD_SELECTORS:
        try:
            els = soup.select(sel)
            if els:
                results.append((sel, len(els)))
        except Exception:
            pass
    return sorted(results, key=lambda x: -x[1])


def detect_pagination_hints(html: str) -> str | None:
    """Detect pagination type: 'query_param', 'next_link', or None."""
    soup = BeautifulSoup(html, "lxml")
    # Look for ?page= or &page= in links
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if re.search(r"[?&]page=\d+", href):
            return "query_param"
    # Look for next/» links
    for a in soup.find_all("a"):
        t = a.get_text().strip().lower()
        if t in ("next", "»", "next page", ">"):
            return "next_link"
    return None


def clean_text(t: str) -> str:
    import re
    return re.sub(r"\s+", " ", t).strip()
