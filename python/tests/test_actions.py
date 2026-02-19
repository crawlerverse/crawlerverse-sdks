import json

from crawlerverse.actions import (
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
from crawlerverse.types import Direction


class TestMove:
    def test_defaults(self):
        a = Move(direction=Direction.NORTH)
        assert a.action == "move"
        assert a.direction == Direction.NORTH
        assert a.reasoning is None

    def test_with_reasoning(self):
        a = Move(direction=Direction.EAST, reasoning="Exploring east corridor")
        assert a.reasoning == "Exploring east corridor"

    def test_serializes_to_camel_case(self):
        a = Move(direction=Direction.NORTH)
        data = json.loads(a.model_dump_json(by_alias=True))
        assert data == {"action": "move", "direction": "north"}


class TestAttack:
    def test_defaults(self):
        a = Attack(direction=Direction.EAST)
        assert a.action == "attack"

    def test_serializes(self):
        attack = Attack(direction=Direction.EAST)
        data = json.loads(attack.model_dump_json(by_alias=True))
        assert data["action"] == "attack"
        assert data["direction"] == "east"


class TestWait:
    def test_defaults(self):
        assert Wait().action == "wait"


class TestPickup:
    def test_defaults(self):
        assert Pickup().action == "pickup"


class TestDrop:
    def test_requires_item_type(self):
        a = Drop(item_type="health-potion")
        assert a.action == "drop"
        data = json.loads(a.model_dump_json(by_alias=True))
        assert data["itemType"] == "health-potion"


class TestUse:
    def test_requires_item_type(self):
        a = Use(item_type="health-potion")
        assert a.action == "use"


class TestEquip:
    def test_requires_item_type(self):
        a = Equip(item_type="iron-sword")
        assert a.action == "equip"


class TestEnterPortal:
    def test_defaults(self):
        assert EnterPortal().action == "enter_portal"

    def test_serializes(self):
        data = json.loads(EnterPortal().model_dump_json(by_alias=True))
        assert data["action"] == "enter_portal"


class TestRangedAttack:
    def test_fields(self):
        a = RangedAttack(direction=Direction.SOUTH, distance=5)
        assert a.action == "ranged_attack"
        assert a.distance == 5


class TestActionUnionSerialization:
    def test_none_fields_excluded(self):
        a = Move(direction=Direction.NORTH)
        data = json.loads(a.model_dump_json(by_alias=True, exclude_none=True))
        assert "reasoning" not in data
