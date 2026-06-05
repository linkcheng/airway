# src/airway/mcp/tools.py
import json
from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient


class AirwayTools:
    def __init__(self, proxy: AuthProxy, client: BishengClient):
        self._proxy = proxy
        self._client = client

    async def knowledge_list(self, user_id: str, page: int = 1, size: int = 20) -> str:
        token = await self._proxy.get_session(user_id)
        result = await self._client.knowledge_list(token, page=page, size=size)
        return json.dumps(result, ensure_ascii=False)

    async def knowledge_detail(self, user_id: str, knowledge_id: str) -> str:
        token = await self._proxy.get_session(user_id)
        result = await self._client.knowledge_detail(token, knowledge_id)
        return json.dumps(result, ensure_ascii=False)

    async def knowledge_search(
        self, user_id: str, query: str, knowledge_id: str, top_k: int = 5,
    ) -> str:
        token = await self._proxy.get_session(user_id)
        result = await self._client.knowledge_search(
            token, query=query, knowledge_id=knowledge_id, top_k=top_k,
        )
        return json.dumps(result, ensure_ascii=False)
