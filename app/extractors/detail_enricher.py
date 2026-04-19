"""Detail page enricher for shallow job records."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.config import MAX_DETAIL_PAGES
from app.utils.http import fetch_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

SKILL_PATTERNS = re.compile(
    r"\b(python|java|sql|excel|nursing|icu|ot|mbbs|md|bsc|msc|pharma|radiology|"
    r"ultrasound|mri|ct scan|lab|pathology|anesthesia|surgeon|physician|"
    r"communication|teamwork|leadership)\b",
    re.IGNORECASE,
)

EMPLOYMENT_TYPE_PATTERNS = [
    (re.compile(r"\bfull[- ]?time\b", re.I), "Full-time"),
    (re.compile(r"\bpart[- ]?time\b", re.I), "Part-time"),
    (re.compile(r"\bcontract\b", re.I), "Contract"),
    (re.compile(r"\btemporary\b", re.I), "Temporary"),
    (re.compile(r"\bpermanent\b", re.I), "Permanent"),
    (re.compile(r"\bfresher\b", re.I), "Fresher"),
]

EXPERIENCE_PATTERN = re.compile(
    r"(\d+[\+]?\s*[-–to]*\s*\d*\s*years?\s*(?:of\s*)?(?:experience)?)",
    re.IGNORECASE,
)


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    for sel in [".job-description", "#job-description", ".description",
                "section.detail", "article", "main", ".content"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 100:
                return text[:3000]
    return soup.get_text(separator=" ", strip=True)[:3000]


def _extract_apply_url(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    for sel in ["a[href*='apply']", "a:has-text('Apply')", ".apply-btn a", "#apply-link"]:
        try:
            el = soup.select_one(sel)
            if el and el.get("href"):
                from app.utils.urls import join_url
                return join_url(page_url, el["href"])
        except Exception:
            pass
    return None


def _extract_employment_type(text: str) -> Optional[str]:
    for pattern, label in EMPLOYMENT_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _extract_experience(text: str) -> Optional[str]:
    m = EXPERIENCE_PATTERN.search(text)
    return m.group(1).strip() if m else None


def _extract_skills(text: str) -> list[str]:
    return list({m.lower() for m in SKILL_PATTERNS.findall(text)})


class DetailEnricher:
    """Fetches detail pages and enriches shallow job records."""

    def enrich(self, raw_jobs: list[dict]) -> list[dict]:
        """
        Enrich job records that have job_url but lack description.

        Args:
            raw_jobs: List of raw job dicts.

        Returns:
            Enriched raw job dicts.
        """
        enriched = []
        count = 0

        for job in raw_jobs:
            job_url = job.get("job_url", "")
            if not job_url or job.get("description"):
                enriched.append(job)
                continue

            if count >= MAX_DETAIL_PAGES:
                enriched.append(job)
                continue

            try:
                html, _ = fetch_text(job_url)
                soup = BeautifulSoup(html, "lxml")
                description = _extract_description(soup)
                apply_url = _extract_apply_url(soup, job_url)
                full_text = soup.get_text(separator=" ", strip=True)
                employment_type = _extract_employment_type(full_text)
                experience = _extract_experience(full_text)
                skills = _extract_skills(full_text)

                job = dict(job)
                if description:
                    job["description"] = description
                if apply_url:
                    job["apply_url"] = apply_url
                if employment_type:
                    job["employment_type"] = employment_type
                if experience:
                    job["experience"] = experience
                if skills:
                    job["skills"] = skills

                count += 1
                logger.debug(f"Enriched: {job_url}")
            except Exception as e:
                logger.warning(f"Detail enrichment failed for {job_url}: {e}")

            enriched.append(job)

        logger.info(f"DetailEnricher enriched {count} jobs")
        return enriched
