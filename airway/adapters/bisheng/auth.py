from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from airway.config import AirwayError

if TYPE_CHECKING:
    from airway.config import AppConfig


class BishengAuthProvider:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._base_url = config.bisheng.base_url.rstrip("/")
        self._token_key = f"{config.redis.key_prefix}bisheng:token"
        self._public_key_key = f"{config.redis.key_prefix}bisheng:rsa_public_key"
        self._public_key_pem: str | None = None

    async def _redis_get(self, key: str) -> str | None:
        import redis.asyncio as aioredis

        r = aioredis.from_url(self._config.redis.url)
        try:
            val = await r.get(key)
            return val.decode() if val else None
        finally:
            await r.aclose()

    async def _redis_set(self, key: str, value: str, ex: int | None = None) -> None:
        import redis.asyncio as aioredis

        r = aioredis.from_url(self._config.redis.url)
        try:
            await r.set(key, value, ex=ex)
        finally:
            await r.aclose()

    async def fetch_public_key(self) -> str:
        if self._public_key_pem:
            return self._public_key_pem
        cached = await self._redis_get(self._public_key_key)
        if cached:
            self._public_key_pem = cached
            return cached
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self._base_url}/api/v1/user/public_key")
            resp.raise_for_status()
            data = resp.json()
            if data.get("status_code") != 200:
                raise AirwayError("AUTH_ERROR", "获取 RSA 公钥失败")
            pem = data["data"]
            self._public_key_pem = pem
            await self._redis_set(self._public_key_key, pem, ex=3600)
            return pem

    async def encrypt_password(self, password: str) -> str:
        pem = await self.fetch_public_key()
        public_key = serialization.load_pem_public_key(pem.encode())
        md5_hash = hashlib.md5(password.encode()).hexdigest().encode()
        encrypted = public_key.encrypt(md5_hash, padding.PKCS1v15())
        return base64.b64encode(encrypted).decode()

    async def login(self) -> str:
        encrypted_pw = await self.encrypt_password(self._config.bisheng.admin_password)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/user/login",
                json={
                    "user_name": self._config.bisheng.admin_user,
                    "password": encrypted_pw,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status_code") != 200:
                raise AirwayError("AUTH_ERROR", f"Bisheng 登录失败: {data.get('status_message')}")
            token = data["data"]["access_token"]
            await self._redis_set(self._token_key, token, ex=86400 - 300)
            return token

    async def get_token(self) -> str:
        cached = await self._redis_get(self._token_key)
        if cached:
            return cached
        return await self.login()

    async def register_user(self, user_name: str, password: str) -> int:
        encrypted_pw = await self.encrypt_password(password)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/user/regist",
                json={"user_name": user_name, "password": encrypted_pw},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status_code") == 200:
                return data["data"]["user_id"]
            if data.get("status_code") == 10605:
                raise AirwayError("USER_CONFLICT", "用户名已存在")
            raise AirwayError("REGISTER_ERROR", f"用户注册失败: {data.get('status_message')}")

    async def login_user(self, user_name: str, password: str) -> tuple[int, str]:
        encrypted_pw = await self.encrypt_password(password)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/user/login",
                json={"user_name": user_name, "password": encrypted_pw},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status_code") != 200:
                raise AirwayError("AUTH_ERROR", f"用户登录失败: {data.get('status_message')}")
            user_id = data["data"]["user_id"]
            token = data["data"]["access_token"]
            return user_id, token
