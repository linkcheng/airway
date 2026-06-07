from __future__ import annotations

from typing import Protocol


class BishengAuth(Protocol):
    async def login(self) -> str:
        """Authenticate and return JWT access token."""
        ...

    async def get_token(self) -> str:
        """Get cached token or login if expired."""
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
