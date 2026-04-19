"""Base extractor abstract class."""

from abc import ABC, abstractmethod
from typing import Optional

from app.models.schemas import SourceConfig


class BaseExtractor(ABC):
    """Abstract base class for all job extractors."""

    @abstractmethod
    def extract(self, source_url: str, config: Optional[SourceConfig] = None) -> list[dict]:
        """
        Extract raw job dicts from source_url.

        Args:
            source_url: The URL to extract jobs from.
            config: Optional saved source config.

        Returns:
            List of raw job dicts (not normalized JobRecord yet).
        """
        ...
