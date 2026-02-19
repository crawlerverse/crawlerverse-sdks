import os
from unittest.mock import patch

import pytest

from crawlerverse._base_client import build_headers, map_error_response, resolve_api_key
from crawlerverse.exceptions import (
    AuthenticationError,
    ForbiddenError,
    GameOverError,
    InvalidActionError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


class TestResolveApiKey:
    def test_explicit_key(self):
        assert resolve_api_key("cra_abc123") == "cra_abc123"

    def test_env_var(self):
        with patch.dict(os.environ, {"CRAWLERVERSE_API_KEY": "cra_from_env"}):
            assert resolve_api_key(None) == "cra_from_env"

    def test_missing_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="No API key"):
                resolve_api_key(None)

    def test_explicit_overrides_env(self):
        with patch.dict(os.environ, {"CRAWLERVERSE_API_KEY": "cra_env"}):
            assert resolve_api_key("cra_explicit") == "cra_explicit"


class TestBuildHeaders:
    def test_contains_required_headers(self):
        headers = build_headers("cra_test123")
        assert headers["Authorization"] == "Bearer cra_test123"
        assert "crawlerverse-python/" in headers["User-Agent"]


class TestMapErrorResponse:
    def test_401(self):
        with pytest.raises(AuthenticationError):
            map_error_response(401, {"error": "Invalid API key"}, headers={})

    def test_403(self):
        with pytest.raises(ForbiddenError):
            map_error_response(403, {"error": "Suspended"}, headers={})

    def test_404(self):
        with pytest.raises(NotFoundError):
            map_error_response(404, {"error": "Not found"}, headers={})

    def test_400_with_details(self):
        with pytest.raises(ValidationError) as exc_info:
            map_error_response(
                400,
                {"error": "Invalid", "details": {"field": ["required"]}},
                headers={},
            )
        assert exc_info.value.details == {"field": ["required"]}

    def test_409_with_outcome(self):
        with pytest.raises(GameOverError) as exc_info:
            map_error_response(
                409,
                {
                    "error": "Game ended",
                    "outcome": {
                        "status": "completed",
                        "result": "death",
                        "floor": 3,
                        "turns": 47,
                    },
                },
                headers={},
            )
        assert exc_info.value.outcome.result == "death"

    def test_422(self):
        with pytest.raises(InvalidActionError) as exc_info:
            map_error_response(
                422,
                {"error": "Can't move", "code": "MOVE_BLOCKED"},
                headers={},
            )
        assert exc_info.value.code == "MOVE_BLOCKED"

    def test_429_with_retry_after(self):
        with pytest.raises(RateLimitError) as exc_info:
            map_error_response(
                429,
                {"error": "Rate limited"},
                headers={"retry-after": "30"},
            )
        assert exc_info.value.retry_after == 30

    def test_429_default_retry(self):
        with pytest.raises(RateLimitError) as exc_info:
            map_error_response(429, {"error": "Rate limited"}, headers={})
        assert exc_info.value.retry_after == 60
