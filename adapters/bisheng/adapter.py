from .client import BishengV2Client
from .auth import BishengV1Client


class BishengAdapter:
    def __init__(self, v2_api_url: str, v1_api_url: str,
                 redis_url: str, admin_user: str, admin_pass: str,
                 knowledge_bases: list[dict]):
        self.v2 = BishengV2Client(v2_api_url, redis_url)
        self.v1 = BishengV1Client(v1_api_url, admin_user, admin_pass)
        self.kb_map = {kb["name"]: kb for kb in knowledge_bases}

    async def query(self, query: str, knowledge_base: str | None = None,
                    top_k: int = 5) -> str:
        name = knowledge_base or next(iter(self.kb_map))
        if name not in self.kb_map:
            raise ValueError(f"Unknown knowledge base: {name}")
        kb = self.kb_map[name]
        return await self.v2.chat_completions(
            model=kb["assistant_id"],
            messages=[{"role": "user", "content": query}],
        )

    async def start_workflow(self, workflow_id: str, inputs: dict | None = None) -> str:
        return await self.v2.invoke_workflow(
            workflow_id=workflow_id,
            user_input=inputs or {},
        )

    _STATUS_MAP = {
        "RUNNING": "working",
        "INPUT": "input_required",
        "SUCCESS": "completed",
        "FAILED": "failed",
        "NOT_FOUND": "not_found",
    }

    async def get_workflow_status(self, session_id: str) -> dict:
        raw = await self.v2.get_workflow_status(session_id)
        status = raw.get("status", "NOT_FOUND")
        mapped = self._STATUS_MAP.get(status, "unknown")
        result = {"status": mapped, "session_id": session_id}
        if status == "INPUT":
            for key in ("input_schema", "message_id", "node_id"):
                if key in raw:
                    result[key] = raw[key]
        elif status == "SUCCESS":
            if "result" in raw:
                result["result"] = raw["result"]
        elif status == "FAILED":
            if "error" in raw:
                result["error"] = raw["error"]
        return result

    async def continue_workflow(self, task_id: str, inputs: dict,
                                message_id: str) -> None:
        raw = await self.v2.get_workflow_status(task_id)
        node_id = raw.get("node_id")
        if not node_id:
            raise ValueError("Cannot continue: workflow status missing node_id")
        nested_input = {node_id: inputs}
        await self.v2.invoke_workflow(
            session_id=task_id,
            input=nested_input,
            message_id=int(message_id),
        )
