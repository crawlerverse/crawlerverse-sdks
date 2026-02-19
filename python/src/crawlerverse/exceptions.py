"""Exception hierarchy for Crawler API errors."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawlerverse.models import AbandonedOutcome, CompletedOutcome


class CrawlerAPIError(Exception):
    """Base exception for all API errors."""

    def __init__(self, *, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"{status_code}: {message}")


class AuthenticationError(CrawlerAPIError):
    """401 - Invalid or missing API key."""


class ForbiddenError(CrawlerAPIError):
    """403 - API key not activated or suspended."""


class NotFoundError(CrawlerAPIError):
    """404 - Resource not found."""


class ValidationError(CrawlerAPIError):
    """400 - Invalid request parameters."""

    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        details: dict[str, list[str]] | None = None,
    ) -> None:
        self.details = details
        super().__init__(status_code=status_code, message=message)


class GameOverError(CrawlerAPIError):
    """409 - Game already ended or timed out."""

    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        outcome: CompletedOutcome | AbandonedOutcome,
    ) -> None:
        self.outcome = outcome
        super().__init__(status_code=status_code, message=message)


class InvalidActionError(CrawlerAPIError):
    """422 - Action rejected by game engine."""

    def __init__(self, *, status_code: int, message: str, code: str) -> None:
        self.code = code
        super().__init__(status_code=status_code, message=message)


class RateLimitError(CrawlerAPIError):
    """429 - Rate limit exceeded."""

    def __init__(self, *, status_code: int, message: str, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(status_code=status_code, message=message)
