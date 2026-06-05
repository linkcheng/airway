import json

import httpx
import redis.asyncio as aioredis


class AirwayError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class BishengV2Client:
    def __init__(self, base_url: str, redis_url: str):
        self._base_url = base_url.rstrip("/")
        self._redis_url = redis_url
        self._http = httpx.AsyncClient(base_url=self._base_url)
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def chat_completions(self, model: str, messages: list[dict]) -> str:
        resp = await self._http.post(
            "/api/v2/assistant/chat/completions",
            json={"model": model, "messages": messages, "stream": False},
        )
        if resp.status_code != 200:
            raise AirwayError("BISHENG_API_ERROR", f"API error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def invoke_workflow(
        self,
        workflow_id: str,
        user_input: dict | None = None,
        session_id: str | None = None,
        input: dict | None = None,
        message_id: int | None = None,
    ) -> str:
        body: dict = {"stream": True}
        if session_id:
            body["workflow_id"] = ""
            body["session_id"] = session_id
            body["input"] = input or {}
            body["message_id"] = message_id
        else:
            body["workflow_id"] = workflow_id
            body["user_input"] = user_input or {}

        resp = await self._http.post("/api/v2/workflow/invoke", json=body)
        text = resp.text
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if "session_id" in payload:
                    return payload["session_id"]
                break
        raise AirwayError("NO_SESSION_ID", "First SSE event has no session_id")

    async def get_workflow_status(self, session_id: str) -> dict:
        redis = await self._get_redis()
        raw = await redis.get(f"workflow:{session_id}:status")
        if raw is None:
            return {"status": "NOT_FOUND"}
        status_data = json.loads(raw)
        if status_data.get("status") == "INPUT":
            input_raw = await redis.get(f"workflow:{session_id}:input")
            if input_raw:
                input_data = json.loads(input_raw)
                status_data.update(input_data)
        return status_data
