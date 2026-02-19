"""Pydantic models for Crawler Agent API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic.alias_generators import to_camel

from crawlerverse.types import Direction, GameStatus, TileType

_DIRECTION_OFFSETS: dict[Direction, tuple[int, int]] = {
    Direction.NORTH: (0, -1),
    Direction.SOUTH: (0, 1),
    Direction.EAST: (1, 0),
    Direction.WEST: (-1, 0),
    Direction.NORTHEAST: (1, -1),
    Direction.NORTHWEST: (-1, -1),
    Direction.SOUTHEAST: (1, 1),
    Direction.SOUTHWEST: (-1, 1),
}

_WALKABLE_TILES = {
    TileType.FLOOR,
    TileType.DOOR,
    TileType.STAIRS_DOWN,
    TileType.STAIRS_UP,
    TileType.PORTAL,
}


class CrawlerModel(BaseModel):
    """Base model with camelCase alias support."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class Monster(CrawlerModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True
    )

    type: str
    hp: int
    max_hp: int


class VisibleTile(CrawlerModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True
    )

    x: int
    y: int
    type: TileType
    items: list[str]
    monster: Monster | None = None


class InventoryItem(CrawlerModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True
    )

    id: str
    type: str
    name: str


class Player(CrawlerModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True
    )

    position: tuple[int, int]
    hp: int
    max_hp: int
    attack: int
    defense: int
    equipped_weapon: str | None = None
    equipped_armor: str | None = None


class Observation(CrawlerModel):
    """The agent's view of the game world for a single turn."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True
    )

    turn: int
    floor: int
    player: Player
    inventory: list[InventoryItem]
    visible_tiles: list[VisibleTile]
    messages: list[str]

    def tile_at(self, x: int, y: int) -> VisibleTile | None:
        """Return the visible tile at the given coordinates, or None."""
        for tile in self.visible_tiles:
            if tile.x == x and tile.y == y:
                return tile
        return None

    def monsters(self) -> list[tuple[VisibleTile, Monster]]:
        """Return all visible tiles that contain a monster."""
        return [
            (tile, tile.monster)
            for tile in self.visible_tiles
            if tile.monster is not None
        ]

    def nearest_monster(self) -> tuple[VisibleTile, Monster] | None:
        """Return the closest monster by Manhattan distance, or None."""
        px, py = self.player.position
        result: tuple[VisibleTile, Monster] | None = None
        best_dist = float("inf")
        for tile, monster in self.monsters():
            dist = abs(tile.x - px) + abs(tile.y - py)
            if dist < best_dist:
                best_dist = dist
                result = (tile, monster)
        return result

    def items_at_feet(self) -> list[str]:
        """Return items on the tile the player is standing on."""
        px, py = self.player.position
        tile = self.tile_at(px, py)
        return tile.items if tile else []

    def has_item(self, name: str) -> bool:
        """Check if the player has an item by name (case-insensitive)."""
        name_lower = name.lower()
        return any(item.name.lower() == name_lower for item in self.inventory)

    def can_move(self, direction: Direction) -> bool:
        """Check if the player can move in the given direction.

        Returns False if the tile is not visible, not walkable, or occupied
        by a monster.
        """
        px, py = self.player.position
        dx, dy = _DIRECTION_OFFSETS[direction]
        tile = self.tile_at(px + dx, py + dy)
        if tile is None:
            return False
        if tile.monster is not None:
            return False
        return tile.type in _WALKABLE_TILES

    def __str__(self) -> str:
        p = self.player
        monster_count = len(self.monsters())
        item_count = sum(len(t.items) for t in self.visible_tiles)
        inv_names = ", ".join(i.name for i in self.inventory) or "empty"
        lines = [
            f"Turn {self.turn} | Floor {self.floor} | HP {p.hp}/{p.max_hp}"
            f" | Pos ({p.position[0]},{p.position[1]})",
            f"Inventory: {inv_names}",
            f"Visible: {monster_count} monsters, {item_count} items",
        ]
        if self.messages:
            lines.append(f'Messages: "{self.messages[-1]}"')
        return "\n".join(lines)


class InProgressOutcome(CrawlerModel):
    status: Literal["in_progress"]


class CompletedOutcome(CrawlerModel):
    status: Literal["completed"]
    result: Literal["victory", "death"]
    floor: int
    turns: int


class AbandonedOutcome(CrawlerModel):
    status: Literal["abandoned"]
    reason: Literal["timeout", "disconnected"]
    floor: int
    turns: int


Outcome = Annotated[
    InProgressOutcome | CompletedOutcome | AbandonedOutcome,
    Field(discriminator="status"),
]

_outcome_adapter: TypeAdapter[  # type: ignore[type-arg]
    InProgressOutcome | CompletedOutcome | AbandonedOutcome
] = TypeAdapter(Outcome)


def parse_outcome(
    data: dict,
) -> InProgressOutcome | CompletedOutcome | AbandonedOutcome:
    """Parse an outcome dict into the appropriate typed model."""
    return _outcome_adapter.validate_python(data)


class CreateGameResponse(CrawlerModel):
    game_id: str
    observation: Observation
    spectator_url: str


class ActionResponse(CrawlerModel):
    observation: Observation
    outcome: Outcome


class GameStateResponse(CrawlerModel):
    observation: Observation
    outcome: Outcome


class GameSummary(CrawlerModel):
    game_id: str
    status: GameStatus
    model_id: str | None = None
    floor_reached: int
    total_turns: int
    result: Literal["victory", "death"] | None = None
    started_at: datetime
    finished_at: datetime | None = None
    spectator_url: str


class ListGamesResponse(CrawlerModel):
    games: list[GameSummary]
    has_more: bool


class HealthResponse(CrawlerModel):
    status: str
    service: str
    timestamp: datetime


class AbandonGameResponse(CrawlerModel):
    game_id: str
    status: str
    floor: int
    turns: int


class GameResult(CrawlerModel):
    """Returned by run_game() with full game context."""

    game_id: str
    spectator_url: str
    outcome: CompletedOutcome | AbandonedOutcome
