"""Action models for submitting game actions."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from crawlerverse.models import CrawlerModel
from crawlerverse.types import Direction


class _ActionBase(CrawlerModel):
    """Base for action models that excludes None fields by default."""

    def model_dump(self, *, exclude_none: bool = True, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(exclude_none=exclude_none, **kwargs)

    def model_dump_json(
        self, *, exclude_none: bool = True, **kwargs: Any
    ) -> str:
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)


class Move(_ActionBase):
    action: Literal["move"] = "move"
    direction: Direction
    reasoning: str | None = None


class Attack(_ActionBase):
    action: Literal["attack"] = "attack"
    direction: Direction
    reasoning: str | None = None


class Wait(_ActionBase):
    action: Literal["wait"] = "wait"
    reasoning: str | None = None


class Pickup(_ActionBase):
    action: Literal["pickup"] = "pickup"
    reasoning: str | None = None


class Drop(_ActionBase):
    action: Literal["drop"] = "drop"
    item_type: Annotated[str, Field(min_length=1)]
    reasoning: str | None = None


class Use(_ActionBase):
    action: Literal["use"] = "use"
    item_type: Annotated[str, Field(min_length=1)]
    reasoning: str | None = None


class Equip(_ActionBase):
    action: Literal["equip"] = "equip"
    item_type: Annotated[str, Field(min_length=1)]
    reasoning: str | None = None


class EnterPortal(_ActionBase):
    action: Literal["enter_portal"] = "enter_portal"
    reasoning: str | None = None


class RangedAttack(_ActionBase):
    action: Literal["ranged_attack"] = "ranged_attack"
    direction: Direction
    distance: Annotated[int, Field(gt=0)]
    reasoning: str | None = None


Action = (
    Move | Attack | Wait | Pickup | Drop | Use | Equip | EnterPortal | RangedAttack
)
