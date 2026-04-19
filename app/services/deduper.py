"""Job deduplication service."""

from app.models.schemas import JobRecord
from app.services.job_fingerprint import fingerprint_job
from app.utils.logger import get_logger

logger = get_logger(__name__)


def dedupe_jobs(jobs: list[JobRecord]) -> list[JobRecord]:
    """
    Deduplicate jobs using:
    1) source + source_job_id
    2) job_url
    3) fingerprint fallback

    Preserves first occurrence.

    Args:
        jobs: List of JobRecord objects.

    Returns:
        Deduplicated list.
    """
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    result: list[JobRecord] = []

    for job in jobs:
        id_key = f"{job.source}::{job.source_job_id}" if job.source_job_id else None
        url_key = job.job_url.strip() if job.job_url else None
        fp = fingerprint_job(job)

        if id_key and id_key in seen_ids:
            continue
        if url_key and url_key in seen_urls:
            continue
        if fp in seen_fingerprints:
            continue

        if id_key:
            seen_ids.add(id_key)
        if url_key:
            seen_urls.add(url_key)
        seen_fingerprints.add(fp)

        result.append(job)

    logger.info(f"Deduper: {len(jobs)} -> {len(result)} jobs after dedup")
    return result
