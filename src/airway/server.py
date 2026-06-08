import argparse
import json
import logging

import redis.asyncio as aioredis
from fastmcp import Context, FastMCP
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from airway.auth.jwt import verify_clawith_jwt
from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient
from airway.config import get_settings
from airway.mcp.tools import AirwayTools

logger = logging.getLogger("airway")

mcp = FastMCP("Airway RAG Server")

_tools: AirwayTools | None = None
_engine = None


def _get_tools() -> AirwayTools:
    if _tools is None:
        raise RuntimeError("Server not initialized. Call init_deps() first.")
    return _tools


def _resolve_user_id(ctx: Context) -> str:
    meta = {}
    rc = getattr(ctx, "request_context", None)
    if rc:
        params = getattr(rc, "params", None)
        if params:
            meta = getattr(params, "meta", None) or {}

    if "authorization" in meta:
        token = meta["authorization"].removeprefix("Bearer ")
        settings = get_settings()
        return verify_clawith_jwt(
            token, settings.clawith_jwt_secret, settings.clawith_jwt_algorithm,
        )
    if "user_id" in meta:
        return meta["user_id"]
    raise ValueError("No authentication provided")


async def init_deps() -> AirwayTools:
    global _tools, _engine

    settings = get_settings()

    _engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    try:
        redis = aioredis.from_url(settings.redis_url)
        await redis.ping()
    except Exception:
        logger.warning("Redis unavailable, running without cache")
        redis = None

    client = BishengClient(base_url=settings.bisheng_base_url)

    proxy = AuthProxy(
        client=client,
        redis=redis,
        session_factory=session_factory,
        key_prefix=settings.redis_key_prefix,
    )
    _tools = AirwayTools(proxy=proxy, client=client)
    return _tools


@mcp.tool()
async def knowledge_list(ctx: Context, page: int = 1, size: int = 20) -> str:
    """列出用户可访问的知识库。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().knowledge_list(user_id, page=page, size=size)


@mcp.tool()
async def knowledge_detail(ctx: Context, knowledge_id: str) -> str:
    """获取知识库详情。knowledge_id 是 Bisheng 知识库 ID。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().knowledge_detail(user_id, knowledge_id)


@mcp.tool()
async def knowledge_search(
    ctx: Context, query: str, knowledge_id: str, top_k: int = 5,
) -> str:
    """在知识库中进行 RAG 检索。query 是检索问题，knowledge_id 是知识库 ID。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().knowledge_search(
        user_id, query=query, knowledge_id=knowledge_id, top_k=top_k,
    )


@mcp.tool()
async def workflow_list(ctx: Context, page: int = 1, size: int = 10, name: str | None = None) -> str:
    """列出可用的 Workflow。name 参数可模糊搜索。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().workflow_list(user_id, page=page, size=size, name=name)


@mcp.tool()
async def workflow_run(ctx: Context, workflow_id: str, input: str | None = None, overrides: str | None = None) -> str:
    """执行 Workflow。workflow_id 是 Bisheng Workflow ID，input 是用户输入，overrides 是节点参数覆盖（JSON 字符串）。"""
    user_id = _resolve_user_id(ctx)
    overrides_dict = None
    if overrides:
        try:
            overrides_dict = json.loads(overrides)
        except json.JSONDecodeError:
            return json.dumps({"error": "overrides 不是有效的 JSON"}, ensure_ascii=False)
    return await _get_tools().workflow_run(user_id, workflow_id, input=input, overrides=overrides_dict)


@mcp.tool()
async def workflow_status(ctx: Context, workflow_id: str, session_id: str) -> str:
    """查询 Workflow 执行结果。session_id 来自 workflow_run 的返回。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().workflow_status(user_id, workflow_id=workflow_id, session_id=session_id)


def main():
    parser = argparse.ArgumentParser(description="Airway MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, get_settings().airway_log_level))

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
