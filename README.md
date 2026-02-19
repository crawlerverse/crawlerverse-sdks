# Crawlerverse SDKs

Official SDKs for the [Crawlerverse](https://crawlerver.se) Agent API. Build AI agents that play the Crawler roguelike game.

## Available SDKs

| SDK | Language | Package | Status |
|-----|----------|---------|--------|
| [Python](./python/) | Python 3.10+ | [`crawlerverse`](https://pypi.org/project/crawlerverse/) | Stable |

## Quick Start

### Python

```bash
pip install crawlerverse
```

```python
from crawlerverse import CrawlerClient, run_game, Move, Direction

with CrawlerClient(api_key="your-key") as client:
    result = run_game(client, my_agent)
```

See the [Python SDK README](./python/README.md) for full documentation and examples.

## Contributing

Each SDK lives in its own directory with independent tooling and CI. See the README in each SDK directory for development setup.

## License

MIT - see [LICENSE](./LICENSE) for details.
