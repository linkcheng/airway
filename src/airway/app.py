import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.rag_tools import (
    knowledge_list,
    knowledge_search,
    knowledge_files,
    knowledge_create,
    knowledge_delete,
    knowledge_upload,
    knowledge_file_delete,
    knowledge_process,
    qa_list,
    qa_add,
    qa_delete,
    workflow_list,
    workflow_run,
    workflow_run_once,
)
from airway.settings import Settings, get_settings

logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

mcp: FastMCP | None = None
_client: BishengAPIClient | None = None
_settings: Settings | None = None


def _resolve_token(user_id: str | None) -> str | None:
    if user_id and _settings and _settings.user_tokens:
        return _settings.user_tokens.get(user_id)
    return None


def create_app() -> FastAPI:
    global mcp, _client, _settings

    settings = get_settings()
    _settings = settings
    _client = BishengAPIClient(settings)

    mcp = FastMCP("airway", instructions="Bisheng RAG tools for Clawith agents")

    @mcp.tool()
    async def knowledge_list_tool(keyword: str | None = None, user_id: str | None = None) -> str:
        """List available knowledge bases from Bisheng."""
        assert _client is not None
        logger.info("tool=knowledge_list user_id=%s keyword=%s", user_id, keyword)
        try:
            result = await knowledge_list(_client, keyword=keyword, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_search_tool(knowledge_id: str, query: str, user_id: str | None = None) -> str:
        """Search for relevant content in a specific knowledge base."""
        assert _client is not None
        logger.info("tool=knowledge_search user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await knowledge_search(_client, knowledge_id=knowledge_id, query=query, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_files_tool(knowledge_id: str, user_id: str | None = None) -> str:
        """List files in a specific knowledge base."""
        assert _client is not None
        logger.info("tool=knowledge_files user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await knowledge_files(_client, knowledge_id=knowledge_id, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_create_tool(name: str, description: str = "", user_id: str | None = None) -> str:
        """Create a new knowledge base in Bisheng."""
        assert _client is not None
        logger.info("tool=knowledge_create user_id=%s name=%s", user_id, name)
        try:
            result = await knowledge_create(_client, name=name, description=description, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_delete_tool(knowledge_id: str, user_id: str | None = None) -> str:
        """Delete a knowledge base from Bisheng."""
        assert _client is not None
        logger.info("tool=knowledge_delete user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await knowledge_delete(_client, knowledge_id=knowledge_id, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_upload_tool(
        knowledge_id: str, file_name: str, file_content_base64: str, user_id: str | None = None
    ) -> str:
        """Upload a file to a knowledge base. File content must be base64 encoded."""
        assert _client is not None
        logger.info("tool=knowledge_upload user_id=%s knowledge_id=%s file=%s", user_id, knowledge_id, file_name)
        try:
            result = await knowledge_upload(
                _client, knowledge_id=knowledge_id, file_name=file_name,
                file_content_base64=file_content_base64, token=_resolve_token(user_id),
            )
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_file_delete_tool(file_id: str, user_id: str | None = None) -> str:
        """Delete a file from a knowledge base."""
        assert _client is not None
        logger.info("tool=knowledge_file_delete user_id=%s file_id=%s", user_id, file_id)
        try:
            result = await knowledge_file_delete(_client, file_id=file_id, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def knowledge_process_tool(
        knowledge_id: str, file_ids: list[str], user_id: str | None = None
    ) -> str:
        """Trigger document processing (chunking and vectorization) for uploaded files."""
        assert _client is not None
        logger.info("tool=knowledge_process user_id=%s knowledge_id=%s file_ids=%s", user_id, knowledge_id, file_ids)
        try:
            result = await knowledge_process(_client, knowledge_id=knowledge_id, file_ids=file_ids, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def qa_list_tool(knowledge_id: str, user_id: str | None = None) -> str:
        """List QA entries in a QA-type knowledge base."""
        assert _client is not None
        logger.info("tool=qa_list user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await qa_list(_client, knowledge_id=knowledge_id, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def qa_add_tool(knowledge_id: str, question: str, answer: str, user_id: str | None = None) -> str:
        """Add a QA entry to a QA-type knowledge base."""
        assert _client is not None
        logger.info("tool=qa_add user_id=%s knowledge_id=%s", user_id, knowledge_id)
        try:
            result = await qa_add(_client, knowledge_id=knowledge_id, question=question, answer=answer, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def qa_delete_tool(qa_id: str, user_id: str | None = None) -> str:
        """Delete a QA entry from a QA-type knowledge base."""
        assert _client is not None
        logger.info("tool=qa_delete user_id=%s qa_id=%s", user_id, qa_id)
        try:
            result = await qa_delete(_client, qa_id=qa_id, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def workflow_list_tool(keyword: str | None = None, page_size: int = 10, page_num: int = 1, user_id: str | None = None) -> str:
        """List available workflows from Bisheng."""
        assert _client is not None
        logger.info("tool=workflow_list user_id=%s keyword=%s", user_id, keyword)
        try:
            result = await workflow_list(_client, keyword=keyword, page_size=page_size, page_num=page_num, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def workflow_run_tool(workflow_id: str, input: str | None = None, session_id: str | None = None, user_id: str | None = None) -> str:
        """Execute a workflow and return results. Input should be a JSON string if provided."""
        assert _client is not None
        logger.info("tool=workflow_run user_id=%s workflow_id=%s", user_id, workflow_id)
        try:
            input_dict = json.loads(input) if input else None
            result = await workflow_run(_client, workflow_id=workflow_id, input=input_dict, session_id=session_id, token=_resolve_token(user_id))
            return json.dumps(result, ensure_ascii=False)
        except BishengAPIError as e:
            return json.dumps({"error": e.detail, "status": e.status_code})

    @mcp.tool()
    async def workflow_run_once_tool(workflow_id: str, node_input: str | None = None, node_data: str | None = None, user_id: str | None = None) -> str:
        """Execute a single node in a workflow. Input should be a JSON string if provided."""
        assert _client is not None
        logger.info("tool=workflow_run_once user_id=%s workflow_id=%s", user_id, workflow_id)
        try:
            node_input_dict = json.loads(node_input) if node_input else None
            node_data_dict = json.loads(node_data) if node_data else None
            result = await workflow_run_once(_client, workflow_id=workflow_id, node_input=node_input_dict, node_data=node_data_dict, token=_resolve_token(user_id))
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
