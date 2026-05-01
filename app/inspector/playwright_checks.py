"""Playwright-based inspection checks."""
from __future__ import annotations

from app.config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_WAIT_MS, COMMON_JOB_HINTS
from app.inspector.validators import is_static_asset_url, is_api_like_url, looks_like_job_json
from app.utils.http import fetch_json
from app.utils.logger import get_logger

log = get_logger(__name__)

BLOCK_INDICATORS = ["403", "forbidden", "access denied", "just a moment", "attention required", "captcha"]
MAX_CTA_CLICKS = 8
CTA_HINTS = {
    "job", "jobs", "career", "careers", "opening", "openings", "vacancy",
    "vacancies", "position", "positions", "apply", "search jobs", "view jobs",
    "all jobs", "explore roles", "opportunity", "opportunities", "find jobs",
}


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _target_frames(page) -> list:
    try:
        return list(page.frames)
    except Exception:
        return []


def _collect_rendered_job_links(page) -> list[dict]:
    rendered: list[dict] = []
    for frame in _target_frames(page):
        try:
            links = frame.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.innerText}))")
        except Exception:
            continue
        for lnk in links:
            href = lnk.get("href", "")
            text = lnk.get("text", "").strip()
            if any(h in href.lower() or h in text.lower() for h in COMMON_JOB_HINTS):
                rendered.append({"url": href, "text": text})
    return rendered


def _classify_network_endpoints(network_responses: list[dict]) -> tuple[list[str], list[str]]:
    candidates: list[str] = []
    confirmed: list[str] = []

    for nr in network_responses:
        rurl = nr["url"]
        ct = (nr.get("content_type") or "").lower()
        status = int(nr.get("status", 0) or 0)

        looks_json = "json" in ct
        looks_api = is_api_like_url(rurl)
        if not looks_json and not looks_api:
            continue

        if looks_json and 200 <= status < 400:
            try:
                data, _ = fetch_json(rurl)
                if looks_like_job_json(data):
                    confirmed.append(rurl)
                    continue
            except Exception:
                pass

        candidates.append(rurl)

    return _unique(candidates), _unique(confirmed)


def _extract_observed_api_requests(network_rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    dedup: dict[str, dict] = {}
    for row in network_rows:
        url = row.get("url", "")
        ct = (row.get("content_type") or "").lower()
        if "json" not in ct and not is_api_like_url(url):
            continue
        req = {
            "url": url,
            "method": row.get("method", "GET"),
            "headers": row.get("request_headers", {}),
            "post_data": row.get("post_data", ""),
            "status": row.get("status"),
            "content_type": row.get("content_type", ""),
        }
        key = f"{req['method']}::{req['url']}"
        dedup[key] = req
    out.extend(dedup.values())
    return out


def _find_likely_job_ctas(page) -> list:
    selectors = [
        "a[href]", "button", "[role='button']", "div[onclick]", "span[onclick]",
        "[data-testid]", "[class*='btn']", "[class*='button']",
    ]
    seen: set[str] = set()
    candidates: list = []

    for frame in _target_frames(page):
        for sel in selectors:
            try:
                elements = frame.query_selector_all(sel)
            except Exception:
                continue

            for el in elements:
                try:
                    if not el.is_visible():
                        continue
                    text = (el.inner_text() or "").strip().lower()
                    href = (el.get_attribute("href") or "").strip().lower()
                    aria = (el.get_attribute("aria-label") or "").strip().lower()
                    cls = (el.get_attribute("class") or "").strip().lower()
                    combined = f"{text} {href} {aria} {cls}"

                    href_hint = any(h in href for h in ["job", "career", "opening", "position", "candidatev2"])
                    text_hint = any(h in combined for h in CTA_HINTS)
                    if not (href_hint or text_hint):
                        continue

                    key = f"{text[:80]}::{href[:120]}::{aria[:80]}::{cls[:80]}"
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(el)
                    if len(candidates) >= MAX_CTA_CLICKS:
                        return candidates
                except Exception:
                    continue
    return candidates


def _sample_visible_button_texts(page, limit: int = 12) -> list[str]:
    samples: list[str] = []
    for frame in _target_frames(page):
        try:
            vals = frame.eval_on_selector_all(
                "button, [role='button'], a[href]",
                "els => els.map(e => (e.innerText || e.getAttribute('aria-label') || '').trim()).filter(Boolean).slice(0, 50)",
            )
        except Exception:
            continue
        for text in vals:
            t = (text or "").strip()
            if not t:
                continue
            samples.append(t[:120])
            if len(samples) >= limit:
                return samples
    return samples


def inspect_with_playwright(url: str) -> dict:
    """
    Open page in headless Playwright, collect signals.
    Returns dict with page_title, candidate_api_endpoints, confirmed_api_endpoints,
    observed_api_requests, rendered_job_links, block_detected, notes.
    """
    result = {
        "page_title": "",
        "candidate_api_endpoints": [],
        "confirmed_api_endpoints": [],
        "observed_api_requests": [],
        "rendered_job_links": [],
        "block_detected": False,
        "notes": [],
    }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["notes"].append("Playwright not installed.")
        log.warning("[playwright] module import failed: playwright not installed")
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
                    if is_static_asset_url(rurl) or rurl == url:
                        return
                    ct = response.headers.get("content-type", "")
                    req = response.request
                    req_headers = {}
                    try:
                        for k, v in (req.headers or {}).items():
                            lk = (k or "").lower()
                            if lk in {"content-length", "host"}:
                                continue
                            req_headers[k] = v
                    except Exception:
                        req_headers = {}

                    network_responses.append({
                        "url": rurl,
                        "content_type": ct,
                        "status": response.status,
                        "method": req.method if req else "GET",
                        "request_headers": req_headers,
                        "post_data": (req.post_data or "") if req else "",
                    })
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)

            result["page_title"] = page.title() or ""
            frame_urls = [fr.url for fr in _target_frames(page) if getattr(fr, "url", None)]
            log.info("[playwright] frames count=%s urls=%s", len(frame_urls), frame_urls[:5])

            title_low = result["page_title"].lower()
            if any(b in title_low for b in BLOCK_INDICATORS):
                result["block_detected"] = True
                result["notes"].append("Block page detected by title.")

            result["rendered_job_links"] = _collect_rendered_job_links(page)
            passive_candidates, passive_confirmed = _classify_network_endpoints(network_responses)
            result["candidate_api_endpoints"] = passive_candidates
            result["confirmed_api_endpoints"] = passive_confirmed
            result["observed_api_requests"] = _extract_observed_api_requests(network_responses)

            network_sample = [n.get("url", "") for n in network_responses[:5]]
            log.info(
                "[playwright] passive_capture responses=%s rendered_links=%s api_candidates=%s api_confirmed=%s observed=%s sample=%s",
                len(network_responses),
                len(result["rendered_job_links"]),
                len(passive_candidates),
                len(passive_confirmed),
                len(result["observed_api_requests"]),
                network_sample,
            )

            if not result["confirmed_api_endpoints"]:
                ctas = _find_likely_job_ctas(page)
                log.info("[playwright] cta_probe candidates=%s", len(ctas))
                if not ctas:
                    result["notes"].append("No likely job CTA found for click probing.")
                    samples = _sample_visible_button_texts(page)
                    if samples:
                        result["notes"].append(f"Visible controls sample: {samples}")

                for i, cta in enumerate(ctas, start=1):
                    before = len(network_responses)
                    clicked = False
                    try:
                        cta.click(timeout=3000)
                        clicked = True
                    except Exception:
                        try:
                            cta.scroll_into_view_if_needed(timeout=1000)
                            cta.click(force=True, timeout=2500)
                            clicked = True
                        except Exception:
                            result["notes"].append(f"CTA click failed at probe {i}.")

                    if not clicked:
                        log.info("[playwright] cta_probe_%s click_failed", i)
                        continue

                    page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)
                    delta = network_responses[before:]
                    new_confirmed = []
                    if delta:
                        new_candidates, new_confirmed = _classify_network_endpoints(delta)
                        result["candidate_api_endpoints"] = _unique(result["candidate_api_endpoints"] + new_candidates)
                        result["confirmed_api_endpoints"] = _unique(result["confirmed_api_endpoints"] + new_confirmed)
                        result["observed_api_requests"] = _extract_observed_api_requests(network_responses)

                    result["rendered_job_links"] = _collect_rendered_job_links(page)
                    log.info(
                        "[playwright] cta_probe_%s delta_responses=%s new_confirmed=%s total_confirmed=%s observed=%s",
                        i,
                        len(delta),
                        len(new_confirmed),
                        len(result["confirmed_api_endpoints"]),
                        len(result["observed_api_requests"]),
                    )

                    if new_confirmed:
                        result["notes"].append(f"Confirmed job API after CTA probe {i}.")
                        break

            browser.close()
            log.info(
                "[playwright] done page_title='%s' block=%s candidates=%s confirmed=%s observed=%s rendered_links=%s",
                result["page_title"],
                result["block_detected"],
                len(result["candidate_api_endpoints"]),
                len(result["confirmed_api_endpoints"]),
                len(result["observed_api_requests"]),
                len(result["rendered_job_links"]),
            )

    except Exception as e:
        result["notes"].append(f"Playwright error: {e}")
        log.warning(f"Playwright inspection error for {url}: {e}")

    return result
