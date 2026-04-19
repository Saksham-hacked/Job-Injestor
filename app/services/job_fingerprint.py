"""Job fingerprinting for deduplication."""

import hashlib

from app.models.schemas import JobRecord


def fingerprint_job(job: JobRecord) -> str:
    """
    Generate a stable SHA256 fingerprint for a JobRecord.

    Prefers source + source_job_id if available.
    Falls back to title + company + location + job_url.

    Args:
        job: JobRecord to fingerprint.

    Returns:
        Hex digest string.
    """
    if job.source and job.source_job_id:
        key = f"{job.source}::{job.source_job_id}"
    else:
        key = f"{job.title}::{job.company}::{job.location or ''}::{job.job_url}"

    return hashlib.sha256(key.encode("utf-8")).hexdigest()
