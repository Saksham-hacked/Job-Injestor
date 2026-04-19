#!/usr/bin/env python3
"""CLI script to ingest jobs from a hospital URL."""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.orchestrator import IngestionOrchestrator
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point for CLI ingestion."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_url.py <url>")
        print("Example: python scripts/ingest_url.py https://www.example.com/careers")
        sys.exit(1)
    
    input_url = sys.argv[1]
    
    print(f"\n{'='*80}")
    print(f"Hospital Job Ingestor - Single URL Ingestion")
    print(f"{'='*80}\n")
    
    orchestrator = IngestionOrchestrator()
    
    try:
        result = orchestrator.ingest_url(input_url)
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"INGESTION SUMMARY")
        print(f"{'='*80}")
        print(f"Input URL:         {result.input_url}")
        print(f"Resolved URL:      {result.resolved_url}")
        print(f"Status:            {result.status.value.upper()}")
        print(f"Source Name:       {result.source_name or 'N/A'}")
        
        if result.inspection:
            print(f"Source Type:       {result.inspection.source_type.value}")
            print(f"Confidence:        {result.inspection.confidence:.2f}")
            print(f"Block Detected:    {result.inspection.block_detected}")
        
        print(f"Jobs Found:        {len(result.jobs)}")
        
        if result.json_output_path:
            print(f"JSON Output:       {result.json_output_path}")
        if result.csv_output_path:
            print(f"CSV Output:        {result.csv_output_path}")
        
        if result.saved_config:
            print(f"Config Saved:      Yes")
        
        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for warning in result.warnings:
                print(f"  - {warning}")
        
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                print(f"  - {error}")
        
        print(f"{'='*80}\n")
        
        # Exit codes
        if result.status.value == "success":
            sys.exit(0)
        elif result.status.value == "partial":
            sys.exit(0)
        elif result.status.value == "blocked":
            sys.exit(2)
        elif result.status.value == "manual_review_needed":
            sys.exit(3)
        else:
            sys.exit(1)
    
    except Exception as e:
        logger.exception("Fatal error during ingestion")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
