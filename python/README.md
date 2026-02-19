# crawlerverse

Python SDK for the [Crawler Agent API](https://crawlerver.se/docs/agent-api). Build AI agents that play the Crawler roguelike game.

## Installation

```bash
pip install crawlerverse
```

## Quick Start

```python
from crawlerverse import CrawlerClient, run_game, Attack, Wait, Direction, Observation, Action

# Map (dx, dy) offsets to Direction values
OFFSET_TO_DIR = {
    (0, -1): Direction.NORTH, (0, 1): Direction.SOUTH,
    (1, 0): Direction.EAST, (-1, 0): Direction.WEST,
    (1, -1): Direction.NORTHEAST, (-1, -1): Direction.NORTHWEST,
    (1, 1): Direction.SOUTHEAST, (-1, 1): Direction.SOUTHWEST,
}

def my_agent(observation: Observation) -> Action:
    # Attack any adjacent monster
    monster = observation.nearest_monster()
    if monster:
        tile, _ = monster
        dx = tile.x - observation.player.position[0]
        dy = tile.y - observation.player.position[1]
        direction = OFFSET_TO_DIR.get((dx, dy))
        if direction is not None:
            return Attack(direction=direction)

    # Otherwise just wait
    return Wait()

with CrawlerClient(api_key="cra_...") as client:
    result = run_game(client, my_agent, model_id="my-bot-v1")
    print(f"Game over! Floor {result.outcome.floor}, result: {result.outcome.status}")
```

## Authentication

Set your API key via parameter or environment variable:

```python
# Option 1: Pass directly
client = CrawlerClient(api_key="cra_...")

# Option 2: Environment variable
# export CRAWLERVERSE_API_KEY=cra_...
client = CrawlerClient()
```

## Async Support

```python
from crawlerverse import AsyncCrawlerClient, async_run_game

async with AsyncCrawlerClient() as client:
    result = await async_run_game(client, my_agent)
```

## API Reference

### Client Methods

```python
client.games.create(model_id="gpt-4o")      # Start a new game
client.games.list(status="completed")         # List your games
client.games.get(game_id)                     # Get game state
client.games.action(game_id, Move(...))       # Submit action
client.games.abandon(game_id)                 # Abandon game
client.health()                               # Health check
```

### Actions

```python
Move(direction=Direction.NORTH)
Attack(direction=Direction.EAST)
Wait()
Pickup()
Drop(item_type="health-potion")
Use(item_type="health-potion")
Equip(item_type="iron-sword")
EnterPortal()
RangedAttack(direction=Direction.SOUTH, distance=5)
```

### Observation Helpers

```python
obs.tile_at(x, y)          # Look up tile by coordinates
obs.monsters()              # All visible monsters
obs.nearest_monster()       # Closest monster
obs.items_at_feet()         # Items at player's position
obs.has_item("sword")       # Check inventory
obs.can_move(Direction.NORTH)  # Check if direction is walkable
```

## Logging

The SDK uses Python's standard `logging` module under the `crawlerverse` logger. To see game progress and debug info:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

For more detail (e.g., retry attempts, action payloads):

```python
logging.getLogger("crawlerverse").setLevel(logging.DEBUG)
```

## Examples

All examples default to a local API at `http://localhost:3000/api/agent`. Set `CRAWLERVERSE_BASE_URL` to point at production.

### OpenAI

See [`examples/openai_agent.py`](examples/openai_agent.py):

```bash
pip install openai
export CRAWLERVERSE_API_KEY=cra_...
export OPENAI_API_KEY=sk-...
python examples/openai_agent.py
```

Works with any OpenAI-compatible provider (Ollama, LMStudio, Azure, etc.) via `OPENAI_BASE_URL`.

### Anthropic (Claude)

See [`examples/anthropic_agent.py`](examples/anthropic_agent.py):

```bash
pip install anthropic
export CRAWLERVERSE_API_KEY=cra_...
export ANTHROPIC_API_KEY=sk-ant-...
python examples/anthropic_agent.py
```

Uses Claude Haiku 4.5 by default. Override with `ANTHROPIC_MODEL=claude-sonnet-4-5`.

### Local LLM (Ollama / LMStudio)

See [`examples/local_llm_agent.py`](examples/local_llm_agent.py) for a script with configurable turn limits and error recovery:

```bash
pip install openai
export CRAWLERVERSE_API_KEY=cra_...
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_MODEL=llama3
python examples/local_llm_agent.py
```

Supports `MAX_TURNS` (default 25) and `MODEL_ID` env vars.

## License

MIT
