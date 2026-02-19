from crawlerverse.exceptions import (
    AuthenticationError,
    CrawlerAPIError,
    ForbiddenError,  # noqa: F401
    GameOverError,
    InvalidActionError,
    NotFoundError,  # noqa: F401
    RateLimitError,
    ValidationError,
)
from crawlerverse.models import CompletedOutcome


def test_base_error():
    e = CrawlerAPIError(status_code=500, message="Internal error")
    assert e.status_code == 500
    assert e.message == "Internal error"
    assert str(e) == "500: Internal error"


def test_inheritance():
    e = AuthenticationError(status_code=401, message="Invalid API key")
    assert isinstance(e, CrawlerAPIError)
    assert isinstance(e, Exception)


def test_rate_limit_error():
    e = RateLimitError(status_code=429, message="Too many requests", retry_after=30)
    assert e.retry_after == 30


def test_game_over_error():
    outcome = CompletedOutcome(status="completed", result="death", floor=3, turns=47)
    e = GameOverError(status_code=409, message="Game ended", outcome=outcome)
    assert e.outcome.result == "death"


def test_invalid_action_error():
    e = InvalidActionError(
        status_code=422, message="Can't move there", code="MOVE_BLOCKED"
    )
    assert e.code == "MOVE_BLOCKED"


def test_validation_error_with_details():
    e = ValidationError(
        status_code=400,
        message="Invalid request",
        details={"direction": ["required"]},
    )
    assert e.details == {"direction": ["required"]}
