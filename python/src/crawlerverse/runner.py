"""High-level game runner helpers."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from crawlerverse.exceptions import GameOverError, InvalidActionError, RateLimitError
from crawlerverse.models import (
    GameResult,
    InProgressOutcome,
    Observation,
)

if TYPE_CHECKING:
    from crawlerverse.actions import Action
    from crawlerverse.async_client import AsyncCrawlerClient
    from crawlerverse.client import CrawlerClient

logger = logging.getLogger("crawlerverse")


def run_game(
    client: CrawlerClient,
    agent_fn: Callable[[Observation], Action],
    *,
    model_id: str | None = None,
    game_id: str | None = None,
    max_invalid_actions: int = 5,
    on_step: Callable[[Observation, Action], None] | None = None,
) -> GameResult:
    """Run a complete game loop.

    Creates a new game (or resumes an existing one), calls agent_fn each turn,
    and returns the final result.
    """
    if game_id is not None:
        state = client.games.get(game_id)
        observation = state.observation
        spectator_url = ""
        if not isinstance(state.outcome, InProgressOutcome):
            return GameResult(
                game_id=game_id,
                spectator_url=spectator_url,
                outcome=state.outcome,
            )
    else:
        game = client.games.create(model_id=model_id)
        game_id = game.game_id
        observation = game.observation
        spectator_url = game.spectator_url

    logger.info("Game %s started. Watch: %s", game_id, spectator_url)

    consecutive_invalid = 0

    while True:
        try:
            action = agent_fn(observation)
        except Exception as e:
            raise RuntimeError(
                f"Agent function failed [game={game_id}, turn={observation.turn}]"
            ) from e

        try:
            result = client.games.action(game_id, action)
            consecutive_invalid = 0
        except InvalidActionError as e:
            consecutive_invalid += 1
            logger.warning(
                "Invalid action (%d/%d): %s [code=%s] "
                "[game=%s, turn=%d, action=%s]",
                consecutive_invalid,
                max_invalid_actions,
                e.message,
                e.code,
                game_id,
                observation.turn,
                action.model_dump_json(by_alias=True),
            )
            if consecutive_invalid >= max_invalid_actions:
                raise
            continue
        except RateLimitError as e:
            logger.warning(
                "Rate limited. Sleeping %d seconds. [game=%s, turn=%d]",
                e.retry_after,
                game_id,
                observation.turn,
            )
            time.sleep(e.retry_after)
            continue
        except GameOverError as e:
            logger.info("Game %s ended between turns: %s", game_id, e.message)
            return GameResult(
                game_id=game_id,
                spectator_url=spectator_url,
                outcome=e.outcome,
            )

        if on_step is not None:
            on_step(observation, action)

        observation = result.observation

        if not isinstance(result.outcome, InProgressOutcome):
            logger.info("Game %s finished: %s", game_id, result.outcome.status)
            return GameResult(
                game_id=game_id,
                spectator_url=spectator_url,
                outcome=result.outcome,
            )


async def async_run_game(
    client: AsyncCrawlerClient,
    agent_fn: Callable[[Observation], Action],
    *,
    model_id: str | None = None,
    game_id: str | None = None,
    max_invalid_actions: int = 5,
    on_step: Callable[[Observation, Action], None] | None = None,
) -> GameResult:
    """Async version of run_game."""
    if game_id is not None:
        state = await client.games.get(game_id)
        observation = state.observation
        spectator_url = ""
        if not isinstance(state.outcome, InProgressOutcome):
            return GameResult(
                game_id=game_id,
                spectator_url=spectator_url,
                outcome=state.outcome,
            )
    else:
        game = await client.games.create(model_id=model_id)
        game_id = game.game_id
        observation = game.observation
        spectator_url = game.spectator_url

    logger.info("Game %s started. Watch: %s", game_id, spectator_url)

    consecutive_invalid = 0

    while True:
        try:
            action = agent_fn(observation)
        except Exception as e:
            raise RuntimeError(
                f"Agent function failed [game={game_id}, turn={observation.turn}]"
            ) from e

        try:
            result = await client.games.action(game_id, action)
            consecutive_invalid = 0
        except InvalidActionError as e:
            consecutive_invalid += 1
            logger.warning(
                "Invalid action (%d/%d): %s [code=%s] "
                "[game=%s, turn=%d, action=%s]",
                consecutive_invalid,
                max_invalid_actions,
                e.message,
                e.code,
                game_id,
                observation.turn,
                action.model_dump_json(by_alias=True),
            )
            if consecutive_invalid >= max_invalid_actions:
                raise
            continue
        except RateLimitError as e:
            logger.warning(
                "Rate limited. Sleeping %d seconds. [game=%s, turn=%d]",
                e.retry_after,
                game_id,
                observation.turn,
            )
            await asyncio.sleep(e.retry_after)
            continue
        except GameOverError as e:
            logger.info("Game %s ended between turns: %s", game_id, e.message)
            return GameResult(
                game_id=game_id,
                spectator_url=spectator_url,
                outcome=e.outcome,
            )

        if on_step is not None:
            on_step(observation, action)

        observation = result.observation

        if not isinstance(result.outcome, InProgressOutcome):
            logger.info("Game %s finished: %s", game_id, result.outcome.status)
            return GameResult(
                game_id=game_id,
                spectator_url=spectator_url,
                outcome=result.outcome,
            )
