"""API-based job extractor."""

import logging
from typing import Optional

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


def _looks_like_job(obj: dict) -> bool:
    """Return True if dict has job-like keys."""
    keys_lower = {k.lower() for k in obj.keys()}
    job_keys_lower = {k.lower() for k in JOB_LIKE_KEYS}
    return bool(keys_lower & job_keys_lower)


def _walk_json(data, results: list[dict], depth: int = 0) -> None:
    """Recursively walk JSON to find job-like objects."""
    if depth > 8:
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


class ApiExtractor(BaseExtractor):
    """Extracts jobs from API endpoints (JSON responses)."""

    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        """
        Extract jobs via API. Uses config if available, otherwise tries GET on source_url.

        Args:
            source_url: API endpoint URL.
            config: Optional source config with method/payload.

        Returns:
            List of raw job dicts.
        """
        method = "GET"
        json_body = None
        params = None
        headers = {}

        if config:
            endpoint = config.api_endpoint or source_url
            method = config.request_method or "GET"
            headers = config.headers or {}
            if config.payload_template and method.upper() == "POST":
                json_body = config.payload_template
        else:
            endpoint = source_url

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
