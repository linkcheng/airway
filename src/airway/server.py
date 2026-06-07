# src/airway/server.py
import argparse
import logging

import redis.asyncio as aioredis
from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

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


async def init_deps() -> AirwayTools:
    global _tools, _engine

    settings = get_settings()

    _engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    redis = aioredis.from_url(settings.redis_url)
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
async def knowledge_list(user_id: str, page: int = 1, size: int = 20) -> str:
    """列出用户可访问的知识库。user_id 是 Clawith 用户 ID。"""
    return await _get_tools().knowledge_list(user_id, page=page, size=size)


@mcp.tool()
async def knowledge_detail(user_id: str, knowledge_id: str) -> str:
    """获取知识库详情。knowledge_id 是 Bisheng 知识库 ID。"""
    return await _get_tools().knowledge_detail(user_id, knowledge_id)


@mcp.tool()
async def knowledge_search(
    user_id: str, query: str, knowledge_id: str, top_k: int = 5,
) -> str:
    """在知识库中进行 RAG 检索。query 是检索问题，knowledge_id 是知识库 ID。"""
    return await _get_tools().knowledge_search(
        user_id, query=query, knowledge_id=knowledge_id, top_k=top_k,
    )


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
