import base64
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization


class BishengV1Client:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.access_token: str | None = None
        self._token_obtained_at: datetime | None = None
        self._token_ttl = timedelta(hours=24)
        self._refresh_margin = timedelta(hours=1)

    async def login(self) -> None:
        public_key = await self._fetch_public_key()
        encrypted_password = self._encrypt_password(public_key)
        await self._authenticate(encrypted_password)
        self._token_obtained_at = datetime.now(timezone.utc)

    async def ensure_token(self) -> None:
        if self._needs_refresh():
            await self.login()

    def _needs_refresh(self) -> bool:
        if self.access_token is None or self._token_obtained_at is None:
            return True
        elapsed = datetime.now(timezone.utc) - self._token_obtained_at
        return elapsed >= self._token_ttl - self._refresh_margin

    async def _fetch_public_key(self) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/user/public_key"
            )
            resp.raise_for_status()
            return resp.json()["public_key"]

    def _encrypt_password(self, public_key_pem: str) -> str:
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        encrypted = public_key.encrypt(
            self.password.encode(),
            padding.PKCS1v15(),
        )
        return base64.b64encode(encrypted).decode()

    async def _authenticate(self, encrypted_password: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/user/login",
                json={
                    "user_name": self.username,
                    "password": encrypted_password,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data["access_token"]
