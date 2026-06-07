# src/airway/client/bisheng.py
import base64
from base64 import b64encode

import httpx
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key


class BishengClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        transport = httpx.AsyncHTTPTransport(retries=3)
        self._http = httpx.AsyncClient(
            base_url=self.base_url, timeout=30.0, transport=transport,
        )
        self._public_key: str | None = None

    async def close(self):
        await self._http.aclose()

    async def get_public_key(self) -> str:
        resp = await self._http.get("/api/v1/user/public_key")
        resp.raise_for_status()
        data = resp.json()
        self._public_key = data["data"]["public_key"]
        return self._public_key

    def _encrypt_password(self, _password: str, public_key_b64: str) -> str:
        key_bytes = base64.b64decode(public_key_b64)
        public_key = load_der_public_key(key_bytes)
        encrypted = public_key.encrypt(
            _password.encode(),
            padding.PKCS1v15(),
        )
        return b64encode(encrypted).decode()

    async def login(self, username: str, password: str) -> str:
        if not self._public_key:
            await self.get_public_key()

        encrypted_pwd = self._encrypt_password(password, self._public_key)
        resp = await self._http.post(
            "/api/v1/user/login",
            json={
                "user_name": username,
                "password": encrypted_pwd,
            },
        )
        if resp.status_code != 200:
            raise Exception(f"Login failed: {resp.status_code} {resp.text}")

        data = resp.json()
        if data.get("code") != 200:
            raise Exception(f"Login failed: {data.get('message')}")

        return data["data"]["access_token"]

    async def _request(
        self,
        method: str,
        path: str,
        token: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await self._http.request(
            method, path, headers=headers, params=params, json=json_body,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise Exception(f"Bisheng API error: {data.get('message')}")
        return data["data"]

    async def knowledge_list(self, token: str, page: int = 1, size: int = 20) -> list[dict]:
        data = await self._request(
            "GET",
            "/api/v1/knowledge/space/mine",
            token,
            params={"page": page, "page_size": size},
        )
        return data.get("list", [])

    async def knowledge_detail(self, token: str, knowledge_id: str) -> dict:
        return await self._request(
            "GET",
            f"/api/v1/knowledge/space/{knowledge_id}/info",
            token,
        )

    async def knowledge_search(
        self, token: str, query: str, knowledge_id: str, top_k: int = 5,
    ) -> list[dict]:
        return await self._request(
            "POST",
            "/api/v2/knowledge/search",
            token,
            json_body={"query": query, "knowledge_id": knowledge_id, "top_k": top_k},
        )
