"""Main ingestion orchestrator pipeline."""

import json
from typing import Optional

from app.config import MAX_DETAIL_PAGES
from app.discovery.url_discovery import discover_candidate_urls
from app.extractors.api_extractor import ApiExtractor
from app.extractors.detail_enricher import DetailEnricher
from app.extractors.embedded_json_extractor import EmbeddedJsonExtractor
from app.extractors.html_extractor import HtmlExtractor
from app.extractors.playwright_extractor import PlaywrightExtractor
from app.inspector.source_inspector import inspect_source
from app.models.enums import RunStatus, StrategyType
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

NOISE_API_HINTS = (
    "tracking",
    "recaptcha",
    "analytics",
    "beacon",
    "consent",
    "cookie",
    "cdn-cgi",
    "rum",
    "geolocation",
)

JOB_API_HINTS = (
    "job",
    "jobs",
    "search",
    "openings",
    "positions",
    "vacancies",
    "careers",
    "requisition",
    "posting",
)


def _parse_post_data(post_data: str):
    if not post_data:
        return None
    text = post_data.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _score_api_url(url: str) -> int:
    low = (url or "").lower()
    score = 0
    if not low:
        return -100

    for hint in JOB_API_HINTS:
        if hint in low:
            score += 3

    for hint in NOISE_API_HINTS:
        if hint in low:
            score -= 8

    if any(low.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".svg", ".gif", ".ico")):
        score -= 8

    return score


def _score_observed_request(req: dict) -> int:
    url = req.get("url", "")
    method = (req.get("method") or "GET").upper()
    ct = (req.get("content_type") or "").lower()
    score = _score_api_url(url)

    if method == "POST":
        score += 2
    if "json" in ct:
        score += 2

    payload = _parse_post_data(req.get("post_data", ""))
    if isinstance(payload, dict):
        payload_keys = {str(k).lower() for k in payload.keys()}
        if {"page", "limit"} & payload_keys:
            score += 2
        if {"job", "jobs", "keyword", "search", "location", "companyid"} & payload_keys:
            score += 2

    return score


def _select_best_observed_request(observed: list[dict]) -> tuple[Optional[dict], int]:
    if not observed:
        return None, -100

    best_req = None
    best_score = -100
    for req in observed:
        s = _score_observed_request(req)
        if s > best_score:
            best_score = s
            best_req = req
    return best_req, best_score


def _choose_best_api_endpoint(endpoints: list[str], fallback: str) -> str:
    if not endpoints:
        return fallback
    best = max(endpoints, key=_score_api_url)
    return best


def _build_api_config_from_observed_request(
    observed_req: dict,
    listing_url: str,
    source_name: str,
    source_url: str,
) -> SourceConfig:
    method = (observed_req.get("method") or "GET").upper()
    payload = _parse_post_data(observed_req.get("post_data", ""))
    headers = observed_req.get("headers") or {}
    return SourceConfig(
        source_name=source_name,
        source_url=source_url,
        strategy=StrategyType.api,
        listing_url=listing_url,
        api_endpoint=observed_req.get("url") or listing_url,
        request_method=method,
        payload_template=payload,
        headers=headers,
        metadata={"captured_by": "playwright", "captured_status": observed_req.get("status")},
    )


class IngestionOrchestrator:
    """Orchestrates the full job ingestion pipeline."""

    def ingest_url(self, input_url: str) -> IngestionResult:
        errors: list[str] = []
        warnings: list[str] = []
        jobs: list[JobRecord] = []
        raw_jobs: list[dict] = []
        saved_config: Optional[SourceConfig] = None
        extraction_config_used: Optional[SourceConfig] = None
        extraction_api_endpoint: Optional[str] = None

        try:
            input_url = normalize_url(input_url)
        except Exception as e:
            return IngestionResult(status=RunStatus.failed, input_url=input_url, errors=[f"URL normalization failed: {e}"])

        source_name = get_domain_slug(input_url)

        existing_config = load_source_config(source_name)
        if existing_config:
            logger.info(f"Found existing config for {source_name}")

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
                logger.info(
                    "Inspection summary: type=%s confidence=%.2f api_candidates=%s html_candidates=%s notes=%s",
                    inspection.source_type.value,
                    inspection.confidence,
                    len(inspection.candidate_api_endpoints),
                    len(inspection.html_selector_candidates),
                    len(inspection.notes),
                )
            except Exception as e:
                errors.append(f"Inspection failed for {candidate_url}: {e}")
                continue

            if inspection.block_detected:
                warnings.append(f"Block detected at {candidate_url}")
                for note in inspection.notes:
                    warnings.append(f"Inspection note: {note}")
                continue

            strategy = choose_strategy(inspection)
            logger.info(f"Strategy: {strategy} for {candidate_url}")

            if strategy == StrategyType.manual_review:
                if existing_config and existing_config.strategy != StrategyType.manual_review:
                    warnings.append(
                        f"Inspection could not classify a strategy for {candidate_url}; using saved config strategy {existing_config.strategy.value}."
                    )
                    strategy = existing_config.strategy
                    logger.info("Falling back to saved config strategy: %s", strategy)
                else:
                    warnings.append(f"No viable strategy for {candidate_url}")
                    for note in inspection.notes:
                        warnings.append(f"Inspection note: {note}")
                    continue

            config_to_use = existing_config

            try:
                if strategy == StrategyType.api:
                    observed = inspection.raw_signals.get("observed_api_requests", []) if inspection.raw_signals else []
                    best_observed, observed_score = _select_best_observed_request(observed)

                    if config_to_use and config_to_use.strategy == StrategyType.api:
                        existing_endpoint = config_to_use.api_endpoint or ""
                        existing_score = _score_api_url(existing_endpoint)
                        if observed and existing_score <= 0:
                            logger.info(
                                "Ignoring stale saved API config endpoint=%s score=%s in favor of current inspection",
                                existing_endpoint,
                                existing_score,
                            )
                            config_to_use = None

                    if config_to_use is None and best_observed and observed_score > 0:
                        config_to_use = _build_api_config_from_observed_request(
                            observed_req=best_observed,
                            listing_url=resolved_url,
                            source_name=source_name,
                            source_url=input_url,
                        )
                        logger.info(
                            "Using Playwright-captured API template score=%s method=%s endpoint=%s",
                            observed_score,
                            config_to_use.request_method,
                            config_to_use.api_endpoint,
                        )
                    elif config_to_use is None and best_observed:
                        logger.info(
                            "Skipping low-score observed API template score=%s endpoint=%s",
                            observed_score,
                            best_observed.get("url"),
                        )

                    extraction_config_used = config_to_use
                    api_url = config_to_use.api_endpoint if config_to_use and config_to_use.api_endpoint else None
                    if not api_url:
                        api_url = _choose_best_api_endpoint(inspection.candidate_api_endpoints, resolved_url)
                        logger.info("Selected best candidate API endpoint: %s", api_url)

                    extraction_api_endpoint = api_url
                    raw_jobs = ApiExtractor().extract(api_url, config_to_use)

                    if not raw_jobs and inspection.html_selector_candidates:
                        logger.info("API yielded 0 jobs; falling back to HTML extractor for this candidate")
                        raw_jobs = HtmlExtractor().extract(resolved_url, config_to_use)
                        if raw_jobs:
                            strategy = StrategyType.html
                            extraction_config_used = None

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
            warnings.append(f"No jobs extracted via {strategy} from {candidate_url}")

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

        if raw_jobs:
            jobs_with_desc = sum(1 for j in raw_jobs if j.get("description"))
            if jobs_with_desc < SHALLOW_THRESHOLD and MAX_DETAIL_PAGES > 0:
                logger.info("Enriching detail pages...")
                try:
                    raw_jobs = DetailEnricher().enrich(raw_jobs)
                except Exception as e:
                    warnings.append(f"Detail enrichment failed: {e}")

        try:
            normalized = normalize_jobs(raw_jobs, source_name, resolved_url)
        except Exception as e:
            errors.append(f"Normalization failed: {e}")
            normalized = []

        jobs = dedupe_jobs(normalized)

        if not jobs:
            status = RunStatus.failed if errors else RunStatus.manual_review_needed
        elif len(jobs) < 3:
            status = RunStatus.partial
        else:
            status = RunStatus.success

        if jobs and strategy and strategy != StrategyType.manual_review:
            try:
                api_endpoint = extraction_api_endpoint or (inspection.candidate_api_endpoints[0] if inspection.candidate_api_endpoints else None)
                request_method = "GET"
                payload_template = None
                headers = {}
                if extraction_config_used and extraction_config_used.strategy == StrategyType.api:
                    api_endpoint = extraction_config_used.api_endpoint or api_endpoint
                    request_method = extraction_config_used.request_method
                    payload_template = extraction_config_used.payload_template
                    headers = extraction_config_used.headers

                config_data = SourceConfig(
                    source_name=source_name,
                    source_url=input_url,
                    strategy=strategy,
                    listing_url=resolved_url,
                    api_endpoint=api_endpoint,
                    request_method=request_method,
                    payload_template=payload_template,
                    listing_selector=inspection.html_selector_candidates[0] if inspection.html_selector_candidates else None,
                    pagination_type=inspection.detected_pagination,
                    detail_page_enabled=inspection.needs_detail_pages,
                    headers=headers,
                )
                saved_config = save_source_config(config_data)
                logger.info(f"Saved source config for {source_name}")
            except Exception as e:
                warnings.append(f"Could not save source config: {e}")

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
