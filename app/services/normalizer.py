"""Job normalizer: maps raw dicts to JobRecord."""

import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from app.models.schemas import JobRecord
from app.utils.logger import get_logger
from app.utils.urls import get_domain_slug

logger = get_logger(__name__)

TITLE_KEYS = ["title", "jobTitle", "job_title", "name", "position", "designation", "positionTitle", "jobName"]
ID_KEYS = ["source_job_id", "id", "jobId", "job_id", "requisitionId", "reqId", "guid", "referenceId"]
URL_KEYS = ["job_url", "jobUrl", "detailUrl", "jobDetailUrl", "applyUrl", "apply_url", "url", "link"]
APPLY_KEYS = ["apply_url", "applyUrl", "applyLink", "applicationUrl"]
LOCATION_KEYS = ["location", "jobLocation", "city", "place", "locationName"]
DESCRIPTION_KEYS = ["description", "jobDescription", "details", "summary", "content"]
SKILLS_KEYS = ["skills", "skillSet", "requiredSkills", "tags"]
EMPLOYMENT_KEYS = ["employment_type", "employmentType", "jobType", "type"]
EXPERIENCE_KEYS = ["experience", "experienceRequired", "yearsExperience"]
POSTED_KEYS = ["posted_text", "postedDate", "datePosted", "postDate", "created_at", "publishedDate"]


def _get_first(d: dict, keys: list[str]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _derive_id_from_url(url: str) -> str:
    try:
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1][:80] if path else ""
    except Exception:
        return ""


def _clean_skills(raw) -> list[str]:
    if isinstance(raw, list):
        return list({str(s).strip().lower() for s in raw if s})
    if isinstance(raw, str):
        parts = re.split(r"[,;|]", raw)
        return list({p.strip().lower() for p in parts if p.strip()})
    return []


def normalize_jobs(
    raw_jobs: list[dict],
    source_name: str,
    source_url: str,
) -> list[JobRecord]:
    """
    Normalize raw job dicts into JobRecord objects.

    Args:
        raw_jobs: List of raw extracted job dicts.
        source_name: Name of the source (domain slug).
        source_url: Original source URL.

    Returns:
        List of normalized JobRecord objects.
    """
    results: list[JobRecord] = []
    now = datetime.now(timezone.utc)
    company = get_domain_slug(source_url).replace("-", " ").title()

    for raw in raw_jobs:
        title = _get_first(raw, TITLE_KEYS)
        if not title:
            continue

        job_url = _get_first(raw, URL_KEYS) or ""
        source_job_id = _get_first(raw, ID_KEYS) or _derive_id_from_url(job_url)
        apply_url = _get_first(raw, APPLY_KEYS)
        location = _get_first(raw, LOCATION_KEYS)
        description = _get_first(raw, DESCRIPTION_KEYS)
        employment_type = _get_first(raw, EMPLOYMENT_KEYS)
        experience = _get_first(raw, EXPERIENCE_KEYS)
        posted_text = _get_first(raw, POSTED_KEYS)

        raw_skills = None
        for k in SKILLS_KEYS:
            if k in raw:
                raw_skills = raw[k]
                break
        skills = _clean_skills(raw_skills)

        if not job_url and not source_job_id:
            logger.debug(f"Skipping record with no URL or ID: {title}")
            continue

        try:
            record = JobRecord(
                source=source_name,
                source_job_id=source_job_id,
                title=title,
                company=company,
                location=location,
                employment_type=employment_type,
                experience=experience,
                posted_text=posted_text,
                job_url=job_url,
                apply_url=apply_url,
                description=description,
                skills=skills,
                metadata={"raw": raw},
                scraped_at=now,
            )
            results.append(record)
        except Exception as e:
            logger.warning(f"Failed to create JobRecord for '{title}': {e}")

    logger.info(f"Normalizer: {len(results)} valid records from {len(raw_jobs)} raw")
    return results
