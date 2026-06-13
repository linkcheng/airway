# ruff: noqa: F821
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from airway.config import AirwayError
from airway.errors import to_tool_error

_session_factory = None

if TYPE_CHECKING:
    from airway.adapters.protocols import BishengAuth, BishengClient
    from airway.config import AppConfig

mcp = FastMCP("airway", mask_error_details=True)

_config: AppConfig = None  # type: ignore[assignment]  # noqa: F821
_client: BishengClient = None  # type: ignore[assignment]  # noqa: F821
_auth: BishengAuth = None  # type: ignore[assignment]  # noqa: F821
_workflow = None  # type: ignore[assignment]


def _validate_query(query: str) -> None:
    if not query or not query.strip():
        raise AirwayError("INVALID_INPUT", "查询内容不能为空")


def _validate_top_k(top_k: int) -> None:
    if top_k < 1 or top_k > 20:
        raise AirwayError("INVALID_INPUT", f"top_k 必须在 1-20 之间，当前值: {top_k}")


async def _ensure_user_mapping(clawith_user_id: str) -> tuple[int, str]:
    from sqlalchemy import select

    from airway.models.user_mapping import MappingStatus, UserMapping

    async with _session_factory() as session:
        result = await session.execute(
            select(UserMapping).where(UserMapping.clawith_user_id == clawith_user_id)
        )
        mapping = result.scalar_one_or_none()
        if mapping and mapping.status == MappingStatus.ACTIVE:
            return mapping.bisheng_user_id, mapping.bisheng_user_name

        user_name = f"clawith_{clawith_user_id[:20]}"
        password = hashlib.md5(f"airway_{clawith_user_id}".encode()).hexdigest()

        try:
            bisheng_user_id = await _auth.register_user(user_name, password)
        except AirwayError as e:
            if e.code != "USER_CONFLICT":
                raise AirwayError("REGISTER_ERROR", "用户注册服务暂时不可用，请稍后重试")
            bisheng_user_id, _ = await _auth.login_user(user_name, password)

        mapping = UserMapping(
            clawith_user_id=clawith_user_id,
            bisheng_user_id=bisheng_user_id,
            bisheng_user_name=user_name,
            password_hash=password,
            status=MappingStatus.ACTIVE,
        )
        session.add(mapping)
        await session.commit()
        return bisheng_user_id, user_name


def _resolve_kb(name: str) -> int:
    return _config.kb_name_to_id(name)


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "未找到相关内容。"
    lines = [f"找到 {len(chunks)} 个相关片段：\n"]
    for i, chunk in enumerate(chunks, 1):
        score = chunk.get("score", 0)
        content = chunk.get("content", "")
        lines.append(f"【片段 {i}】(相关度: {score:.2f})")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


@mcp.tool
async def rag_query(query: str, knowledge_base: str, top_k: int = 5) -> str:
    """RAG 问答：在指定知识库中检索相关文档片段"""
    try:
        _validate_query(query)
        _validate_top_k(top_k)
        kb_id = _resolve_kb(knowledge_base)
        chunks = await _client.search_chunks(knowledge_id=kb_id, keyword=query, limit=top_k)
        return _format_chunks(chunks)
    except AirwayError as e:
        raise to_tool_error(e)


@mcp.tool
async def knowledge_list() -> str:
    """列出所有可用的知识库"""
    try:
        kbs = await _client.list_knowledge()
        if not kbs:
            return "当前没有可用的知识库。"
        configured_ids = {kb.bisheng_knowledge_id for kb in _config.knowledge_bases}
        id_to_name = {kb.bisheng_knowledge_id: kb.name for kb in _config.knowledge_bases}
        lines = [f"可用知识库（共 {len(kbs)} 个）：\n"]
        for kb in kbs:
            kb_id = kb.get("id")
            if kb_id in configured_ids:
                name = id_to_name[kb_id]
                desc = kb.get("description", "")
                lines.append(f"- {name} ({kb.get('name', '')}) - {desc}")
        return "\n".join(lines)
    except AirwayError as e:
        raise to_tool_error(e)


@mcp.tool
async def knowledge_detail(knowledge_base: str) -> str:
    """获取知识库详细信息"""
    try:
        kb_id = _resolve_kb(knowledge_base)
        details = await _client.get_knowledge([kb_id])
        if not details:
            return f'知识库 "{knowledge_base}" 未找到详情。'
        kb = details[0]
        lines = [
            f"知识库: {knowledge_base}",
            f"名称: {kb.get('name', '')}",
            f"描述: {kb.get('description', '')}",
            f"状态: {'已就绪' if kb.get('state') == 2 else '处理中'}",
        ]
        return "\n".join(lines)
    except AirwayError as e:
        raise to_tool_error(e)


@mcp.tool
async def knowledge_search(query: str, knowledge_base: str, top_k: int = 10) -> str:
    """在知识库中按关键词搜索文档片段"""
    try:
        _validate_query(query)
        if top_k < 1 or top_k > 50:
            raise AirwayError("INVALID_INPUT", f"top_k 必须在 1-50 之间，当前值: {top_k}")
        kb_id = _resolve_kb(knowledge_base)
        chunks = await _client.search_chunks(knowledge_id=kb_id, keyword=query, limit=top_k)
        if not chunks:
            return f'搜索 "{query}" 在 {knowledge_base} 中未找到结果。'
        lines = [f'搜索 "{query}" 在 {knowledge_base} 中找到 {len(chunks)} 个结果：\n']
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            lines.append(f"【结果 {i}】")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)
    except AirwayError as e:
        raise to_tool_error(e)


def _resolve_workflow(name: str) -> str:
    return _config.kb_name_to_workflow(name)


@mcp.tool
async def rag_chat(query: str, knowledge_base: str, chat_id: str | None = None) -> str:
    """RAG 问答：通过 Workflow 获取 AI 生成的完整答案"""
    try:
        _validate_query(query)
        workflow_id = _resolve_workflow(knowledge_base)
        user_id, user_name = await _ensure_user_mapping("default_agent")
        token = await _auth.get_token()
        answer, session_id = await _workflow.invoke(
            workflow_id=workflow_id, query=query, token=token, session_id=chat_id
        )
        prefix = f"[会话 ID: {session_id}]\n\n" if session_id else ""
        return f"{prefix}{answer}"
    except AirwayError as e:
        raise to_tool_error(e)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")
