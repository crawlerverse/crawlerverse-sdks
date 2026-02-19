from crawlerverse.types import Direction, GameStatus, TileType


def test_direction_values():
    assert Direction.NORTH == "north"
    assert Direction.SOUTHEAST == "southeast"
    assert len(Direction) == 8


def test_direction_from_string():
    assert Direction("north") is Direction.NORTH


def test_game_status_values():
    assert GameStatus.IN_PROGRESS == "in_progress"
    assert GameStatus.COMPLETED == "completed"
    assert GameStatus.ABANDONED == "abandoned"


def test_tile_type_values():
    assert TileType.FLOOR == "floor"
    assert TileType.STAIRS_DOWN == "stairs_down"
    assert TileType.PORTAL == "portal"
    assert len(TileType) == 6
