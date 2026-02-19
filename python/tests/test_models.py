import json

from crawlerverse.models import (
    AbandonedOutcome,
    CompletedOutcome,
    CreateGameResponse,
    GameStateResponse,
    HealthResponse,
    InProgressOutcome,
    ListGamesResponse,
    Monster,
    Observation,
    Player,
    VisibleTile,
    parse_outcome,
)
from crawlerverse.types import Direction, TileType

# --- Fixtures ---

PLAYER_JSON = {
    "position": [5, 8],
    "hp": 12,
    "maxHp": 20,
    "attack": 8,
    "defense": 4,
    "equippedWeapon": "iron-sword",
    "equippedArmor": None,
}

MONSTER_JSON = {"type": "rat", "hp": 3, "maxHp": 5}

TILE_WITH_MONSTER_JSON = {
    "x": 6,
    "y": 8,
    "type": "floor",
    "items": [],
    "monster": MONSTER_JSON,
}

TILE_WALL_JSON = {"x": 5, "y": 7, "type": "wall", "items": []}

TILE_WITH_ITEMS_JSON = {
    "x": 5,
    "y": 8,
    "type": "floor",
    "items": ["gold-coin", "health-potion"],
}

INVENTORY_JSON = [
    {"id": "item-1", "type": "weapon", "name": "iron-sword"},
    {"id": "item-2", "type": "consumable", "name": "health-potion"},
]

OBSERVATION_JSON = {
    "turn": 47,
    "floor": 3,
    "player": PLAYER_JSON,
    "inventory": INVENTORY_JSON,
    "visibleTiles": [TILE_WITH_MONSTER_JSON, TILE_WALL_JSON, TILE_WITH_ITEMS_JSON],
    "messages": ["The rat bites you for 3 damage", "You attack the rat"],
}


class TestPlayer:
    def test_parse_from_camel_case(self):
        player = Player.model_validate(PLAYER_JSON)
        assert player.position == (5, 8)
        assert player.hp == 12
        assert player.max_hp == 20
        assert player.equipped_weapon == "iron-sword"
        assert player.equipped_armor is None

    def test_parse_from_snake_case(self):
        player = Player(position=(5, 8), hp=12, max_hp=20, attack=8, defense=4)
        assert player.max_hp == 20


class TestMonster:
    def test_parse(self):
        m = Monster.model_validate(MONSTER_JSON)
        assert m.type == "rat"
        assert m.hp == 3
        assert m.max_hp == 5


class TestVisibleTile:
    def test_parse_with_monster(self):
        tile = VisibleTile.model_validate(TILE_WITH_MONSTER_JSON)
        assert tile.x == 6
        assert tile.y == 8
        assert tile.type == TileType.FLOOR
        assert tile.monster is not None
        assert tile.monster.type == "rat"

    def test_parse_without_monster(self):
        tile = VisibleTile.model_validate(TILE_WALL_JSON)
        assert tile.type == TileType.WALL
        assert tile.monster is None


class TestObservation:
    def test_parse_full(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        assert obs.turn == 47
        assert obs.floor == 3
        assert obs.player.hp == 12
        assert len(obs.inventory) == 2
        assert len(obs.visible_tiles) == 3
        assert len(obs.messages) == 2

    def test_tile_at(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        tile = obs.tile_at(6, 8)
        assert tile is not None
        assert tile.monster is not None
        assert obs.tile_at(99, 99) is None

    def test_monsters(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        monsters = obs.monsters()
        assert len(monsters) == 1
        tile, monster = monsters[0]
        assert monster.type == "rat"
        assert tile.x == 6

    def test_nearest_monster(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        result = obs.nearest_monster()
        assert result is not None
        tile, monster = result
        assert monster.type == "rat"

    def test_items_at_feet(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        items = obs.items_at_feet()
        assert items == ["gold-coin", "health-potion"]

    def test_has_item(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        assert obs.has_item("iron-sword") is True
        assert obs.has_item("Iron-Sword") is True
        assert obs.has_item("gold-ring") is False

    def test_can_move(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        # EAST (6,8) has a monster — cannot move there
        assert obs.can_move(Direction.EAST) is False
        # NORTH (5,7) is a wall — cannot move there
        assert obs.can_move(Direction.NORTH) is False

    def test_can_move_clear_floor(self):
        """can_move returns True for a walkable tile with no monster."""
        obs_data = {
            **OBSERVATION_JSON,
            "visibleTiles": [
                {"x": 6, "y": 8, "type": "floor", "items": []},
                TILE_WALL_JSON,
                TILE_WITH_ITEMS_JSON,
            ],
        }
        obs = Observation.model_validate(obs_data)
        assert obs.can_move(Direction.EAST) is True

    def test_str(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        s = str(obs)
        assert "Turn 47" in s
        assert "Floor 3" in s
        assert "12/20" in s

    def test_serializes_to_camel_case(self):
        obs = Observation.model_validate(OBSERVATION_JSON)
        data = json.loads(obs.model_dump_json(by_alias=True))
        assert "visibleTiles" in data
        assert "maxHp" in data["player"]


class TestOutcomes:
    def test_in_progress(self):
        o = parse_outcome({"status": "in_progress"})
        assert isinstance(o, InProgressOutcome)

    def test_completed_victory(self):
        o = parse_outcome(
            {"status": "completed", "result": "victory", "floor": 5, "turns": 187}
        )
        assert isinstance(o, CompletedOutcome)
        assert o.result == "victory"
        assert o.floor == 5

    def test_completed_death(self):
        o = parse_outcome(
            {"status": "completed", "result": "death", "floor": 3, "turns": 47}
        )
        assert isinstance(o, CompletedOutcome)
        assert o.result == "death"

    def test_abandoned(self):
        o = parse_outcome(
            {"status": "abandoned", "reason": "timeout", "floor": 2, "turns": 30}
        )
        assert isinstance(o, AbandonedOutcome)
        assert o.reason == "timeout"


class TestCreateGameResponse:
    def test_parse(self):
        r = CreateGameResponse.model_validate(
            {
                "gameId": "abc-123",
                "observation": OBSERVATION_JSON,
                "spectatorUrl": "https://crawlerver.se/spectate/abc-123",
            }
        )
        assert r.game_id == "abc-123"
        assert r.observation.turn == 47
        assert r.spectator_url == "https://crawlerver.se/spectate/abc-123"


class TestGameStateResponse:
    def test_parse_in_progress(self):
        r = GameStateResponse.model_validate(
            {
                "observation": OBSERVATION_JSON,
                "outcome": {"status": "in_progress"},
            }
        )
        assert isinstance(r.outcome, InProgressOutcome)


class TestListGamesResponse:
    def test_parse(self):
        r = ListGamesResponse.model_validate(
            {
                "games": [
                    {
                        "gameId": "abc-123",
                        "status": "completed",
                        "modelId": "gpt-4o",
                        "floorReached": 5,
                        "totalTurns": 187,
                        "result": "victory",
                        "startedAt": "2025-02-02T10:30:00Z",
                        "finishedAt": "2025-02-02T10:45:00Z",
                        "spectatorUrl": "https://crawlerver.se/spectate/abc-123",
                    }
                ],
                "hasMore": False,
            }
        )
        assert len(r.games) == 1
        assert r.games[0].game_id == "abc-123"
        assert r.games[0].floor_reached == 5
        assert r.has_more is False


class TestHealthResponse:
    def test_parse(self):
        r = HealthResponse.model_validate(
            {
                "status": "ok",
                "service": "crawler-agent-api",
                "timestamp": "2025-02-02T10:30:00Z",
            }
        )
        assert r.status == "ok"
