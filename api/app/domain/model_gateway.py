"""Provider-independent model gateway values and errors."""

from dataclasses import dataclass


class ModelConfigurationError(RuntimeError):
    """Required model credentials or endpoints are missing."""


class ModelResponseError(RuntimeError):
    """A provider response violates the expected contract."""


class RerankUnavailableError(ModelConfigurationError):
    """Rerank is optional and has no configured endpoint."""


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    relevance_score: float
