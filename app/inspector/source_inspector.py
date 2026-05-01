"""Main source inspector orchestrating all checks."""
from __future__ import annotations

from app.models.schemas import SourceInspectionResult
from app.models.enums import SourceType
from app.inspector.html_checks import (
    detect_embedded_json_markers,
    detect_job_links_from_html,
    detect_html_card_candidates,
    detect_pagination_hints,
)
from app.inspector.playwright_checks import inspect_with_playwright
from app.inspector.validators import is_block_page_title, classify_confidence
from app.utils.http import fetch_text
from app.utils.logger import get_logger

log = get_logger(__name__)


def inspect_source(url: str) -> SourceInspectionResult:
    """Inspect a source URL and return SourceInspectionResult."""
    notes: list[str] = []
    raw_signals: dict = {}
    resolved_url = url
    page_title = ""
    raw_html = ""
    block_detected = False

    log.info(f"[inspect] start url={url}")

    try:
        raw_html, resolved_url = fetch_text(url)
        log.info(f"[inspect] raw_fetch ok resolved_url={resolved_url} html_len={len(raw_html)}")
    except Exception as e:
        notes.append(f"Raw fetch failed: {e}")
        raw_signals["fetch_error"] = str(e)
        log.warning(f"[inspect] raw_fetch failed url={url} error={e}")

    if "403" in str(raw_signals.get("fetch_error", "")) or "401" in str(raw_signals.get("fetch_error", "")):
        block_detected = True
        log.info("[inspect] auth/block-like status seen in fetch error")

    embedded_markers: list[str] = []
    job_links: list[dict] = []
    card_candidates: list[tuple] = []
    pagination: str | None = None

    if raw_html:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw_html, "lxml")
        page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
        if is_block_page_title(page_title):
            block_detected = True
            notes.append("Block detected via page title.")

        embedded_markers = detect_embedded_json_markers(raw_html)
        job_links = detect_job_links_from_html(raw_html, resolved_url)
        card_candidates = detect_html_card_candidates(raw_html)
        pagination = detect_pagination_hints(raw_html)

    log.info(
        "[inspect] html_signals embedded=%s job_links=%s cards=%s pagination=%s",
        len(embedded_markers),
        len(job_links),
        card_candidates[0][1] if card_candidates else 0,
        pagination,
    )

    raw_signals.update(
        {
            "embedded_json_markers": embedded_markers,
            "job_links_count": len(job_links),
            "card_candidates": card_candidates,
            "pagination": pagination,
        }
    )

    log.info(f"[inspect] playwright probe start url={resolved_url}")
    pw_result = inspect_with_playwright(resolved_url)
    if pw_result.get("block_detected"):
        block_detected = True
    if not page_title:
        page_title = pw_result.get("page_title", "")

    confirmed_apis = pw_result.get("confirmed_api_endpoints", [])
    candidate_apis = pw_result.get("candidate_api_endpoints", [])
    observed_api_requests = pw_result.get("observed_api_requests", [])
    rendered_job_links = pw_result.get("rendered_job_links", [])
    pw_notes = pw_result.get("notes", [])
    notes.extend(pw_notes)

    observed_urls = [r.get("url", "") for r in observed_api_requests if r.get("url")]
    merged_candidate_apis = []
    seen = set()
    for u in observed_urls + candidate_apis:
        if u and u not in seen:
            seen.add(u)
            merged_candidate_apis.append(u)

    log.info(
        "[inspect] playwright_signals confirmed_api=%s candidate_api=%s observed=%s rendered_links=%s notes=%s",
        len(confirmed_apis),
        len(merged_candidate_apis),
        len(observed_api_requests),
        len(rendered_job_links),
        len(pw_notes),
    )

    raw_signals.update(
        {
            "confirmed_api": bool(confirmed_apis),
            "suspected_api": bool(merged_candidate_apis),
            "observed_api_requests": observed_api_requests,
            "observed_api_request_count": len(observed_api_requests),
            "rendered_job_links_count": len(rendered_job_links),
            "block_detected": block_detected,
            "job_card_count": card_candidates[0][1] if card_candidates else 0,
        }
    )

    if block_detected:
        source_type = SourceType.blocked
    elif confirmed_apis or observed_api_requests:
        source_type = SourceType.api
    elif embedded_markers:
        source_type = SourceType.embedded_json
    elif card_candidates and card_candidates[0][1] >= 3:
        source_type = SourceType.html
    elif rendered_job_links and len(rendered_job_links) >= 3:
        source_type = SourceType.js_rendered
    elif job_links and len(job_links) >= 3:
        source_type = SourceType.html
    else:
        source_type = SourceType.manual_review

    confidence = classify_confidence(raw_signals)
    best_selector = card_candidates[0][0] if card_candidates else None

    log.info(
        "[inspect] decision source_type=%s confidence=%.2f block=%s",
        source_type.value,
        confidence,
        block_detected,
    )

    return SourceInspectionResult(
        source_url=url,
        resolved_url=resolved_url,
        source_type=source_type,
        confidence=confidence,
        block_detected=block_detected,
        page_title=page_title,
        candidate_api_endpoints=confirmed_apis + merged_candidate_apis,
        html_selector_candidates=[best_selector] if best_selector else [],
        detected_pagination=pagination,
        needs_detail_pages=(source_type in (SourceType.html, SourceType.js_rendered)),
        notes=notes,
        raw_signals=raw_signals,
    )
