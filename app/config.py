"""Configuration for hospital_job_ingestor."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = DATA_DIR / "outputs"
SOURCE_CONFIGS_DIR = DATA_DIR / "source_configs"
RUN_LOGS_DIR = DATA_DIR / "run_logs"

DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_WAIT_MS = 3000
MAX_DETAIL_PAGES = 10
MAX_HTML_PAGES = 10

CAREER_PATH_CANDIDATES = [
    "/careers", "/jobs", "/job-openings", "/job-listings",
    "/career-opportunities", "/work-with-us", "/join-us",
    "/openings", "/vacancies", "/employment", "/opportunities",
    "/careers/search", "/jobs/search", "/en/careers", "/en/jobs",
]

BLOCK_PAGE_TITLE_HINTS = [
    "access denied", "403 forbidden", "just a moment",
    "attention required", "cloudflare", "blocked", "captcha",
    "403", "unauthorized",
]

STATIC_ASSET_EXTENSIONS = {
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".woff", ".woff2", ".ttf", ".eot", ".ico", ".map",
    ".webp", ".mp4", ".mp3", ".pdf", ".zip",
}

COMMON_JOB_HINTS = [
    "job", "career", "opening", "vacancy", "position",
    "requisition", "apply", "hire", "recruit", "employment",
]

EMBEDDED_JSON_MARKERS = [
    "__NEXT_DATA__", "__INITIAL_STATE__", "window.__INITIAL_STATE__",
    "window.__NEXT_DATA__", "window.initialData", "window.APP_STATE",
    "window.__APP_DATA__",
]

NETWORK_HINTS = [
    "/api/", "/jobs/", "/careers/", "/v1/", "/v2/",
    "search", "listing", "openings", "positions", "vacancies",
    "requisitions", "job-search",
]
