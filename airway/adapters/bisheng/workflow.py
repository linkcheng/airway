from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx

from airway.config import AirwayError

if TYPE_CHECKING:
    from airway.config import AppConfig


class BishengWorkflowAdapter:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._base_url = config.bisheng.base_url.rstrip("/")
        self._timeout = 30.0

    async def invoke(
        self, workflow_id: str, query: str, token: str, session_id: str | None = None
    ) -> tuple[str, str]:
        payload: dict = {
            "workflow_id": workflow_id,
            "query": query,
            "stream": True,
        }
        if session_id:
            payload["session_id"] = session_id

        answer_parts: list[str] = []
        result_session_id = session_id or ""

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/v2/workflow/invoke",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise AirwayError(
                        "WORKFLOW_ERROR",
                        f"Workflow 调用失败: HTTP {resp.status_code}",
                    )

                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if not data_str:
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if "session_id" in event and not result_session_id:
                        result_session_id = event["session_id"]

                    inner = event.get("data", {})
                    if isinstance(inner, dict):
                        event_type = inner.get("event")
                        if event_type in ("end", "over"):
                            break
                        if event_type == "stream" and inner.get("data"):
                            answer_parts.append(inner["data"])

        if not answer_parts:
            raise AirwayError("WORKFLOW_ERROR", "RAG 服务未返回有效响应")

        return "".join(answer_parts), result_session_id
