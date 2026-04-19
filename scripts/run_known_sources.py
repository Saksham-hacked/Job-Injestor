#!/usr/bin/env python3
"""CLI script to run ingestion for all known source configs."""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.orchestrator import IngestionOrchestrator
from app.storage.source_config_store import list_source_configs
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Run ingestion for all known sources."""
    print(f"\n{'='*80}")
    print(f"Hospital Job Ingestor - Known Sources Run")
    print(f"{'='*80}\n")
    
    configs = list_source_configs()
    
    if not configs:
        print("No saved source configurations found.")
        print("Run 'ingest_url.py' on some URLs first to build up saved configs.")
        sys.exit(0)
    
    print(f"Found {len(configs)} saved source(s)\n")
    
    orchestrator = IngestionOrchestrator()
    results = []
    
    for i, config in enumerate(configs, 1):
        print(f"\n[{i}/{len(configs)}] Processing: {config.source_name}")
        print(f"URL: {config.source_url}")
        print("-" * 80)
        
        try:
            result = orchestrator.ingest_url(config.source_url)
            results.append((config.source_name, result))
            
            print(f"Status: {result.status.value.upper()}")
            print(f"Jobs: {len(result.jobs)}")
            
            if result.warnings:
                print(f"Warnings: {len(result.warnings)}")
            if result.errors:
                print(f"Errors: {len(result.errors)}")
            
        except Exception as e:
            logger.exception(f"Error processing {config.source_name}")
            print(f"❌ Error: {e}")
            results.append((config.source_name, None))
    
    # Print final summary
    print(f"\n{'='*80}")
    print(f"FINAL SUMMARY")
    print(f"{'='*80}")
    
    success_count = sum(1 for _, r in results if r and r.status.value == "success")
    partial_count = sum(1 for _, r in results if r and r.status.value == "partial")
    blocked_count = sum(1 for _, r in results if r and r.status.value == "blocked")
    manual_count = sum(1 for _, r in results if r and r.status.value == "manual_review_needed")
    failed_count = sum(1 for _, r in results if r and r.status.value == "failed")
    error_count = sum(1 for _, r in results if r is None)
    
    total_jobs = sum(len(r.jobs) for _, r in results if r)
    
    print(f"Sources Processed:    {len(configs)}")
    print(f"Success:              {success_count}")
    print(f"Partial:              {partial_count}")
    print(f"Blocked:              {blocked_count}")
    print(f"Manual Review:        {manual_count}")
    print(f"Failed:               {failed_count}")
    print(f"Fatal Errors:         {error_count}")
    print(f"Total Jobs Collected: {total_jobs}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
