"""Diagnostic toolkit for debugging agent behavior.

Enable by setting CRAWLERVERSE_DEBUG=1 in your environment.

Detects:
  - Invalid moves: LLM chose a direction blocked by a wall or monster
  - Position mismatches: position after action doesn't match expected delta
  - Unexpected movement: position changed on a non-move action

Each move action also prints a 5x5 ASCII grid around the player so you can
visually verify the local map layout.

Usage with run_game (openai_agent.py, anthropic_agent.py):

    from diagnostics import create_debug_callback

    tracker = create_debug_callback()
    run_game(client, agent, on_step=tracker)

Usage with a manual loop (local_llm_agent.py):

    from diagnostics import DebugTracker

    tracker = DebugTracker()
    ...
    tracker.on_action(obs, action)  # call BEFORE submitting to API
    result = client.games.action(game_id, action)
    tracker.on_result(result.observation)  # call AFTER getting response
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from crawlerverse import Action, Observation

_DIRECTION_OFFSETS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
}

_TILE_CHARS: dict[str, str] = {
    "wall": "#",
    "floor": ".",
    "door": "+",
    "stairs_down": ">",
    "stairs_up": "<",
    "portal": "%",
}


def _is_debug() -> bool:
    return os.environ.get("CRAWLERVERSE_DEBUG", "").strip() in ("1", "true", "yes")


def _tile_char(tile) -> str:  # noqa: ANN001 — VisibleTile
    """Single character for a tile, for the ASCII grid."""
    if tile is None:
        return "?"
    if tile.monster:
        return "M"
    return _TILE_CHARS.get(tile.type.value, tile.type.value[0])


class DebugTracker:
    """Tracks agent state across turns and prints diagnostics.

    Call ``on_action(obs, action)`` before submitting each action, and
    ``on_result(new_obs)`` after receiving the API response.
    """

    def __init__(self) -> None:
        self.enabled = _is_debug()
        self._prev_pos: tuple[int, int] | None = None
        self._prev_action_name: str | None = None
        self._prev_direction: str | None = None

    def on_action(self, obs: Observation, action: Action) -> None:
        """Diagnose the chosen action against the current observation."""
        if not self.enabled:
            return

        from crawlerverse import Move

        # Check for position anomalies vs previous turn
        self._check_position(obs)

        if not isinstance(action, Move):
            self._prev_pos = obs.player.position
            self._prev_action_name = type(action).__name__
            self._prev_direction = None
            return

        px, py = obs.player.position
        direction = action.direction

        # Print local map
        self._print_grid(obs, px, py, direction)

        # Check validity
        can = obs.can_move(action.direction)
        dx, dy = _DIRECTION_OFFSETS.get(direction, (0, 0))
        target_tile = obs.tile_at(px + dx, py + dy)
        if target_tile is None:
            target_desc = "NOT VISIBLE"
        else:
            target_desc = target_tile.type.value
            if target_tile.monster:
                target_desc += f" [monster: {target_tile.monster.type}]"

        print(
            f"  [DIAG] Target ({px + dx},{py + dy}): {target_desc} | "
            f"can_move({direction})={can}"
        )

        if not can:
            print(
                "  [DIAG] *** INVALID MOVE *** "
                "LLM chose a blocked direction"
            )

        self._prev_pos = obs.player.position
        self._prev_action_name = "Move"
        self._prev_direction = direction

    def on_result(self, obs: Observation) -> None:
        """Check the observation returned after an action for anomalies.

        Optional — gives immediate feedback rather than waiting for
        the next ``on_action`` call.
        """
        if not self.enabled:
            return
        self._check_position(obs)

    # ------------------------------------------------------------------

    def _check_position(self, obs: Observation) -> None:
        """Compare current position with expected position from last action."""
        if self._prev_pos is None:
            return

        dx = obs.player.position[0] - self._prev_pos[0]
        dy = obs.player.position[1] - self._prev_pos[1]

        if self._prev_action_name == "Move" and self._prev_direction:
            ex, ey = _DIRECTION_OFFSETS.get(self._prev_direction, (0, 0))
            if (dx, dy) == (ex, ey):
                return  # move succeeded as expected
            if (dx, dy) == (0, 0):
                return  # move was blocked — normal
            print(
                f"  [DIAG] *** POSITION MISMATCH *** "
                f"prev={self._prev_pos} action=move {self._prev_direction} "
                f"expected delta=({ex},{ey}) actual delta=({dx},{dy}) "
                f"new pos={obs.player.position}"
            )
        elif self._prev_action_name != "Move" and (dx, dy) != (0, 0):
            print(
                f"  [DIAG] *** UNEXPECTED MOVEMENT *** "
                f"prev={self._prev_pos} action={self._prev_action_name} "
                f"but position changed by ({dx},{dy}) "
                f"to {obs.player.position}"
            )

    def _print_grid(
        self,
        obs: Observation,
        px: int,
        py: int,
        direction: str,
    ) -> None:
        """Print a 5x5 ASCII grid centred on the player."""
        print(
            f"  [DIAG] Player at ({px},{py}), wants to move {direction}"
        )
        print(
            "  [DIAG] Local map "
            "(@ = player, # = wall, . = floor, M = monster, ? = unseen):"
        )
        for row_dy in range(-2, 3):
            row = ""
            for col_dx in range(-2, 3):
                if col_dx == 0 and row_dy == 0:
                    row += " @"
                else:
                    tile = obs.tile_at(px + col_dx, py + row_dy)
                    row += " " + _tile_char(tile)
            print(f"  [DIAG]  {row}")


def create_debug_callback() -> Callable[[Observation, Action], None] | None:
    """Create an ``on_step`` callback for ``run_game``, or None if disabled.

    Note: ``run_game`` calls ``on_step(obs, action)`` with the observation
    *before* the action was submitted (the pre-action state).
    """
    if not _is_debug():
        return None

    tracker = DebugTracker()

    def _on_step(obs: Observation, action: Action) -> None:
        tracker.on_action(obs, action)

    return _on_step
