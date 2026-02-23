"""Example: Run a local LLM agent against a local Crawler API.

Usage:
    # Start local Supabase + web app first:
    #   pnpm --filter @crawler/web supabase:start
    #   pnpm --filter @crawler/web dev

    export CRAWLERVERSE_API_KEY=cra_...
    export OPENAI_BASE_URL=http://mac-mini.local:1234/v1
    export OPENAI_MODEL=gpt-oss:20b
    python examples/local_llm_agent.py

    # Resume a game (if it crashes or hits max turns):
    GAME_ID=<uuid> python examples/local_llm_agent.py

    # Enable debug diagnostics (local map, move validation):
    CRAWLERVERSE_DEBUG=1 python examples/local_llm_agent.py

Works with any OpenAI-compatible API (Ollama, LMStudio, etc.)
by setting OPENAI_BASE_URL.

Requirements (not included in crawlerverse):
    pip install openai
"""

from __future__ import annotations

import json
import logging
import os

from diagnostics import DebugTracker
from openai import OpenAI

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
)
from crawlerverse.exceptions import (
    CrawlerAPIError,
    GameOverError,
    InvalidActionError,
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
  {"action": "pickup"}
  {"action": "use", "itemType": "<item>"}
  {"action": "equip", "itemType": "<item>"}
  {"action": "wait"}
  {"action": "enter_portal"}

Directions: north, south, east, west, northeast, northwest, southeast, southwest

## Strategy
- Attack adjacent monsters.
- Pick up items when standing on them.
- Use health potions when HP is low.
- Explore by moving to floor tiles.
- Find and enter stairs to go deeper.

Respond ONLY with JSON. Include a "reasoning" field."""

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
    """Format observation into a detailed prompt for the LLM."""
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
    """Parse LLM response into an Action, with fallback to Wait."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try to extract JSON from response
    if not text.startswith("{"):
        start = text.find("{")
        if start >= 0:
            end = text.rfind("}")
            if end > start:
                text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Parse fail: %s", text[:200])
        return Wait(reasoning="parse error")

    action_type = data.get("action", "wait")
    cls = ACTION_MAP.get(action_type)
    if cls is None:
        return Wait(reasoning=f"unknown: {action_type}")

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
        return Wait(reasoning=f"construct error: {e}")


def main():
    max_turns = int(os.environ.get("MAX_TURNS", "25"))
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    model_id = os.environ.get("MODEL_ID", f"local/{model}")
    base_url = os.environ.get(
        "CRAWLERVERSE_BASE_URL", "https://www.crawlerver.se/api/agent"
    )

    print(f"Model: {model} (leaderboard ID: {model_id})")
    print(f"API: {base_url}")
    print(f"Max turns: {max_turns}")
    print()

    llm = OpenAI(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ.get("OPENAI_API_KEY", "not-needed"),
    )
    conv: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    with CrawlerClient(
        api_key=os.environ["CRAWLERVERSE_API_KEY"],
        base_url=base_url,
    ) as client:
        resume_id = os.environ.get("GAME_ID")
        if resume_id:
            state = client.games.get(resume_id)
            if state.outcome.status != "in_progress":
                print(f"Game {resume_id} already ended ({state.outcome.status})")
                return
            game_id = resume_id
            obs = state.observation
            print(f"Resuming game: {game_id}")
        else:
            game = client.games.create(model_id=model_id)
            game_id = game.game_id
            obs = game.observation
            print(f"Game started: {game_id}")
            print(f"Spectate: {game.spectator_url}")
        print()

        debug = DebugTracker()

        for turn_num in range(max_turns):
            prompt = format_observation(obs)
            conv.append({"role": "user", "content": prompt})
            p = obs.player
            print(
                f"--- Turn {obs.turn} | Floor {obs.floor} "
                f"| HP: {p.hp}/{p.max_hp} "
                f"| Pos: ({p.position[0]},{p.position[1]}) ---"
            )

            resp = llm.chat.completions.create(
                model=model,
                messages=conv,
                temperature=0.3,
                max_tokens=200,
            )
            reply = resp.choices[0].message.content or ""
            conv.append({"role": "assistant", "content": reply})
            action = parse_action(reply)
            print(f"  LLM -> {action.model_dump_json(by_alias=True)}")
            debug.on_action(obs, action)

            try:
                result = client.games.action(game_id, action)
            except InvalidActionError as e:
                print(f"  Invalid action: {e}. Sending Wait.")
                result = client.games.action(game_id, Wait())
            except GameOverError:
                print("  Game ended (GameOverError).")
                try:
                    state = client.games.get(game_id)
                    o = state.outcome
                    print(f"  Status: {o.status}")
                    if hasattr(o, "result"):
                        print(f"  Result: {o.result}")
                    if hasattr(o, "floor"):
                        print(f"  Floor: {o.floor}, Turns: {o.turns}")
                except Exception:
                    pass
                break
            except CrawlerAPIError as e:
                print(f"  API error ({e.status_code}): {e}")
                # 500 likely means player died (server bug CRA-191)
                try:
                    state = client.games.get(game_id)
                    if state.outcome.status != "in_progress":
                        o = state.outcome
                        print(f"  Game over! {o.status}")
                        if hasattr(o, "result"):
                            print(f"  Result: {o.result}")
                        if hasattr(o, "floor"):
                            print(f"  Floor: {o.floor}, Turns: {o.turns}")
                        break
                except Exception:
                    pass
                continue

            obs = result.observation
            debug.on_result(obs)

            # Check if game ended
            if result.outcome.status != "in_progress":
                o = result.outcome
                print(f"\nGame over! {o.status}")
                if hasattr(o, "result"):
                    print(f"  Result: {o.result}")
                if hasattr(o, "floor"):
                    print(f"  Floor: {o.floor}, Turns: {o.turns}")
                break

            if obs.messages:
                for msg in obs.messages:
                    print(f"  >> {msg}")
        else:
            print(
                f"\nReached {max_turns} turns. "
                f"Floor: {obs.floor}, HP: {obs.player.hp}/{obs.player.max_hp}"
            )


if __name__ == "__main__":
    main()
