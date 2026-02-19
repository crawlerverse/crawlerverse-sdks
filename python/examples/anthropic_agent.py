"""Example: Use Anthropic Claude to play Crawler.

Usage:
    export CRAWLERVERSE_API_KEY=cra_...
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/anthropic_agent.py

    # Resume a game (if it crashes or hits max turns):
    GAME_ID=<uuid> python examples/anthropic_agent.py

    # Enable debug diagnostics (local map, move validation):
    CRAWLERVERSE_DEBUG=1 python examples/anthropic_agent.py

Requirements (not included in crawlerverse):
    pip install anthropic
"""

from __future__ import annotations

import json
import logging
import os

from anthropic import Anthropic
from diagnostics import create_debug_callback

from crawlerverse import (
    Action,
    Attack,
    CrawlerClient,
    Direction,
    Drop,
    EnterPortal,
    Equip,
    Move,
    Observation,
    Pickup,
    RangedAttack,
    Use,
    Wait,
    run_game,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("crawlerverse")
log.setLevel(logging.DEBUG)

SYSTEM_PROMPT = """\
You are an AI agent playing Crawler, a roguelike dungeon game.
Each turn you receive an observation and must choose ONE action.
Respond with a JSON object (no markdown, no explanation).

## Actions
  {"action": "move", "direction": "<dir>"}
  {"action": "attack", "direction": "<dir>"}
  {"action": "ranged_attack", "direction": "<dir>", "distance": <1-15>}
  {"action": "pickup"}
  {"action": "drop", "itemType": "<item>"}
  {"action": "use", "itemType": "<item>"}
  {"action": "equip", "itemType": "<item>"}
  {"action": "wait"}
  {"action": "enter_portal"}

Directions: north, south, east, west, northeast, northwest, southeast, southwest

## Strategy Tips
- Kill monsters to clear the path. Attack adjacent monsters.
- Pick up items (potions, weapons, armor) — they help you survive.
- Equip weapons and armor for better stats.
- Use health potions when HP is low.
- Find stairs down to descend to the next floor.
- Explore systematically; avoid getting surrounded.

Always include a "reasoning" field explaining your decision."""

ACTION_MAP: dict[str, type[Action]] = {
    "move": Move,
    "attack": Attack,
    "wait": Wait,
    "pickup": Pickup,
    "drop": Drop,
    "use": Use,
    "equip": Equip,
    "enter_portal": EnterPortal,
    "ranged_attack": RangedAttack,
}


def format_observation(obs: Observation) -> str:
    """Format observation into a detailed prompt for Claude."""
    p = obs.player
    lines = [
        f"Turn {obs.turn} | Floor {obs.floor}",
        f"HP: {p.hp}/{p.max_hp} | ATK: {p.attack} | DEF: {p.defense}",
        f"Position: ({p.position[0]}, {p.position[1]})",
    ]

    if p.equipped_weapon:
        lines.append(f"Weapon: {p.equipped_weapon}")
    if p.equipped_armor:
        lines.append(f"Armor: {p.equipped_armor}")

    if obs.inventory:
        inv = ", ".join(f"{i.name} ({i.type})" for i in obs.inventory)
        lines.append(f"Inventory: {inv}")

    passable = [d.value for d in Direction if obs.can_move(d)]
    lines.append(f"Passable directions: {', '.join(passable) if passable else 'none'}")

    lines.append("")
    lines.append("Visible tiles:")
    for tile in obs.visible_tiles:
        parts = [f"  ({tile.x},{tile.y}) {tile.type}"]
        if tile.monster:
            m = tile.monster
            parts.append(f"[MONSTER: {m.type} HP:{m.hp}/{m.max_hp}]")
        if tile.items:
            parts.append(f"[ITEMS: {', '.join(tile.items)}]")
        lines.append(" ".join(parts))

    if obs.messages:
        lines.append("")
        lines.append("Messages:")
        for msg in obs.messages:
            lines.append(f"  {msg}")

    return "\n".join(lines)


def parse_action(raw: str) -> Action:
    """Parse Claude's response into an Action, with fallback to Wait."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Extract JSON if surrounded by other text
    if not text.startswith("{"):
        start = text.find("{")
        if start >= 0:
            end = text.rfind("}")
            if end > start:
                text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Failed to parse Claude response as JSON: %s", text[:100])
        return Wait(reasoning="Failed to parse response")

    action_type = data.get("action", "wait")
    cls = ACTION_MAP.get(action_type)
    if cls is None:
        log.warning("Unknown action type: %s", action_type)
        return Wait(reasoning=f"Unknown action: {action_type}")

    # Build kwargs from the response, filtering to known fields
    valid_fields = set(cls.model_fields.keys())
    kwargs = {}
    for k, v in data.items():
        if k != "action" and k in valid_fields:
            kwargs[k] = v

    # Handle camelCase -> snake_case for itemType
    if "itemType" in data and "item_type" in valid_fields:
        kwargs["item_type"] = data["itemType"]

    try:
        return cls(**kwargs)
    except Exception as e:
        log.warning("Failed to construct %s: %s", action_type, e)
        return Wait(reasoning=f"Failed to construct {action_type}")


def make_agent(model: str = "claude-haiku-4-5-20251001"):
    """Create an agent function that uses Anthropic Claude to decide actions."""
    client = Anthropic()
    messages: list[dict[str, str]] = []

    def agent(obs: Observation) -> Action:
        prompt = format_observation(obs)
        messages.append({"role": "user", "content": prompt})

        # Prefill assistant turn with "{" to force JSON output
        prefill = {"role": "assistant", "content": "{"}
        response = client.messages.create(
            model=model,
            system=SYSTEM_PROMPT,
            messages=[*messages, prefill],
            temperature=0.3,
            max_tokens=200,
        )

        reply = "{" + response.content[0].text
        messages.append({"role": "assistant", "content": reply})

        action = parse_action(reply)
        log.info("Turn %d: %s", obs.turn, action.model_dump_json(by_alias=True))
        return action

    return agent


def main():
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    model_id = os.environ.get("MODEL_ID", f"anthropic/{model}")

    resume_id = os.environ.get("GAME_ID")

    if resume_id:
        print(f"Resuming game: {resume_id}")
    else:
        print(f"Starting game with model: {model} (leaderboard ID: {model_id})")
    print()

    agent = make_agent(model=model)

    base_url = os.environ.get(
        "CRAWLERVERSE_BASE_URL", "http://localhost:3000/api/agent"
    )

    with CrawlerClient(base_url=base_url) as client:
        result = run_game(
            client,
            agent,
            model_id=model_id,
            game_id=resume_id,
            on_step=create_debug_callback(),
        )

    outcome = result.outcome
    print()
    print(f"Game over! {outcome.status}")
    print(f"  Floor reached: {outcome.floor}")
    print(f"  Total turns: {outcome.turns}")
    if hasattr(outcome, "result"):
        print(f"  Result: {outcome.result}")
    print(f"  Watch replay: {result.spectator_url}")


if __name__ == "__main__":
    main()
