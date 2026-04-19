"""Main ingestion orchestrator pipeline."""

import logging
from typing import Optional

from app.config import MAX_DETAIL_PAGES
from app.discovery.url_discovery import discover_candidate_urls
from app.extractors.api_extractor import ApiExtractor
from app.extractors.detail_enricher import DetailEnricher
from app.extractors.embedded_json_extractor import EmbeddedJsonExtractor
from app.extractors.html_extractor import HtmlExtractor
from app.extractors.playwright_extractor import PlaywrightExtractor
from app.inspector.source_inspector import inspect_source
from app.models.enums import RunStatus, SourceType, StrategyType
from app.models.results import IngestionResult
from app.models.schemas import JobRecord, SourceConfig
from app.services.deduper import dedupe_jobs
from app.services.normalizer import normalize_jobs
from app.storage.file_store import save_csv_output, save_json_output, save_run_log
from app.storage.source_config_store import load_source_config, save_source_config
from app.strategy.strategy_engine import choose_strategy
from app.utils.logger import get_logger
from app.utils.urls import get_domain_slug, normalize_url

logger = get_logger(__name__)

SHALLOW_THRESHOLD = 5  # if fewer than this jobs have descriptions, enrich


class IngestionOrchestrator:
    """Orchestrates the full job ingestion pipeline."""

    def ingest_url(self, input_url: str) -> IngestionResult:
        """
        Run the full ingestion pipeline for a given URL.

        Args:
            input_url: Hospital homepage or careers page URL.

        Returns:
            IngestionResult with status, jobs, paths, warnings, errors.
        """
        errors: list[str] = []
        warnings: list[str] = []
        jobs: list[JobRecord] = []
        saved_config: Optional[SourceConfig] = None

        # Normalize input
        try:
            input_url = normalize_url(input_url)
        except Exception as e:
            return IngestionResult(
                status=RunStatus.failed,
                input_url=input_url,
                errors=[f"URL normalization failed: {e}"],
            )

        source_name = get_domain_slug(input_url)

        # Check for known source config
        existing_config = load_source_config(source_name)
        if existing_config:
            logger.info(f"Found existing config for {source_name}")

        # Discover candidate URLs
        try:
            candidates = discover_candidate_urls(input_url)
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            candidates = [input_url]

        if not candidates:
            candidates = [input_url]

        logger.info(f"Candidates: {candidates}")

        inspection = None
        strategy = None
        resolved_url = input_url

        for candidate_url in candidates:
            logger.info(f"Inspecting candidate: {candidate_url}")
            try:
                inspection = inspect_source(candidate_url)
                resolved_url = inspection.resolved_url or candidate_url
            except Exception as e:
                errors.append(f"Inspection failed for {candidate_url}: {e}")
                continue

            if inspection.block_detected:
                warnings.append(f"Block detected at {candidate_url}")
                continue

            strategy = choose_strategy(inspection)
            logger.info(f"Strategy: {strategy} for {candidate_url}")

            if strategy == StrategyType.manual_review:
                warnings.append(f"No viable strategy for {candidate_url}")
                continue

            # Extract
            raw_jobs: list[dict] = []
            config_to_use = existing_config

            try:
                if strategy == StrategyType.api:
                    api_url = (
                        inspection.candidate_api_endpoints[0]
                        if inspection.candidate_api_endpoints
                        else resolved_url
                    )
                    raw_jobs = ApiExtractor().extract(api_url, config_to_use)

                elif strategy == StrategyType.embedded_json:
                    raw_jobs = EmbeddedJsonExtractor().extract(resolved_url, config_to_use)

                elif strategy == StrategyType.html:
                    raw_jobs = HtmlExtractor().extract(resolved_url, config_to_use)

                elif strategy == StrategyType.playwright:
                    raw_jobs = PlaywrightExtractor().extract(resolved_url, config_to_use)

            except Exception as e:
                errors.append(f"Extraction failed with {strategy}: {e}")
                logger.error(f"Extraction error: {e}")
                continue

            if raw_jobs:
                logger.info(f"Extracted {len(raw_jobs)} raw jobs via {strategy}")
                break
            else:
                warnings.append(f"No jobs extracted via {strategy} from {candidate_url}")

        # If no inspection done at all
        if inspection is None:
            return IngestionResult(
                status=RunStatus.failed,
                input_url=input_url,
                resolved_url=resolved_url,
                source_name=source_name,
                errors=errors,
                warnings=warnings,
            )

        if inspection.block_detected and not raw_jobs:
            return IngestionResult(
                status=RunStatus.blocked,
                input_url=input_url,
                resolved_url=resolved_url,
                source_name=source_name,
                inspection=inspection,
                errors=errors,
                warnings=warnings,
            )

        if strategy == StrategyType.manual_review or (not raw_jobs and not errors):
            return IngestionResult(
                status=RunStatus.manual_review_needed,
                input_url=input_url,
                resolved_url=resolved_url,
                source_name=source_name,
                inspection=inspection,
                errors=errors,
                warnings=warnings,
            )

        # Enrich details if shallow
        if raw_jobs:
            jobs_with_desc = sum(1 for j in raw_jobs if j.get("description"))
            if jobs_with_desc < SHALLOW_THRESHOLD and MAX_DETAIL_PAGES > 0:
                logger.info("Enriching detail pages...")
                try:
                    raw_jobs = DetailEnricher().enrich(raw_jobs)
                except Exception as e:
                    warnings.append(f"Detail enrichment failed: {e}")

        # Normalize
        try:
            normalized = normalize_jobs(raw_jobs, source_name, resolved_url)
        except Exception as e:
            errors.append(f"Normalization failed: {e}")
            normalized = []

        # Deduplicate
        jobs = dedupe_jobs(normalized)

        # Determine status
        if not jobs:
            status = RunStatus.failed if errors else RunStatus.manual_review_needed
        elif len(jobs) < 3:
            status = RunStatus.partial
        else:
            status = RunStatus.success

        # Save source config
        if jobs and strategy and strategy != StrategyType.manual_review:
            try:
                config_data = SourceConfig(
                    source_name=source_name,
                    source_url=input_url,
                    strategy=strategy,
                    listing_url=resolved_url,
                    api_endpoint=inspection.candidate_api_endpoints[0]
                    if inspection.candidate_api_endpoints else None,
                    listing_selector=inspection.html_selector_candidates[0][0]
                    if inspection.html_selector_candidates else None,
                    pagination_type=inspection.detected_pagination,
                    detail_page_enabled=inspection.needs_detail_pages,
                )
                saved_config = save_source_config(config_data)
                logger.info(f"Saved source config for {source_name}")
            except Exception as e:
                warnings.append(f"Could not save source config: {e}")

        # Save outputs
        json_path = None
        csv_path = None
        if jobs:
            try:
                result_temp = IngestionResult(
                    status=status,
                    input_url=input_url,
                    resolved_url=resolved_url,
                    source_name=source_name,
                    inspection=inspection,
                    saved_config=saved_config,
                    jobs=jobs,
                    errors=errors,
                    warnings=warnings,
                )
                json_path = save_json_output(source_name, jobs, result_temp)
                csv_path = save_csv_output(source_name, jobs)
            except Exception as e:
                warnings.append(f"Could not save outputs: {e}")

        result = IngestionResult(
            status=status,
            input_url=input_url,
            resolved_url=resolved_url,
            source_name=source_name,
            inspection=inspection,
            saved_config=saved_config,
            jobs=jobs,
            errors=errors,
            warnings=warnings,
            json_output_path=str(json_path) if json_path else None,
            csv_output_path=str(csv_path) if csv_path else None,
        )

        save_run_log(result)
        return result
