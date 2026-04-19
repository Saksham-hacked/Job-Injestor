"""Embedded JSON extractor (Next.js, etc.)."""

import json
import logging
import re
from typing import Optional

from app.extractors.base import BaseExtractor
from app.models.schemas import SourceConfig
from app.utils.http import fetch_text
from app.utils.html import maybe_extract_json_script_blocks
from app.utils.logger import get_logger

logger = get_logger(__name__)

JOB_LIKE_KEYS = {
    "title", "jobtitle", "job_title", "jobTitle", "name", "position",
    "requisitionid", "requisitionId", "reqId", "jobId", "job_id",
    "location", "description", "department", "employment_type",
}


def _looks_like_job(obj: dict) -> bool:
    keys_lower = {k.lower() for k in obj.keys()}
    job_keys_lower = {k.lower() for k in JOB_LIKE_KEYS}
    return bool(keys_lower & job_keys_lower)


def _walk_json(data, results: list[dict], depth: int = 0) -> None:
    if depth > 10:
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


class EmbeddedJsonExtractor(BaseExtractor):
    """Extracts jobs from embedded JSON in HTML (Next.js __NEXT_DATA__, etc.)."""

    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        """
        Fetch HTML and extract jobs from embedded JSON script blocks.

        Args:
            source_url: URL to fetch and parse.
            config: Optional source config.

        Returns:
            List of raw job dicts.
        """
        try:
            html, _ = fetch_text(source_url)
        except Exception as e:
            logger.error(f"EmbeddedJsonExtractor fetch failed: {e}")
            return []

        candidates = maybe_extract_json_script_blocks(html)
        all_results: list[dict] = []

        for text in candidates:
            try:
                data = json.loads(text)
                _walk_json(data, all_results)
            except Exception:
                continue

        logger.info(f"EmbeddedJsonExtractor found {len(all_results)} candidate job objects")
        return all_results
