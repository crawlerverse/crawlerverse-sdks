"""Asynchronous Crawler API client."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from crawlerverse._base_client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    build_headers,
    map_error_response,
    resolve_api_key,
)
from crawlerverse.actions import Action
from crawlerverse.models import (
    AbandonGameResponse,
    ActionResponse,
    CreateGameResponse,
    GameStateResponse,
    HealthResponse,
    ListGamesResponse,
)

logger = logging.getLogger("crawlerverse")


class _AsyncGamesResource:
    """Games namespace: client.games.* (async)."""

    def __init__(self, client: AsyncCrawlerClient) -> None:
        self._client = client

    async def create(
        self, *, model_id: str | None = None
    ) -> CreateGameResponse:
        body: dict[str, Any] = {}
        if model_id is not None:
            body["modelId"] = model_id
        data = await self._client._request("POST", "/games", json=body)
        return CreateGameResponse.model_validate(data)

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListGamesResponse:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        data = await self._client._request("GET", "/games", params=params)
        return ListGamesResponse.model_validate(data)

    async def get(self, game_id: str) -> GameStateResponse:
        data = await self._client._request("GET", f"/games/{game_id}")
        return GameStateResponse.model_validate(data)

    async def action(self, game_id: str, action: Action) -> ActionResponse:
        body = action.model_dump(by_alias=True, exclude_none=True)
        data = await self._client._request(
            "POST", f"/games/{game_id}/action", json=body
        )
        return ActionResponse.model_validate(data)

    async def abandon(self, game_id: str) -> AbandonGameResponse:
        data = await self._client._request(
            "POST", f"/games/{game_id}/abandon"
        )
        return AbandonGameResponse.model_validate(data)


class AsyncCrawlerClient:
    """Asynchronous client for the Crawler Agent API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        resolved_key = resolve_api_key(api_key)
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            headers=build_headers(resolved_key), timeout=timeout
        )
        self.games = _AsyncGamesResource(self)

    async def health(self) -> HealthResponse:
        data = await self._request("GET", "/health")
        return HealthResponse.model_validate(data)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = await self._http.request(
            method, url, json=json, params=params
        )
        if response.status_code >= 400:
            try:
                body = response.json()
            except (ValueError, UnicodeDecodeError):
                logger.warning(
                    "Failed to parse error response as JSON (status=%d)",
                    response.status_code,
                )
                body = {"error": response.text}
            map_error_response(response.status_code, body, response.headers)
        return response.json()

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncCrawlerClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
