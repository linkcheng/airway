import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.rag_tools import knowledge_list, knowledge_search, knowledge_files
from airway.settings import Settings, get_settings

logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

mcp: FastMCP | None = None
_client: BishengAPIClient | None = None


def create_app() -> FastAPI:
    global mcp, _client

    settings = get_settings()
    _client = BishengAPIClient(settings)

    mcp = FastMCP("airway", instructions="Bisheng RAG tools for Clawith agents")

    @mcp.tool()
    async def knowledge_list_tool(keyword: str | None = None, user_id: str | None = None) -> str:
        """List available knowledge bases from Bisheng."""
        assert _client is not None
        logger.info("tool=knowledge_list user_id=%s keyword=%s", user_id, keyword)
        try:
            result = await knowledge_list(_client, keyword=keyword)
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_search_tool(knowledge_id: str, query: str, user_id: str | None = None) -> str:
        """Search for relevant content in a specific knowledge base."""
        assert _client is not None
        logger.info("tool=knowledge_search user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await knowledge_search(_client, knowledge_id=knowledge_id, query=query)
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_files_tool(knowledge_id: str, user_id: str | None = None) -> str:
        """List files in a specific knowledge base."""
        assert _client is not None
        logger.info("tool=knowledge_files user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await knowledge_files(_client, knowledge_id=knowledge_id)
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        yield
        if _client:
            await _client.close()

    app = FastAPI(title="Airway", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> JSONResponse:
        assert _client is not None
        try:
            await _client.get("/api/v1/chat/chat/online")
            return JSONResponse({"status": "ok"})
        except Exception:
            return JSONResponse(
                {"status": "degraded", "detail": "bisheng api unreachable"},
                status_code=503,
            )

    app.mount("/sse", mcp.sse_app())

    return app
