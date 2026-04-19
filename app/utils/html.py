"""HTML utilities for hospital_job_ingestor."""
from __future__ import annotations
import re
import json
from bs4 import BeautifulSoup, Tag
from app.config import COMMON_JOB_HINTS


def extract_visible_text(element: Tag) -> str:
    """Extract visible text from a BS4 element."""
    return element.get_text(separator=" ", strip=True)


def clean_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def is_job_like_text(text: str) -> bool:
    """Return True if text looks like a job title or listing."""
    t = text.lower()
    return any(hint in t for hint in COMMON_JOB_HINTS)


def maybe_extract_json_script_blocks(html: str) -> list[str]:
    """Return a list of candidate script text blocks that may contain JSON."""
    soup = BeautifulSoup(html, "lxml")
    candidates: list[str] = []
    for script in soup.find_all("script"):
        text = script.string or ""
        text = text.strip()
        if not text:
            continue
        # Look for JSON-like content
        if "{" in text and ("job" in text.lower() or "career" in text.lower() or "position" in text.lower()):
            candidates.append(text)
        # Look for known markers
        if any(m in text for m in ["__NEXT_DATA__", "__INITIAL_STATE__", "window."]):
            candidates.append(text)
    return candidates
