import json

import httpx

from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient


class AirwayTools:
    def __init__(self, proxy: AuthProxy, client: BishengClient):
        self._proxy = proxy
        self._client = client

    async def _with_retry(self, user_id: str, fn):
        token = await self._proxy.get_session(user_id)
        try:
            return await fn(token)
        except Exception as e:
            if self._is_auth_error(e):
                token = await self._proxy.refresh_session(user_id)
                return await fn(token)
            raise

    @staticmethod
    def _is_auth_error(e: Exception) -> bool:
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code == 401
        return False

    async def knowledge_list(self, user_id: str, page: int = 1, size: int = 20) -> str:
        async def _do(token: str):
            result = await self._client.knowledge_list(token, page=page, size=size)
            return json.dumps(result, ensure_ascii=False)
        return await self._with_retry(user_id, _do)

    async def knowledge_detail(self, user_id: str, knowledge_id: str) -> str:
        async def _do(token: str):
            result = await self._client.knowledge_detail(token, knowledge_id)
            return json.dumps(result, ensure_ascii=False)
        return await self._with_retry(user_id, _do)

    async def knowledge_search(
        self, user_id: str, query: str, knowledge_id: str, top_k: int = 5,
    ) -> str:
        async def _do(token: str):
            result = await self._client.knowledge_search(
                token, query=query, knowledge_id=knowledge_id, top_k=top_k,
            )
            return json.dumps(result, ensure_ascii=False)
        return await self._with_retry(user_id, _do)
