"""URL utilities for hospital_job_ingestor."""
from urllib.parse import urlparse, urljoin, urlunparse
import re


def normalize_url(url: str) -> str:
    """Normalize a URL: ensure scheme, strip trailing slash."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(parsed._replace(path=path, fragment=""))


def join_url(base: str, maybe_relative: str) -> str:
    """Join a base URL with a possibly-relative URL."""
    return urljoin(base, maybe_relative)


def get_domain_slug(url: str) -> str:
    """Return a filesystem-safe slug from domain, e.g. 'apollohospitals'."""
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    host = re.sub(r"^www\.", "", host)
    host = host.split(":")[0]
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", host).strip("_")
    return slug.lower()
