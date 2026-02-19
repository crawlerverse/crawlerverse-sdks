import pytest

from crawlerverse.actions import Move, Wait
from crawlerverse.async_client import AsyncCrawlerClient
from crawlerverse.exceptions import (
    AuthenticationError,
    GameOverError,
    InvalidActionError,
    NotFoundError,
    RateLimitError,
)
from crawlerverse.models import InProgressOutcome
from crawlerverse.types import Direction

OBSERVATION_JSON = {
    "turn": 1,
    "floor": 1,
    "player": {
        "position": [5, 5],
        "hp": 20,
        "maxHp": 20,
        "attack": 5,
        "defense": 3,
        "equippedWeapon": None,
        "equippedArmor": None,
    },
    "inventory": [],
    "visibleTiles": [{"x": 5, "y": 5, "type": "floor", "items": []}],
    "messages": [],
}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("CRAWLERVERSE_API_KEY", "cra_test123")
    async with AsyncCrawlerClient(base_url="https://test.example.com/api/agent") as c:
        yield c


async def test_create_game(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://test.example.com/api/agent/games",
        json={
            "gameId": "game-1",
            "observation": OBSERVATION_JSON,
            "spectatorUrl": "https://crawlerver.se/spectate/game-1",
        },
        status_code=201,
    )
    game = await client.games.create(model_id="test")
    assert game.game_id == "game-1"


async def test_submit_action(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://test.example.com/api/agent/games/game-1/action",
        json={
            "observation": OBSERVATION_JSON,
            "outcome": {"status": "in_progress"},
        },
    )
    result = await client.games.action("game-1", Move(direction=Direction.NORTH))
    assert isinstance(result.outcome, InProgressOutcome)


async def test_list_games(client, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://test.example.com/api/agent/games?limit=20&offset=0",
        json={"games": [], "hasMore": False},
    )
    result = await client.games.list()
    assert result.games == []


async def test_get_game(client, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://test.example.com/api/agent/games/game-1",
        json={
            "observation": OBSERVATION_JSON,
            "outcome": {"status": "in_progress"},
        },
    )
    state = await client.games.get("game-1")
    assert state.observation.turn == 1


async def test_health(client, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://test.example.com/api/agent/health",
        json={
            "status": "ok",
            "service": "crawler-agent-api",
            "timestamp": "2025-02-02T10:30:00Z",
        },
    )
    health = await client.health()
    assert health.status == "ok"


class TestAsyncClientInit:
    async def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("CRAWLERVERSE_API_KEY", raising=False)
        with pytest.raises(AuthenticationError, match="No API key"):
            AsyncCrawlerClient()


class TestAsyncGamesAction:
    async def test_action_422_raises(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Can't move there", "code": "MOVE_BLOCKED"},
            status_code=422,
        )
        with pytest.raises(InvalidActionError, match="Can't move"):
            await client.games.action("game-1", Move(direction=Direction.NORTH))

    async def test_action_409_raises(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "error": "Game ended",
                "outcome": {
                    "status": "completed",
                    "result": "death",
                    "floor": 3,
                    "turns": 47,
                },
            },
            status_code=409,
        )
        with pytest.raises(GameOverError) as exc_info:
            await client.games.action("game-1", Wait())
        assert exc_info.value.outcome.result == "death"

    async def test_action_429_raises(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Rate limited"},
            status_code=429,
            headers={"retry-after": "5"},
        )
        with pytest.raises(RateLimitError) as exc_info:
            await client.games.action("game-1", Wait())
        assert exc_info.value.retry_after == 5


class TestAsyncGamesGet:
    async def test_get_game_404(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/games/nope",
            json={"error": "Game not found"},
            status_code=404,
        )
        with pytest.raises(NotFoundError):
            await client.games.get("nope")


class TestAsyncGamesAbandon:
    async def test_abandon(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/abandon",
            json={
                "gameId": "game-1",
                "status": "abandoned",
                "floor": 2,
                "turns": 30,
            },
        )
        result = await client.games.abandon("game-1")
        assert result.status == "abandoned"
