from fastmcp import FastMCP

from adapters.bisheng.adapter import BishengAdapter

mcp = FastMCP("airway")
adapter: BishengAdapter | None = None


@mcp.tool
async def rag_query(query: str, knowledge_base: str | None = None, top_k: int = 5) -> str:
    """RAG 问答"""
    return await adapter.query(query, knowledge_base, top_k)


@mcp.tool
async def rag_upload(file_path: str, knowledge_base: str) -> str:
    """上传文档到知识库"""
    raise NotImplementedError("Upload not yet implemented")


@mcp.tool
async def rag_kb_list() -> list[dict]:
    """列出可用知识库"""
    return [
        {"name": kb["name"], "assistant_id": kb["assistant_id"], "kb_id": kb["kb_id"]}
        for kb in adapter.kb_map.values()
    ]


@mcp.tool
async def workflow_start(workflow_id: str, inputs: dict | None = None) -> dict:
    """启动 Workflow"""
    session_id = await adapter.start_workflow(workflow_id, inputs)
    return {"task_id": session_id, "status": "working"}


@mcp.tool
async def workflow_status(task_id: str) -> dict:
    """查询 Workflow 状态"""
    return await adapter.get_workflow_status(task_id)


@mcp.tool
async def workflow_continue(task_id: str, inputs: dict, message_id: str) -> dict:
    """提交人工输入"""
    await adapter.continue_workflow(task_id, inputs, message_id)
    return {"task_id": task_id, "status": "working"}


if __name__ == "__main__":
    from config import load_config

    cfg = load_config("config.yaml")
    bisheng = cfg.bisheng
    adapter = BishengAdapter(
        v2_api_url=bisheng.v2_api_url,
        v1_api_url=bisheng.v1_api_url,
        redis_url=bisheng.redis_url,
        admin_user=bisheng.admin_username,
        admin_pass=bisheng.admin_password,
        knowledge_bases=[kb.model_dump() for kb in bisheng.knowledge_bases],
    )
    mcp.run(transport="streamable-http", host=cfg.server.host, port=cfg.server.port)
