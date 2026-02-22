"""Crawlerverse - Python SDK for the Crawler Agent API."""

__version__ = "0.2.1"

from crawlerverse.actions import (
    Action,
    Attack,
    Drop,
    EnterPortal,
    Equip,
    Move,
    Pickup,
    RangedAttack,
    Use,
    Wait,
)
from crawlerverse.async_client import AsyncCrawlerClient
from crawlerverse.client import CrawlerClient
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
from crawlerverse.models import (
    AbandonedOutcome,
    ActionResponse,
    CompletedOutcome,
    CreateGameResponse,
    GameResult,
    GameStateResponse,
    GameSummary,
    HealthResponse,
    InProgressOutcome,
    InventoryItem,
    ListGamesResponse,
    Monster,
    Observation,
    Player,
    VisibleTile,
)
from crawlerverse.runner import async_run_game, run_game
from crawlerverse.types import Direction, GameStatus, TileType

__all__ = [
    # Version
    "__version__",
    # Clients
    "CrawlerClient",
    "AsyncCrawlerClient",
    # Runner
    "run_game",
    "async_run_game",
    # Actions
    "Action",
    "Attack",
    "Drop",
    "EnterPortal",
    "Equip",
    "Move",
    "Pickup",
    "RangedAttack",
    "Use",
    "Wait",
    # Models
    "AbandonedOutcome",
    "ActionResponse",
    "CompletedOutcome",
    "CreateGameResponse",
    "GameResult",
    "GameStateResponse",
    "GameSummary",
    "HealthResponse",
    "InProgressOutcome",
    "InventoryItem",
    "ListGamesResponse",
    "Monster",
    "Observation",
    "Player",
    "VisibleTile",
    # Enums
    "Direction",
    "GameStatus",
    "TileType",
    # Exceptions
    "AuthenticationError",
    "CrawlerAPIError",
    "ForbiddenError",
    "GameOverError",
    "InvalidActionError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
]
