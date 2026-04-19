"""HTML-based job extractor with pagination support."""

import logging
from typing import Optional
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, urlunparse

from bs4 import BeautifulSoup

from app.config import MAX_HTML_PAGES
from app.extractors.base import BaseExtractor
from app.models.schemas import SourceConfig
from app.utils.http import fetch_text
from app.utils.logger import get_logger
from app.utils.urls import join_url

logger = get_logger(__name__)

SELECTOR_CANDIDATES = [
    ".job-card", ".job-listing", ".job-item", ".job", ".opening",
    ".career-item", "li.job", "div[class*='job']", "div[class*='career']",
    "article.job", ".position", ".vacancy", "tr.job-row",
]

TITLE_SELECTORS = [
    "h2", "h3", "h4", ".job-title", ".position-title", ".title",
    "a.job-link", "[class*='title']",
]

LINK_SELECTORS = ["a[href]"]


def _extract_card(card, base_url: str) -> Optional[dict]:
    """Extract job info from a single card element."""
    title = None
    job_url = None

    for sel in TITLE_SELECTORS:
        el = card.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break

    if not title:
        title = card.get_text(strip=True)[:120] or None

    link_el = card.select_one("a[href]")
    if link_el:
        href = link_el.get("href", "")
        if href:
            job_url = join_url(base_url, href)

    if not title:
        return None

    location_el = card.select_one("[class*='location'], [class*='place'], .city")
    location = location_el.get_text(strip=True) if location_el else None

    raw_id = None
    if job_url:
        # try data attributes
        raw_id = card.get("data-job-id") or card.get("data-id") or card.get("id")

    return {
        "title": title,
        "job_url": job_url or "",
        "location": location,
        "source_job_id": raw_id or "",
    }


def _find_next_page_url(soup: BeautifulSoup, current_url: str, page_num: int) -> Optional[str]:
    """Heuristically find the next page URL."""
    # Try rel="next"
    next_link = soup.find("a", rel="next")
    if next_link and next_link.get("href"):
        return join_url(current_url, next_link["href"])

    # Try ?page= increment
    parsed = urlparse(current_url)
    qs = parse_qs(parsed.query)
    if "page" in qs:
        qs["page"] = [str(page_num + 1)]
        new_query = urlencode({k: v[0] for k, v in qs.items()})
        return urlunparse(parsed._replace(query=new_query))

    return None


class HtmlExtractor(BaseExtractor):
    """Extracts jobs from HTML using CSS selectors with basic pagination."""

    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        """
        Fetch and parse HTML to extract job listings.

        Args:
            source_url: URL to start extraction from.
            config: Optional source config with selectors.

        Returns:
            List of raw job dicts.
        """
        selectors = SELECTOR_CANDIDATES[:]
        if config and config.listing_selector:
            selectors = [config.listing_selector] + selectors

        all_jobs: list[dict] = []
        current_url: Optional[str] = source_url
        page_num = 1

        while current_url and page_num <= MAX_HTML_PAGES:
            try:
                html, resolved = fetch_text(current_url)
                current_url = resolved
            except Exception as e:
                logger.error(f"HtmlExtractor fetch failed on page {page_num}: {e}")
                break

            soup = BeautifulSoup(html, "lxml")
            found_any = False

            for sel in selectors:
                cards = soup.select(sel)
                if cards:
                    logger.info(f"HtmlExtractor: selector '{sel}' matched {len(cards)} cards on page {page_num}")
                    for card in cards:
                        job = _extract_card(card, current_url)
                        if job:
                            all_jobs.append(job)
                    found_any = True
                    break

            if not found_any:
                logger.info("HtmlExtractor: no matching cards found, stopping pagination")
                break

            next_url = _find_next_page_url(soup, current_url, page_num)
            if next_url and next_url != current_url:
                logger.info(f"HtmlExtractor: following next page -> {next_url}")
                current_url = next_url
                page_num += 1
            else:
                break

        logger.info(f"HtmlExtractor total raw jobs: {len(all_jobs)}")
        return all_jobs
