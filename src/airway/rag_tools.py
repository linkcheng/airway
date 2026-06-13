import base64
import logging
from typing import Any

from airway.bisheng_client import BishengAPIClient, BishengAPIError

logger = logging.getLogger(__name__)


async def knowledge_list(
    client: BishengAPIClient, keyword: str | None = None, *, token: str | None = None
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if keyword:
        params["name"] = keyword
    data = await client.get("/api/v1/knowledge", params=params, token_override=token)
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
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    data = await client.get(
        "/api/v1/knowledge/chunk",
        params={"knowledge_id": knowledge_id, "query": query},
        token_override=token,
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
    client: BishengAPIClient, knowledge_id: str, *, token: str | None = None
) -> list[dict[str, Any]]:
    data = await client.get(f"/api/v1/knowledge/file_list/{knowledge_id}", token_override=token)
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


async def knowledge_create(
    client: BishengAPIClient, name: str, description: str = "", *, token: str | None = None
) -> dict[str, Any]:
    data = await client.post(
        "/api/v1/knowledge/create",
        json={"name": name, "description": description},
        token_override=token,
    )
    return {
        "id": data.get("id"),
        "name": data.get("name", name),
    }


async def knowledge_delete(
    client: BishengAPIClient, knowledge_id: str, *, token: str | None = None
) -> dict[str, Any]:
    await client.delete(
        "/api/v1/knowledge",
        json={"knowledge_id": knowledge_id},
        token_override=token,
    )
    return {"deleted": True, "knowledge_id": knowledge_id}


async def knowledge_file_delete(
    client: BishengAPIClient, file_id: str, *, token: str | None = None
) -> dict[str, Any]:
    await client.delete(f"/api/v1/knowledge/file/{file_id}", token_override=token)
    return {"deleted": True, "file_id": file_id}


async def knowledge_upload(
    client: BishengAPIClient,
    knowledge_id: str,
    file_name: str,
    file_content_base64: str,
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    try:
        file_data = base64.b64decode(file_content_base64)
    except Exception as e:
        raise BishengAPIError(400, f"Invalid base64 encoding: {e}") from e
    data = await client.upload(
        f"/api/v1/knowledge/upload/{knowledge_id}",
        file_name=file_name,
        file_data=file_data,
        token_override=token,
    )
    items = data if isinstance(data, list) else data.get("data", [])
    return [
        {"id": item.get("id"), "name": item.get("name", file_name)}
        for item in items
    ]


async def knowledge_process(
    client: BishengAPIClient, knowledge_id: str, file_ids: list[str], *, token: str | None = None
) -> dict[str, Any]:
    data = await client.post(
        "/api/v1/knowledge/process",
        json={"knowledge_id": knowledge_id, "file_ids": file_ids},
        token_override=token,
    )
    return data if isinstance(data, dict) else {"status": "processing", "data": data}


async def qa_list(
    client: BishengAPIClient, knowledge_id: str, *, token: str | None = None
) -> list[dict[str, Any]]:
    data = await client.get(f"/api/v1/knowledge/qa/list/{knowledge_id}", token_override=token)
    items = data if isinstance(data, list) else data.get("data", [])
    return [
        {
            "id": item.get("id"),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
        }
        for item in items
    ]


async def qa_add(
    client: BishengAPIClient, knowledge_id: str, question: str, answer: str, *, token: str | None = None
) -> dict[str, Any]:
    data = await client.post(
        "/api/v1/knowledge/qa/add",
        json={"knowledge_id": knowledge_id, "question": question, "answer": answer},
        token_override=token,
    )
    return {
        "id": data.get("id"),
        "question": data.get("question", question),
        "answer": data.get("answer", answer),
    }


async def qa_delete(client: BishengAPIClient, qa_id: str, *, token: str | None = None) -> dict[str, Any]:
    await client.delete(
        "/api/v1/knowledge/qa/delete",
        json={"id": qa_id},
        token_override=token,
    )
    return {"deleted": True, "qa_id": qa_id}


async def workflow_list(
    client: BishengAPIClient,
    keyword: str | None = None,
    page_size: int = 10,
    page_num: int = 1,
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"page_size": page_size, "page_num": page_num}
    if keyword:
        params["name"] = keyword
    data = await client.get("/api/v1/workflow/list", params=params, token_override=token)
    items = data.get("data", []) if isinstance(data, dict) else data
    return [
        {
            "id": item.get("id"),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "status": item.get("status"),
            "flow_type": item.get("flow_type"),
        }
        for item in items
    ]


async def workflow_run(
    client: BishengAPIClient,
    workflow_id: str,
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    *,
    token: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"workflow_id": workflow_id, "stream": False}
    if input:
        body["input"] = input
    if session_id:
        body["session_id"] = session_id
    data = await client.post("/api/v2/workflow/invoke", json=body, token_override=token)
    events = data.get("events", []) if isinstance(data, dict) else []
    outputs = []
    for event in events:
        schema = event.get("output_schema", {})
        if schema:
            outputs.append({
                "node_name": event.get("node_name", ""),
                "message": schema.get("message", ""),
            })
    return {
        "session_id": data.get("session_id", ""),
        "outputs": outputs,
    }


async def workflow_run_once(
    client: BishengAPIClient,
    workflow_id: str,
    node_input: dict[str, Any] | None = None,
    node_data: dict[str, Any] | None = None,
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"workflow_id": workflow_id}
    if node_input:
        body["node_input"] = node_input
    if node_data:
        body["node_data"] = node_data
    data = await client.post("/api/v1/workflow/run_once", json=body, token_override=token)
    results = data.get("data", []) if isinstance(data, dict) else data
    return [
        {"key": item.get("key", ""), "value": item.get("value"), "type": item.get("type", "")}
        for item in results
    ]
