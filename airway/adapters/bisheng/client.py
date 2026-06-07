from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from airway.config import AirwayError

if TYPE_CHECKING:
    from airway.adapters.protocols import BishengAuth
    from airway.config import AppConfig


class BishengHttpClient:
    def __init__(self, config: AppConfig, auth: BishengAuth) -> None:
        self._config = config
        self._auth = auth
        self._base_url = config.bisheng.base_url.rstrip("/")

    def _client(self, token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(5.0, connect=3.0),
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict:
        token = await self._auth.get_token()
        async with self._client(token) as client:
            try:
                resp = await getattr(client, method)(url, **kwargs)
            except httpx.TimeoutException:
                raise AirwayError("BISHENG_UNAVAILABLE", "RAG 服务暂时不可用，请稍后重试")
            except httpx.ConnectError:
                raise AirwayError("BISHENG_UNAVAILABLE", "RAG 服务暂时不可用，请稍后重试")
            resp.raise_for_status()
            data = resp.json()
            if data.get("status_code") != 200:
                raise AirwayError("BISHENG_ERROR", data.get("status_message", "Bisheng API 错误"))
            return data.get("data", {})

    async def list_knowledge(self, page_size: int = 100) -> list[dict]:
        data = await self._request("get", "/api/v2/knowledge", params={"page_size": page_size})
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else []

    async def get_knowledge(self, knowledge_ids: list[int]) -> list[dict]:
        params = [("knowledge_id", str(kid)) for kid in knowledge_ids]
        data = await self._request("get", "/api/v1/knowledge/info", params=params)
        return data if isinstance(data, list) else [data] if data else []

    async def search_chunks(
        self, knowledge_id: int, keyword: str, page: int = 1, limit: int = 10
    ) -> list[dict]:
        data = await self._request(
            "get",
            "/api/v1/knowledge/chunk",
            params={"knowledge_id": knowledge_id, "keyword": keyword, "page": page, "limit": limit},
        )
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else []
