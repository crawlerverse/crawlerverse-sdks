"""Enums and type definitions for the Crawler Agent API."""

from enum import Enum


class Direction(str, Enum):
    """Cardinal and diagonal directions for movement and attacks."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"


class GameStatus(str, Enum):
    """Possible states of an agent game."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TileType(str, Enum):
    """Types of tiles visible in the game map."""

    FLOOR = "floor"
    WALL = "wall"
    STAIRS_DOWN = "stairs_down"
    STAIRS_UP = "stairs_up"
    DOOR = "door"
    PORTAL = "portal"
