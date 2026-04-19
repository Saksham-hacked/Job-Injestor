# Hospital Job Ingestor

A production-grade Python tool for intelligently extracting job listings from hospital websites. The system automatically inspects sources, chooses the best extraction strategy, and normalizes results into structured outputs.

## Features

- **Intelligent Source Discovery**: Automatically finds careers pages from hospital homepages
- **Multi-Strategy Extraction**: Supports API, embedded JSON, HTML, and JavaScript-rendered extraction
- **Adaptive Classification**: Inspects sources and chooses optimal extraction strategy
- **Protection Detection**: Honestly reports blocked/protected sites instead of bypassing them
- **Normalization**: Converts heterogeneous data into a common schema
- **Deduplication**: Removes duplicate job listings
- **Configuration Persistence**: Saves successful extraction configs for future runs
- **Structured Outputs**: Exports to JSON and CSV formats

## Architecture

```
hospital_job_ingestor/
├── app/
│   ├── models/           # Pydantic models and enums
│   ├── discovery/        # URL discovery logic
│   ├── inspector/        # Source inspection and classification
│   ├── strategy/         # Strategy selection engine
│   ├── extractors/       # Extraction implementations (API, HTML, Playwright, etc.)
│   ├── services/         # Business logic (orchestrator, normalizer, deduper)
│   ├── storage/          # File-based persistence
│   └── utils/            # HTTP, HTML, URL utilities
├── data/
│   ├── outputs/          # Generated JSON/CSV files
│   ├── source_configs/   # Saved source configurations
│   └── run_logs/         # Execution logs
└── scripts/              # CLI entry points
```

## Supported Source Types

1. **API**: Direct JSON endpoints
2. **Embedded JSON**: `__NEXT_DATA__`, `__INITIAL_STATE__`, etc.
3. **HTML**: Static HTML with job cards
4. **JS-Rendered**: Content requiring browser rendering
5. **Blocked**: Protected/blocked sources (reported, not bypassed)
6. **Manual Review**: Sources requiring human intervention

## Extraction Strategies

The system prioritizes strategies in this order:

1. **API Strategy**: Direct JSON fetching from discovered endpoints
2. **Embedded JSON Strategy**: Extracting from embedded JavaScript data
3. **HTML Strategy**: Parsing static HTML with heuristic selectors
4. **Playwright Strategy**: Browser-based rendering for dynamic content
5. **Manual Review**: Fallback when automated extraction isn't viable

## Installation

### Prerequisites

- Python 3.11 or higher
- pip

### Setup

```bash
# Clone or download the project
cd hospital_job_ingestor

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

### Single URL Ingestion

```bash
python scripts/ingest_url.py "https://www.apollohospitals.com/careers/index.html"
```

**Output:**
```
================================================================================
INGESTION SUMMARY
================================================================================
Input URL:         https://www.apollohospitals.com/careers/index.html
Resolved URL:      https://www.apollohospitals.com/careers/index.html
Status:            SUCCESS
Source Name:       apollohospitals_com
Source Type:       html
Confidence:        0.85
Block Detected:    False
Jobs Found:        42
JSON Output:       data/outputs/apollohospitals_com_2024-03-15_143022.json
CSV Output:        data/outputs/apollohospitals_com_2024-03-15_143022.csv
Config Saved:      Yes
================================================================================
```

### Known Sources Batch Run

```bash
python scripts/run_known_sources.py
```

This will process all previously saved source configurations and generate fresh outputs.

### Exit Codes

- `0`: Success or partial success
- `1`: Failed
- `2`: Blocked
- `3`: Manual review needed

## Sample Hospital URLs

Here are some example hospital career pages you can test with:

```bash
# Apollo Hospitals
python scripts/ingest_url.py "https://www.apollohospitals.com/careers/index.html"

# Fortis Healthcare
python scripts/ingest_url.py "https://www.fortishealthcare.com/careers-at-fortis"

# Manipal Hospitals
python scripts/ingest_url.py "https://careers.manipalhospitals.com/manipalhospitals/"

# Narayana Health
python scripts/ingest_url.py "https://jobs.narayanahealth.org/NH-India/viewalljobs/"

# Artemis Hospitals
python scripts/ingest_url.py "https://careers.artemishospitals.com/"
python scripts/ingest_url.py "https://www.artemishospitals.com/apply-online"
```

## Output Format

### JobRecord Schema

```json
{
  "source": "apollohospitals_com",
  "source_job_id": "REQ-2024-1234",
  "title": "Staff Nurse",
  "company": "Apollo Hospitals",
  "location": "Chennai, Tamil Nadu",
  "employment_type": "Full-time",
  "experience": "2-5 years",
  "posted_text": "Posted 3 days ago",
  "job_url": "https://www.apollohospitals.com/careers/job/12345",
  "apply_url": "https://www.apollohospitals.com/careers/apply/12345",
  "description": "Experienced staff nurse for ICU...",
  "skills": ["Critical Care", "BLS", "ACLS"],
  "metadata": {
    "raw": { ... },
    "extraction_strategy": "html"
  },
  "scraped_at": "2024-03-15T14:30:22.123456"
}
```

### CSV Columns

- source
- source_job_id
- title
- company
- location
- employment_type
- experience
- job_url
- apply_url
- posted_text
- scraped_at

## Result Statuses

- **success**: Jobs successfully extracted and normalized
- **partial**: Some jobs found but extraction incomplete or shallow
- **blocked**: Site is protected/blocked (detection only, no bypass)
- **manual_review_needed**: Automated extraction not viable
- **failed**: Fatal error during processing

## Configuration

Key settings in `app/config.py`:

```python
DEFAULT_TIMEOUT = 30                # HTTP timeout in seconds
PLAYWRIGHT_HEADLESS = True          # Run browser in headless mode
PLAYWRIGHT_WAIT_MS = 3000          # Wait time after page load
MAX_DETAIL_PAGES = 10              # Max detail pages to enrich
MAX_HTML_PAGES = 10                # Max pagination depth
```

## Limitations and Ethical Constraints

This tool is designed for **public, non-authenticated sources only**:

- ✅ Extracts from publicly accessible career pages
- ✅ Detects and reports protected/blocked sites
- ✅ Uses standard HTTP requests and browser rendering
- ❌ Does NOT bypass CAPTCHAs or anti-bot protections
- ❌ Does NOT implement stealth/evasion techniques
- ❌ Does NOT automate login or authentication
- ❌ Does NOT attempt to circumvent rate limiting

When the system encounters protections, it **reports them honestly** rather than attempting to bypass them.

## Storage

### Source Configurations
Saved to `data/source_configs/<source_name>.json`

Contains:
- Extraction strategy
- Selectors
- API endpoints
- Request templates
- Metadata

### Outputs
Saved to `data/outputs/`:
- `<source>_<timestamp>.json`: Full job records
- `<source>_<timestamp>.csv`: Tabular export

### Run Logs
Saved to `data/run_logs/`:
- `run_<timestamp>.json`: Execution details

## Development

### Project Structure

- `models/`: Pydantic schemas and enums
- `discovery/`: URL discovery and careers page detection
- `inspector/`: Source inspection, classification, and validation
- `strategy/`: Strategy selection logic
- `extractors/`: Extraction implementations
- `services/`: Core business logic (orchestration, normalization, deduplication)
- `storage/`: File-based persistence layer
- `utils/`: Shared utilities (HTTP, HTML parsing, URL handling, logging)

### Adding New Strategies

1. Create extractor in `app/extractors/`
2. Inherit from `BaseExtractor`
3. Implement `extract()` method
4. Add strategy to `StrategyType` enum
5. Update `strategy_engine.py` logic

### Extending Source Types

1. Add type to `SourceType` enum
2. Implement detection logic in inspector
3. Create corresponding extractor if needed
4. Update orchestrator flow

## Dependencies

- **httpx**: Modern HTTP client
- **beautifulsoup4**: HTML parsing
- **lxml**: Fast HTML/XML parsing
- **playwright**: Browser automation for JS-rendered content
- **pydantic**: Data validation and serialization
- **python-dotenv**: Environment configuration

## License

Internal tool for job aggregation purposes.

## Support

For issues or questions, contact the development team.

---

**Note**: This tool respects robots.txt and follows ethical web scraping practices. Always ensure you have proper authorization before scraping any website.
