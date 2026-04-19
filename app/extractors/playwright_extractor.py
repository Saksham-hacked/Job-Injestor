"""Playwright-based extractor for JS-rendered job pages."""

import logging
from typing import Optional

from app.config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_WAIT_MS
from app.extractors.base import BaseExtractor
from app.models.schemas import SourceConfig
from app.utils.logger import get_logger
from app.utils.urls import join_url
from app.inspector.validators import is_static_asset_url

logger = get_logger(__name__)

MAX_LOAD_MORE_CLICKS = 3
MAX_SCROLLS = 5

JOB_HINT_WORDS = {"job", "jobs", "career", "careers", "opening", "vacancy", "position", "role"}


def _is_job_like_link(href: str, text: str) -> bool:
    combined = (href + " " + text).lower()
    return any(w in combined for w in JOB_HINT_WORDS)


class PlaywrightExtractor(BaseExtractor):
    """Extracts jobs from JS-rendered pages using Playwright."""

    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        """
        Open page in headless browser, optionally click load-more, collect job links.

        Args:
            source_url: URL to render.
            config: Optional source config.

        Returns:
            List of raw job dicts.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            logger.error("Playwright not installed. Run: playwright install chromium")
            return []

        jobs: list[dict] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (compatible; HospitalJobIngestor/1.0)"})

                try:
                    page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)
                except PWTimeout:
                    logger.warning("Playwright page load timed out, continuing with partial DOM")

                # Try bounded "Load More" clicks
                for _ in range(MAX_LOAD_MORE_CLICKS):
                    try:
                        btn = page.query_selector(
                            "button:has-text('Load More'), button:has-text('Show More'), "
                            "a:has-text('Load More'), [class*='load-more']"
                        )
                        if btn and btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(1500)
                        else:
                            break
                    except Exception:
                        break

                # Bounded scrolls
                for _ in range(MAX_SCROLLS):
                    try:
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(600)
                    except Exception:
                        break

                # Collect job-like links
                links = page.query_selector_all("a[href]")
                seen = set()
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        text = (link.inner_text() or "").strip()[:200]
                        if not href or href.startswith("#") or is_static_asset_url(href):
                            continue
                        full_url = join_url(source_url, href)
                        if full_url in seen:
                            continue
                        if _is_job_like_link(href, text):
                            seen.add(full_url)
                            jobs.append({
                                "title": text or "Unknown",
                                "job_url": full_url,
                                "location": None,
                                "source_job_id": "",
                            })
                    except Exception:
                        continue

                browser.close()

        except Exception as e:
            logger.error(f"PlaywrightExtractor error: {e}")

        logger.info(f"PlaywrightExtractor found {len(jobs)} job-like links")
        return jobs
