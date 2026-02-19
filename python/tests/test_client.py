import json

import pytest

from crawlerverse.actions import Move, Wait
from crawlerverse.client import CrawlerClient
from crawlerverse.exceptions import (
    AuthenticationError,
    CrawlerAPIError,
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
def client(monkeypatch):
    monkeypatch.setenv("CRAWLERVERSE_API_KEY", "cra_test123")
    with CrawlerClient(base_url="https://test.example.com/api/agent") as c:
        yield c


class TestClientInit:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("CRAWLERVERSE_API_KEY", raising=False)
        with pytest.raises(AuthenticationError, match="No API key"):
            CrawlerClient()

    def test_context_manager(self, monkeypatch):
        monkeypatch.setenv("CRAWLERVERSE_API_KEY", "cra_test")
        with CrawlerClient() as c:
            assert c is not None


class TestGamesCreate:
    def test_create_game(self, client, httpx_mock):
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
        game = client.games.create(model_id="test-model")
        assert game.game_id == "game-1"
        assert game.observation.turn == 1
        assert game.spectator_url == "https://crawlerver.se/spectate/game-1"

        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer cra_test123"
        assert "crawlerverse-python/" in request.headers["User-Agent"]
        body = json.loads(request.content)
        assert body["modelId"] == "test-model"


class TestGamesAction:
    def test_submit_action(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {"status": "in_progress"},
            },
        )
        result = client.games.action("game-1", Move(direction=Direction.NORTH))
        assert result.observation.turn == 1
        assert isinstance(result.outcome, InProgressOutcome)

    def test_action_422_raises(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Can't move there", "code": "MOVE_BLOCKED"},
            status_code=422,
        )
        with pytest.raises(InvalidActionError, match="Can't move"):
            client.games.action("game-1", Move(direction=Direction.NORTH))

    def test_action_409_raises(self, client, httpx_mock):
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
            client.games.action("game-1", Wait())
        assert exc_info.value.outcome.result == "death"

    def test_action_429_raises(self, client, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Rate limited"},
            status_code=429,
            headers={"retry-after": "5"},
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.games.action("game-1", Wait())
        assert exc_info.value.retry_after == 5


class TestGamesList:
    def test_list_games(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/games?status=completed&limit=10&offset=0",
            json={
                "games": [
                    {
                        "gameId": "game-1",
                        "status": "completed",
                        "modelId": "test",
                        "floorReached": 5,
                        "totalTurns": 100,
                        "result": "victory",
                        "startedAt": "2025-02-02T10:30:00Z",
                        "finishedAt": "2025-02-02T10:45:00Z",
                        "spectatorUrl": "https://crawlerver.se/spectate/game-1",
                    }
                ],
                "hasMore": False,
            },
        )
        result = client.games.list(status="completed", limit=10)
        assert len(result.games) == 1
        assert result.games[0].floor_reached == 5


class TestGamesGet:
    def test_get_game(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/games/game-1",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {"status": "in_progress"},
            },
        )
        state = client.games.get("game-1")
        assert isinstance(state.outcome, InProgressOutcome)

    def test_get_game_404(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/games/nope",
            json={"error": "Game not found"},
            status_code=404,
        )
        with pytest.raises(NotFoundError):
            client.games.get("nope")


class TestGamesAbandon:
    def test_abandon(self, client, httpx_mock):
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
        result = client.games.abandon("game-1")
        assert result.status == "abandoned"


class TestMalformedResponses:
    def test_html_error_body(self, client, httpx_mock):
        """Non-JSON error responses are handled gracefully."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/health",
            text="<html>502 Bad Gateway</html>",
            status_code=502,
        )
        with pytest.raises(CrawlerAPIError) as exc_info:
            client.health()
        assert "502 Bad Gateway" in exc_info.value.message

    def test_empty_error_body(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/health",
            text="",
            status_code=500,
        )
        with pytest.raises(CrawlerAPIError):
            client.health()

    def test_409_without_outcome(self, client, httpx_mock):
        """409 without an outcome field raises generic CrawlerAPIError."""
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Conflict without outcome"},
            status_code=409,
        )
        with pytest.raises(CrawlerAPIError, match="Conflict without outcome"):
            client.games.action("game-1", Wait())


class TestHealth:
    def test_health(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/health",
            json={
                "status": "ok",
                "service": "crawler-agent-api",
                "timestamp": "2025-02-02T10:30:00Z",
            },
        )
        health = client.health()
        assert health.status == "ok"
