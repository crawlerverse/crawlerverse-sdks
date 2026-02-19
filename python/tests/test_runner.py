import pytest

from crawlerverse.actions import Action, Move, Wait
from crawlerverse.client import CrawlerClient
from crawlerverse.exceptions import InvalidActionError
from crawlerverse.models import (
    AbandonedOutcome,
    CompletedOutcome,
    Observation,
)
from crawlerverse.runner import run_game
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


def _agent_always_wait(obs: Observation) -> Action:
    return Wait()


class TestRunGameBasicLoop:
    def test_game_completes_victory(self, client, httpx_mock):
        # Create game
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
        # Action -> game completed
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {
                    "status": "completed",
                    "result": "victory",
                    "floor": 5,
                    "turns": 100,
                },
            },
        )

        result = run_game(client, _agent_always_wait, model_id="test")
        assert result.game_id == "game-1"
        assert result.spectator_url == "https://crawlerver.se/spectate/game-1"
        assert isinstance(result.outcome, CompletedOutcome)
        assert result.outcome.result == "victory"


class TestRunGameResume:
    def test_resume_existing_game(self, client, httpx_mock):
        # GET game state
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/games/existing-game",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {"status": "in_progress"},
            },
        )
        # Action -> game completed
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/existing-game/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {
                    "status": "completed",
                    "result": "death",
                    "floor": 2,
                    "turns": 30,
                },
            },
        )

        result = run_game(client, _agent_always_wait, game_id="existing-game")
        assert result.game_id == "existing-game"
        assert result.outcome.result == "death"


class TestRunGameErrorHandling:
    def test_invalid_action_retries_with_same_observation(self, client, httpx_mock):
        call_count = 0

        def agent_fn(obs: Observation) -> Action:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Move(direction=Direction.NORTH)  # will be rejected
            return Wait()  # second attempt works

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
        # First action: 422
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Can't move", "code": "MOVE_BLOCKED"},
            status_code=422,
        )
        # Second action: success -> game over
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {
                    "status": "completed",
                    "result": "death",
                    "floor": 1,
                    "turns": 1,
                },
            },
        )

        run_game(client, agent_fn)
        assert call_count == 2  # agent was called twice

    def test_max_invalid_actions_raises(self, client, httpx_mock):
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
        # Always return 422
        for _ in range(3):
            httpx_mock.add_response(
                method="POST",
                url="https://test.example.com/api/agent/games/game-1/action",
                json={"error": "Invalid", "code": "INVALID_ACTION"},
                status_code=422,
            )

        with pytest.raises(InvalidActionError):
            run_game(client, _agent_always_wait, max_invalid_actions=3)

    def test_game_over_between_turns(self, client, httpx_mock):
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
        # 409 on action (game timed out)
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "error": "Game timed out",
                "outcome": {
                    "status": "abandoned",
                    "reason": "timeout",
                    "floor": 1,
                    "turns": 5,
                },
            },
            status_code=409,
        )

        result = run_game(client, _agent_always_wait)
        assert isinstance(result.outcome, AbandonedOutcome)
        assert result.outcome.reason == "timeout"


class TestRunGameRateLimit:
    def test_rate_limit_backoff_then_success(self, client, httpx_mock):
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
        # First action: rate limited
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={"error": "Rate limited"},
            status_code=429,
            headers={"retry-after": "0"},
        )
        # Retry: success
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {
                    "status": "completed",
                    "result": "victory",
                    "floor": 5,
                    "turns": 100,
                },
            },
        )

        result = run_game(client, _agent_always_wait)
        assert isinstance(result.outcome, CompletedOutcome)
        assert result.outcome.result == "victory"


class TestRunGameAgentExceptions:
    def test_agent_exception_wrapped_with_context(self, client, httpx_mock):
        def bad_agent(obs: Observation) -> Action:
            raise ValueError("Agent crashed")

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

        with pytest.raises(RuntimeError, match="Agent function failed") as exc_info:
            run_game(client, bad_agent)
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_resume_completed_game_returns_immediately(self, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://test.example.com/api/agent/games/done-game",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {
                    "status": "completed",
                    "result": "victory",
                    "floor": 5,
                    "turns": 100,
                },
            },
        )

        result = run_game(client, _agent_always_wait, game_id="done-game")
        assert isinstance(result.outcome, CompletedOutcome)
        assert result.outcome.result == "victory"


class TestRunGameOnStep:
    def test_on_step_called(self, client, httpx_mock):
        steps = []

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
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {
                    "status": "completed",
                    "result": "victory",
                    "floor": 5,
                    "turns": 1,
                },
            },
        )

        run_game(
            client,
            _agent_always_wait,
            on_step=lambda obs, action: steps.append((obs.turn, action.action)),
        )
        assert len(steps) == 1
        assert steps[0] == (1, "wait")

    def test_on_step_exception_propagates(self, client, httpx_mock):
        """on_step callback errors propagate and crash the game loop."""

        def bad_callback(obs, action):
            raise RuntimeError("Callback failed")

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
        httpx_mock.add_response(
            method="POST",
            url="https://test.example.com/api/agent/games/game-1/action",
            json={
                "observation": OBSERVATION_JSON,
                "outcome": {"status": "in_progress"},
            },
        )

        with pytest.raises(RuntimeError, match="Callback failed"):
            run_game(
                client,
                _agent_always_wait,
                on_step=bad_callback,
            )
