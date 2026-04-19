"""Playwright-based inspection checks."""
from __future__ import annotations
from app.config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_WAIT_MS, COMMON_JOB_HINTS
from app.inspector.validators import is_static_asset_url, is_api_like_url, looks_like_job_json
from app.utils.logger import get_logger
import json

log = get_logger(__name__)

BLOCK_INDICATORS = ["403", "forbidden", "access denied", "just a moment", "attention required", "captcha"]


def inspect_with_playwright(url: str) -> dict:
    """
    Open page in headless Playwright, collect signals.
    Returns dict with page_title, candidate_api_endpoints, confirmed_api_endpoints,
    rendered_job_links, block_detected, notes.
    """
    result = {
        "page_title": "",
        "candidate_api_endpoints": [],
        "confirmed_api_endpoints": [],
        "rendered_job_links": [],
        "block_detected": False,
        "notes": [],
    }
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["notes"].append("Playwright not installed.")
        return result

    network_responses: list[dict] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            context = browser.new_context()
            page = context.new_page()

            def on_response(response):
                try:
                    rurl = response.url
                    if is_static_asset_url(rurl):
                        return
                    if rurl == url:
                        return
                    ct = response.headers.get("content-type", "")
                    network_responses.append({"url": rurl, "content_type": ct, "status": response.status})
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)

            result["page_title"] = page.title() or ""

            # Check block
            title_low = result["page_title"].lower()
            if any(b in title_low for b in BLOCK_INDICATORS):
                result["block_detected"] = True
                result["notes"].append("Block page detected by title.")

            # Collect rendered links
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.innerText}))")
            for lnk in links:
                href = lnk.get("href", "")
                text = lnk.get("text", "").strip()
                if any(h in href.lower() or h in text.lower() for h in COMMON_JOB_HINTS):
                    result["rendered_job_links"].append({"url": href, "text": text})

            browser.close()

        # Classify network responses
        for nr in network_responses:
            rurl = nr["url"]
            ct = nr["content_type"]
            if not is_api_like_url(rurl):
                result["candidate_api_endpoints"].append(rurl)
                continue
            # Try to confirm as API
            if "json" in ct:
                try:
                    data, _ = __import__("app.utils.http", fromlist=["fetch_json"]).fetch_json(rurl)
                    if looks_like_job_json(data):
                        result["confirmed_api_endpoints"].append(rurl)
                    else:
                        result["candidate_api_endpoints"].append(rurl)
                except Exception:
                    result["candidate_api_endpoints"].append(rurl)
            else:
                result["candidate_api_endpoints"].append(rurl)

    except Exception as e:
        result["notes"].append(f"Playwright error: {e}")
        log.warning(f"Playwright inspection error for {url}: {e}")

    return result
