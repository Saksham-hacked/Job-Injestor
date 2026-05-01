"""API-based job extractor."""

from __future__ import annotations

import json
from typing import Any, Optional

from app.config import DEFAULT_USER_AGENT, PLAYWRIGHT_HEADLESS, PLAYWRIGHT_WAIT_MS
from app.extractors.base import BaseExtractor
from app.models.schemas import SourceConfig
from app.utils.http import fetch_json
from app.utils.logger import get_logger

logger = get_logger(__name__)

JOB_LIKE_KEYS = {
    "title", "jobtitle", "job_title", "jobTitle", "name", "position",
    "requisitionid", "requisitionId", "reqId", "jobId", "job_id", "id",
    "location", "description", "apply_url", "applyUrl", "jobDetailUrl",
    "department", "employment_type", "employmentType",
}

CLICK_SELECTORS = [
    "text=Open Jobs",
    "button:has-text('Open Jobs')",
    "a:has-text('Open Jobs')",
    "text=We Have",
    "button:has-text('We Have')",
    "a:has-text('We Have')",
]

MAX_API_PAGES = 200
MAX_REPEAT_PAGES = 2


def _looks_like_job(obj: dict) -> bool:
    keys_lower = {k.lower() for k in obj.keys()}
    job_keys_lower = {k.lower() for k in JOB_LIKE_KEYS}
    return bool(keys_lower & job_keys_lower)


def _walk_json(data: Any, results: list[dict], depth: int = 0) -> None:
    if depth > 10:
        return
    if isinstance(data, dict):
        if _looks_like_job(data):
            results.append(data)
        else:
            for v in data.values():
                _walk_json(v, results, depth + 1)
    elif isinstance(data, list):
        for item in data:
            _walk_json(item, results, depth + 1)


def _extract_list_from_payload(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("data", "jobs", "results", "openings", "positions", "items", "records"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    safe: dict[str, str] = {}
    blocked = {
        "content-length",
        "host",
        "cookie",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "connection",
    }
    for k, v in (headers or {}).items():
        lk = (k or "").lower()
        if lk in blocked:
            continue
        safe[k] = v
    return safe


def _job_identity(job: dict) -> str:
    for k in ("id", "_id", "jobId", "job_id", "requisitionId", "reqId"):
        v = job.get(k)
        if v:
            return f"id::{str(v).strip()}"
    for k in ("job_url", "apply_url", "applyUrl", "url", "link"):
        v = job.get(k)
        if v:
            return f"url::{str(v).strip()}"
    title = str(job.get("title") or job.get("designation_display_name") or "").strip().lower()
    loc = str(job.get("location") or job.get("officelocation_show_arr") or "").strip().lower()
    return f"fallback::{title}::{loc}"


def _page_signature(rows: list[dict]) -> str:
    sample = [_job_identity(r) for r in rows[:20]]
    return "|".join(sample)


def _browser_fetch_json_pages(
    endpoint: str,
    payload_template: dict[str, Any],
    listing_url: str,
    headers: dict[str, str],
) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("Playwright not installed") from e

    safe_headers = _sanitize_headers(headers)
    limit = int(payload_template.get("limit") or 10)
    page_num = int(payload_template.get("page") or 1)
    all_rows: list[dict] = []
    seen_job_keys: set[str] = set()
    prev_signature = ""
    repeat_pages = 0

    js_fetch = """
    async ({ apiUrl, payload, extraHeaders }) => {
      const baseHeaders = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json'
      };
      const merged = { ...baseHeaders, ...(extraHeaders || {}) };
      const resp = await fetch(apiUrl, {
        method: 'POST',
        headers: merged,
        body: JSON.stringify(payload),
        credentials: 'include'
      });
      const contentType = resp.headers.get('content-type') || '';
      const text = await resp.text();
      return { ok: resp.ok, status: resp.status, contentType, text };
    }
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=DEFAULT_USER_AGENT,
            locale="en-US",
        )
        page = context.new_page()

        logger.info(f"ApiExtractor(browser): open {listing_url}")
        page.goto(listing_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(PLAYWRIGHT_WAIT_MS + 2000)

        for sel in CLICK_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.scroll_into_view_if_needed()
                    loc.click(timeout=3000)
                    logger.info(f"ApiExtractor(browser): clicked {sel}")
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        while page_num <= MAX_API_PAGES:
            payload = dict(payload_template)
            payload["page"] = page_num
            res = page.evaluate(js_fetch, {"apiUrl": endpoint, "payload": payload, "extraHeaders": safe_headers})

            if not res.get("ok"):
                browser.close()
                raise RuntimeError(f"Browser fetch failed status={res.get('status')} body={str(res.get('text', ''))[:300]}")

            ct = (res.get("contentType") or "").lower()
            if "json" not in ct:
                browser.close()
                raise RuntimeError(f"Unexpected content-type from browser fetch: {ct} body={str(res.get('text', ''))[:300]}")

            data = json.loads(res.get("text") or "null")
            rows = _extract_list_from_payload(data)
            if not rows:
                logger.info(f"ApiExtractor(browser): no rows on page {page_num}, stop")
                break

            sig = _page_signature(rows)
            if sig and sig == prev_signature:
                repeat_pages += 1
            else:
                repeat_pages = 0
            prev_signature = sig

            new_rows = 0
            for r in rows:
                key = _job_identity(r)
                if key in seen_job_keys:
                    continue
                seen_job_keys.add(key)
                all_rows.append(r)
                new_rows += 1

            logger.info(
                f"ApiExtractor(browser): page={page_num} fetched={len(rows)} new={new_rows} total={len(all_rows)} repeats={repeat_pages}"
            )

            if new_rows == 0:
                logger.info("ApiExtractor(browser): page added no new jobs, stop")
                break

            if repeat_pages >= MAX_REPEAT_PAGES:
                logger.info("ApiExtractor(browser): repeated page signature detected, stop")
                break

            if len(rows) < limit:
                logger.info("ApiExtractor(browser): last page by short batch, stop")
                break

            page_num += 1
            page.wait_for_timeout(600)

        if page_num > MAX_API_PAGES:
            logger.warning(f"ApiExtractor(browser): reached max page cap ({MAX_API_PAGES}), stop")

        browser.close()

    return all_rows


class ApiExtractor(BaseExtractor):
    """Extracts jobs from API endpoints (JSON responses)."""

    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        method = "GET"
        json_body = None
        params = None
        headers = {}
        listing_url = source_url

        if config:
            endpoint = config.api_endpoint or source_url
            method = (config.request_method or "GET").upper()
            headers = config.headers or {}
            listing_url = config.listing_url or source_url
            if config.payload_template and method == "POST":
                json_body = config.payload_template
        else:
            endpoint = source_url

        if method == "POST" and isinstance(json_body, dict):
            try:
                logger.info(f"ApiExtractor(browser): POST {endpoint}")
                browser_rows = _browser_fetch_json_pages(endpoint, json_body, listing_url, headers)
                if browser_rows:
                    logger.info(f"ApiExtractor(browser) found {len(browser_rows)} candidate job objects")
                    return browser_rows
            except Exception as e:
                logger.warning(f"ApiExtractor(browser) failed: {e}; falling back to direct HTTP")

        try:
            logger.info(f"ApiExtractor: {method} {endpoint}")
            data, _ = fetch_json(
                endpoint,
                method=method,
                headers=headers if headers else None,
                json_body=json_body,
                params=params,
            )
        except Exception as e:
            logger.error(f"ApiExtractor fetch failed: {e}")
            return []

        results: list[dict] = []
        _walk_json(data, results)
        logger.info(f"ApiExtractor found {len(results)} candidate job objects")
        return results
