"""Main entrypoint for hospital_job_ingestor."""

from app.models.results import IngestionResult
from app.services.orchestrator import IngestionOrchestrator


def run_ingestion(input_url: str) -> IngestionResult:
    """
    Run the full ingestion pipeline for the given URL.

    Args:
        input_url: Hospital homepage or careers page URL.

    Returns:
        IngestionResult.
    """
    orchestrator = IngestionOrchestrator()
    return orchestrator.ingest_url(input_url)
