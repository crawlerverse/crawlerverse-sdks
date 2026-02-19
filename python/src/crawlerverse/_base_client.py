"""Shared client logic: auth resolution, headers, error mapping."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, NoReturn

from crawlerverse import __version__
from crawlerverse.exceptions import (
    AuthenticationError,
    CrawlerAPIError,
    ForbiddenError,
    GameOverError,
    InvalidActionError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from crawlerverse.models import parse_outcome

ENV_KEY = "CRAWLERVERSE_API_KEY"
DEFAULT_BASE_URL = "https://crawlerver.se/api/agent"
DEFAULT_TIMEOUT = 30.0


def resolve_api_key(api_key: str | None) -> str:
    """Resolve the API key from the explicit argument or environment variable.

    Priority: explicit argument > CRAWLERVERSE_API_KEY env var.
    Raises AuthenticationError if neither is available.
    """
    if api_key is not None:
        return api_key
    env_key = os.environ.get(ENV_KEY)
    if env_key is not None:
        return env_key
    msg = (
        f"No API key provided. Pass api_key= or set "
        f"{ENV_KEY} environment variable."
    )
    raise AuthenticationError(status_code=401, message=msg)


def build_headers(api_key: str) -> dict[str, str]:
    """Build the default HTTP headers for API requests."""
    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": f"crawlerverse-python/{__version__}",
        "Content-Type": "application/json",
    }


def map_error_response(
    status_code: int,
    body: dict[str, Any],
    headers: Mapping[str, str],
) -> NoReturn:
    """Map an HTTP error response to the appropriate exception.

    Always raises; the NoReturn type hint makes this explicit.
    """
    message = body.get("error", "Unknown error")

    if status_code == 400:
        raise ValidationError(
            status_code=400,
            message=message,
            details=body.get("details"),
        )

    if status_code == 401:
        raise AuthenticationError(status_code=401, message=message)

    if status_code == 403:
        raise ForbiddenError(status_code=403, message=message)

    if status_code == 404:
        raise NotFoundError(status_code=404, message=message)

    if status_code == 409:
        outcome_data = body.get("outcome")
        if outcome_data:
            outcome = parse_outcome(outcome_data)
            raise GameOverError(status_code=409, message=message, outcome=outcome)
        raise CrawlerAPIError(status_code=409, message=message)

    if status_code == 422:
        raise InvalidActionError(
            status_code=422,
            message=message,
            code=body.get("code", "UNKNOWN"),
        )

    if status_code == 429:
        retry_after = int(headers.get("retry-after", "60"))
        raise RateLimitError(status_code=429, message=message, retry_after=retry_after)

    raise CrawlerAPIError(status_code=status_code, message=message)
