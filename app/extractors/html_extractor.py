"""HTML-based job extractor with pagination support."""

import re
from typing import Optional
from urllib.parse import parse_qs, parse_qsl, urlparse, urlencode, urlunparse

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

PAGINATION_QUERY_KEYS = {"page", "p", "pg", "offset", "start", "startrow", "from"}


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
        raw_id = card.get("data-job-id") or card.get("data-id") or card.get("id")

    return {
        "title": title,
        "job_url": job_url or "",
        "location": location,
        "source_job_id": raw_id or "",
    }


def _increment_page_query(current_url: str, page_num: int) -> Optional[str]:
    parsed = urlparse(current_url)
    qs = parse_qs(parsed.query)
    for key in PAGINATION_QUERY_KEYS:
        if key in qs:
            qs[key] = [str(page_num + 1)]
            new_query = urlencode({k: v[0] for k, v in qs.items()})
            return urlunparse(parsed._replace(query=new_query))
    return None


def _resolve_pagination_href(current_url: str, href: str) -> str:
    """Resolve pagination hrefs, including query-fragment links like '&p=2'."""
    href = (href or "").strip()
    if not href:
        return current_url

    parsed = urlparse(current_url)

    if href.startswith("&"):
        base_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        add_pairs = parse_qsl(href[1:], keep_blank_values=True)
        merged: dict[str, str] = {}
        for k, v in base_pairs:
            merged[k] = v
        for k, v in add_pairs:
            merged[k] = v
        return urlunparse(parsed._replace(query=urlencode(merged, doseq=False)))

    if href.startswith("?"):
        return urlunparse(parsed._replace(query=href[1:]))

    return join_url(current_url, href)


def _pagination_candidates(soup: BeautifulSoup, current_url: str, page_num: int) -> list[str]:
    candidates: list[tuple[str, int]] = []

    next_link = soup.find("a", rel="next")
    if next_link and next_link.get("href"):
        candidates.append((_resolve_pagination_href(current_url, next_link["href"]), 100))

    inc = _increment_page_query(current_url, page_num)
    if inc:
        candidates.append((inc, 90))

    current_parsed = urlparse(current_url)

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue

        text = " ".join((a.get_text() or "").split()).strip().lower()
        aria = str(a.get("aria-label") or "").strip().lower()
        cls = " ".join(a.get("class") or []).strip().lower()
        rel = " ".join(a.get("rel") or []).strip().lower()

        score = 0
        if "next" in text or "next" in aria or "next" in cls or "next" in rel or text in {">", "»"}:
            score += 50
        if re.fullmatch(r"\d+", text or ""):
            score += 20

        full = _resolve_pagination_href(current_url, href)
        parsed = urlparse(full)
        if parsed.netloc != current_parsed.netloc:
            continue

        q = parse_qs(parsed.query)
        if any(k.lower() in PAGINATION_QUERY_KEYS for k in q.keys()):
            score += 30

        if parsed.path == current_parsed.path and parsed.query != current_parsed.query:
            score += 10

        if score > 0:
            candidates.append((full, score))

    seen: set[str] = set()
    ordered: list[str] = []
    for url, _ in sorted(candidates, key=lambda x: -x[1]):
        if url == current_url or url in seen:
            continue
        seen.add(url)
        ordered.append(url)

    return ordered


class HtmlExtractor(BaseExtractor):
    """Extracts jobs from HTML using CSS selectors with heuristic pagination."""

    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        selectors = SELECTOR_CANDIDATES[:]
        if config and config.listing_selector:
            selectors = [config.listing_selector] + selectors

        all_jobs: list[dict] = []
        current_url: Optional[str] = source_url
        page_num = 1
        visited: set[str] = set()

        while current_url and page_num <= MAX_HTML_PAGES:
            if current_url in visited:
                logger.info("HtmlExtractor: already visited %s, stopping", current_url)
                break
            visited.add(current_url)

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

            next_urls = _pagination_candidates(soup, current_url, page_num)
            next_url = None
            for u in next_urls:
                if u not in visited:
                    next_url = u
                    break

            if next_url and next_url != current_url:
                logger.info(f"HtmlExtractor: following next page -> {next_url}")
                current_url = next_url
                page_num += 1
            else:
                break

        logger.info(f"HtmlExtractor total raw jobs: {len(all_jobs)}")
        return all_jobs
