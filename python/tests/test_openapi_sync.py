"""Validate that SDK models stay in sync with the OpenAPI spec.

This test fetches the canonical OpenAPI spec from crawlerver.se and checks
that our Pydantic models have matching fields. If this test fails,
the API has changed and the SDK needs updating.

Set OPENAPI_SPEC_URL to override the spec URL (e.g. for local development).
Set OPENAPI_SPEC_PATH to use a local file instead of fetching.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import httpx
import pytest
import yaml

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
from crawlerverse.models import (
    AbandonedOutcome,
    ActionResponse,
    CompletedOutcome,
    CrawlerModel,
    CreateGameResponse,
    GameStateResponse,
    GameSummary,
    HealthResponse,
    InProgressOutcome,
    InventoryItem,
    ListGamesResponse,
    Monster,
    Observation,
    Player,
    VisibleTile,
)

OPENAPI_SPEC_URL = os.environ.get(
    "OPENAPI_SPEC_URL",
    "https://crawlerver.se/agent-api-openapi.yaml",
)
OPENAPI_SPEC_PATH = os.environ.get("OPENAPI_SPEC_PATH")

# Map OpenAPI schema names to our Pydantic models
SCHEMA_MODEL_MAP: dict[str, type[CrawlerModel]] = {
    "Observation": Observation,
    "Player": Player,
    "InventoryItem": InventoryItem,
    "VisibleTile": VisibleTile,
    "Monster": Monster,
    "HealthResponse": HealthResponse,
    "CreateGameResponse": CreateGameResponse,
    "GameStateResponse": GameStateResponse,
    "ListGamesResponse": ListGamesResponse,
    "GameSummary": GameSummary,
    "ActionResponse": ActionResponse,
    "InProgressOutcome": InProgressOutcome,
    "CompletedOutcome": CompletedOutcome,
    "AbandonedOutcome": AbandonedOutcome,
    "MoveAction": Move,
    "AttackAction": Attack,
    "WaitAction": Wait,
    "PickupAction": Pickup,
    "DropAction": Drop,
    "UseAction": Use,
    "EquipAction": Equip,
    "EnterPortalAction": EnterPortal,
    "RangedAttackAction": RangedAttack,
}


@pytest.fixture(scope="module")
def openapi_schemas() -> dict[str, Any]:
    # Prefer local file if OPENAPI_SPEC_PATH is set
    if OPENAPI_SPEC_PATH:
        path = Path(OPENAPI_SPEC_PATH)
        if not path.exists():
            pytest.skip(f"OpenAPI spec not found at {path}")
        with open(path) as f:
            spec = yaml.safe_load(f)
        return spec["components"]["schemas"]

    # Otherwise fetch from URL
    try:
        resp = httpx.get(OPENAPI_SPEC_URL, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Could not fetch OpenAPI spec from {OPENAPI_SPEC_URL}: {exc}")
    spec = yaml.safe_load(resp.text)
    return spec["components"]["schemas"]


def _get_schema_field_names(schema: dict[str, Any]) -> set[str]:
    """Extract field names from an OpenAPI schema."""
    props = schema.get("properties", {})
    return set(props.keys())


def _get_model_field_aliases(model: type[CrawlerModel]) -> set[str]:
    """Get the camelCase aliases (wire names) for a Pydantic model."""
    aliases = set()
    for name, field_info in model.model_fields.items():
        alias = field_info.alias
        if alias is not None:
            aliases.add(alias)
        else:
            # If alias_generator is set, compute it
            gen = model.model_config.get("alias_generator")
            if gen:
                aliases.add(gen(name))
            else:
                aliases.add(name)
    return aliases


def _is_literal_with_default(field_info: Any) -> bool:
    """Check if a field is a Literal type with a matching default.

    Action models use ``action: Literal["move"] = "move"`` so users
    don't have to pass the discriminator.  These are *effectively*
    required on the wire (the default always matches the only allowed
    value), so the test should treat them as required.
    """
    if field_info.is_required():
        return False  # already required, nothing special
    annotation = field_info.annotation
    origin = get_origin(annotation)
    if origin is Literal:
        args = get_args(annotation)
        if len(args) == 1 and field_info.default == args[0]:
            return True
    return False


@pytest.mark.parametrize(
    "schema_name,model",
    list(SCHEMA_MODEL_MAP.items()),
    ids=list(SCHEMA_MODEL_MAP.keys()),
)
def test_model_fields_match_openapi(
    schema_name: str,
    model: type[CrawlerModel],
    openapi_schemas: dict[str, Any],
):
    """Each SDK model must have all fields from the OpenAPI spec."""
    schema = openapi_schemas[schema_name]
    spec_fields = _get_schema_field_names(schema)
    model_aliases = _get_model_field_aliases(model)

    missing = spec_fields - model_aliases
    assert not missing, (
        f"SDK model {model.__name__} is missing fields from OpenAPI spec "
        f"'{schema_name}': {missing}"
    )


@pytest.mark.parametrize(
    "schema_name,model",
    list(SCHEMA_MODEL_MAP.items()),
    ids=list(SCHEMA_MODEL_MAP.keys()),
)
def test_required_fields_match(
    schema_name: str,
    model: type[CrawlerModel],
    openapi_schemas: dict[str, Any],
):
    """Required fields in OpenAPI spec must be required in SDK models."""
    schema = openapi_schemas[schema_name]
    required_in_spec = set(schema.get("required", []))

    # Get model fields that are required or effectively required
    # (Literal discriminator fields with a matching default).
    required_in_model = set()
    for name, field_info in model.model_fields.items():
        alias = field_info.alias
        if alias is None:
            gen = model.model_config.get("alias_generator")
            alias = gen(name) if gen else name
        if field_info.is_required() or _is_literal_with_default(field_info):
            required_in_model.add(alias)

    missing_required = required_in_spec - required_in_model
    assert not missing_required, (
        f"SDK model {model.__name__} has fields that should be required "
        f"per OpenAPI spec '{schema_name}': {missing_required}"
    )
