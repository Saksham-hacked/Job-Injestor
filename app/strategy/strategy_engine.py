"""Strategy engine: map inspection result to extraction strategy."""
from app.models.schemas import SourceInspectionResult
from app.models.enums import SourceType, StrategyType


def choose_strategy(inspection: SourceInspectionResult) -> StrategyType:
    """
    Choose extraction strategy based on inspection result.
    Priority: api > embedded_json > html > playwright > manual_review
    """
    mapping = {
        SourceType.api: StrategyType.api,
        SourceType.embedded_json: StrategyType.embedded_json,
        SourceType.html: StrategyType.html,
        SourceType.js_rendered: StrategyType.playwright,
        SourceType.blocked: StrategyType.manual_review,
        SourceType.manual_review: StrategyType.manual_review,
    }
    return mapping.get(inspection.source_type, StrategyType.manual_review)
