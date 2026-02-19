# Python SDK (crawlerverse)

## Overview

Python SDK for the Crawler Agent API. Published to PyPI as `crawlerverse`.

## Commands

```bash
cd python

uv sync --group dev          # Install deps (including ruff, pytest, etc.)
uv run ruff check src/ tests/  # Lint
uv run pytest -v --tb=short --cov=crawlerverse --cov-report=term-missing  # Test with coverage
uv build                     # Build package
```

## Project Structure

```
python/
├── src/crawlerverse/        # Package source
│   ├── __init__.py          # Public API exports
│   ├── _base_client.py      # Shared client logic (auth, headers, error mapping)
│   ├── client.py            # Sync CrawlerClient
│   ├── async_client.py      # Async AsyncCrawlerClient
│   ├── runner.py            # run_game() / async_run_game() game loop
│   ├── models.py            # Pydantic models (Observation, Outcome, etc.)
│   ├── actions.py           # Action models (Move, Attack, Wait, etc.)
│   ├── types.py             # Enums (Direction, GameStatus, TileType)
│   └── exceptions.py        # Exception hierarchy
├── tests/                   # pytest tests (128 tests, ~89% coverage)
├── examples/                # Example agent scripts
│   ├── openai_agent.py      # OpenAI (or compatible) agent
│   ├── anthropic_agent.py   # Anthropic Claude agent
│   └── local_llm_agent.py   # Local LLM with turn limit
└── pyproject.toml           # Package config
```

## Key Patterns

- **CamelCase aliasing**: All Pydantic models use `alias_generator=to_camel, populate_by_name=True` for camelCase API ↔ snake_case Python.
- **Action serialization**: `_ActionBase` defaults `exclude_none=True` so optional fields aren't sent.
- **Discriminated unions**: `Outcome` uses `Field(discriminator="status")` for `InProgressOutcome | CompletedOutcome | AbandonedOutcome`.
- **OpenAPI drift tests**: `tests/test_openapi_sync.py` fetches the spec from `https://crawlerver.se/agent-api-openapi.yaml` and validates all models. Override with `OPENAPI_SPEC_URL` or `OPENAPI_SPEC_PATH` env vars.

## Releasing to PyPI

The CI workflow at `.github/workflows/python-ci.yml` includes a publish job.

1. Bump `version` in `pyproject.toml`
2. Commit: `git commit -m "chore: bump crawlerverse to 0.2.0"`
3. Tag: `git tag python-sdk-v0.2.0`
4. Push: `git push && git push --tags`

The publish job triggers on `python-sdk-v*` tags, runs lint/test/build, then publishes with `uv publish`. The `PYPI_API_TOKEN` secret is configured in the GitHub `pypi` environment.

## CI

Workflow: `.github/workflows/python-ci.yml`

- **Lint**: ruff
- **Test**: Python 3.10-3.13 matrix with pytest-cov
- **Build**: uv build + verify imports + upload artifact
- **Publish**: On `python-sdk-v*` tags only, to PyPI
