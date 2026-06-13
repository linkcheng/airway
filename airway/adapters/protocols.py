from __future__ import annotations

from typing import Protocol


class BishengAuth(Protocol):
    async def login(self) -> str:
        """Authenticate and return JWT access token."""
        ...

    async def get_token(self) -> str:
        """Get cached token or login if expired."""
        ...

    async def register_user(self, user_name: str, password: str) -> int:
        """Register a new user in Bisheng. Returns user_id."""
        ...

    async def login_user(self, user_name: str, password: str) -> tuple[int, str]:
        """Login as a specific user. Returns (user_id, access_token)."""
        ...


class BishengClient(Protocol):
    async def list_knowledge(self, page_size: int = 100) -> list[dict]:
        """List knowledge bases from Bisheng."""
        ...

    async def get_knowledge(self, knowledge_ids: list[int]) -> list[dict]:
        """Get knowledge base details by IDs."""
        ...

    async def search_chunks(
        self, knowledge_id: int, keyword: str, page: int = 1, limit: int = 10
    ) -> list[dict]:
        """Search document chunks in a knowledge base."""
        ...


class BishengWorkflow(Protocol):
    async def invoke(
        self, workflow_id: str, query: str, token: str, session_id: str | None = None
    ) -> tuple[str, str]:
        """Invoke a Bisheng Workflow via SSE. Returns (answer, session_id)."""
        ...
