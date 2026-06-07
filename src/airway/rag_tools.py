import logging
from typing import Any

from airway.bisheng_client import BishengAPIClient, BishengAPIError

logger = logging.getLogger(__name__)


async def knowledge_list(
    client: BishengAPIClient, keyword: str | None = None
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if keyword:
        params["name"] = keyword
    data = await client.get("/api/v1/knowledge", params=params)
    items = data if isinstance(data, list) else data.get("data", [])
    return [
        {
            "id": item.get("id"),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "document_count": len(item.get("file_list", [])),
        }
        for item in items
    ]


async def knowledge_search(
    client: BishengAPIClient,
    knowledge_id: str,
    query: str,
) -> list[dict[str, Any]]:
    data = await client.get(
        "/api/v1/knowledge/chunk",
        params={"knowledge_id": knowledge_id, "query": query},
    )
    chunks = data if isinstance(data, list) else data.get("data", [])
    return [
        {
            "content": chunk.get("content", ""),
            "source": chunk.get("source", ""),
            "score": chunk.get("score", 0),
        }
        for chunk in chunks
    ]


async def knowledge_files(
    client: BishengAPIClient, knowledge_id: str
) -> list[dict[str, Any]]:
    data = await client.get(f"/api/v1/knowledge/file_list/{knowledge_id}")
    items = data if isinstance(data, list) else data.get("data", [])
    return [
        {
            "id": item.get("id"),
            "name": item.get("name", ""),
            "status": item.get("status", ""),
            "chunk_num": item.get("chunk_num", 0),
        }
        for item in items
    ]
