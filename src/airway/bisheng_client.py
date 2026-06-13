import logging
from typing import Any

import httpx

from airway.settings import Settings

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

logger = logging.getLogger(__name__)


class BishengAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Bisheng API error {status_code}: {detail}")


class BishengAPIClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.bisheng_api_url.rstrip("/")
        self._timeout = settings.api_timeout
        self._username = settings.bisheng_username
        self._password = settings.bisheng_password
        self._token = settings.bisheng_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def _refresh_token(self) -> None:
        if not self._username or not self._password:
            raise BishengAPIError(401, "No credentials for token refresh")
        client = await self._get_client()
        resp = await client.post(
            "/api/v1/user/login",
            json={"user_name": self._username, "password": self._password},
        )
        if resp.status_code != 200:
            raise BishengAPIError(resp.status_code, "Token refresh failed")
        data = resp.json()
        self._token = data.get("access_token", "")
        logger.info("Bisheng token refreshed")

    async def request(self, method: str, path: str, *, token_override: str | None = None, **kwargs: Any) -> Any:
        client = await self._get_client()
        token = token_override or self._token
        headers = kwargs.pop("headers", {})
        if token:
            headers["Cookie"] = f"access_token={token}"
        resp = await client.request(
            method, path, headers=headers, **kwargs
        )

        if resp.status_code == 401 and not token_override:
            logger.warning("Token expired, refreshing...")
            await self._refresh_token()
            headers["Cookie"] = f"access_token={self._token}" if self._token else ""
            resp = await client.request(
                method, path, headers=headers, **kwargs
            )

        if resp.status_code >= 400:
            raise BishengAPIError(resp.status_code, resp.text)

        return resp.json()

    async def get(self, path: str, *, token_override: str | None = None, **kwargs: Any) -> Any:
        return await self.request("GET", path, token_override=token_override, **kwargs)

    async def post(self, path: str, *, token_override: str | None = None, **kwargs: Any) -> Any:
        return await self.request("POST", path, token_override=token_override, **kwargs)

    async def delete(self, path: str, *, token_override: str | None = None, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, token_override=token_override, **kwargs)

    async def upload(self, path: str, file_name: str, file_data: bytes, *, token_override: str | None = None, **kwargs: Any) -> Any:
        if len(file_data) > MAX_UPLOAD_SIZE:
            raise BishengAPIError(400, f"File size exceeds {MAX_UPLOAD_SIZE // (1024*1024)}MB limit")
        client = await self._get_client()
        files = {"file": (file_name, file_data)}
        token = token_override or self._token
        headers = {"Cookie": f"access_token={token}"} if token else {}
        resp = await client.request("POST", path, files=files, headers=headers, **kwargs)

        if resp.status_code == 401 and not token_override:
            logger.warning("Token expired during upload, refreshing...")
            await self._refresh_token()
            headers = {"Cookie": f"access_token={self._token}"} if self._token else {}
            resp = await client.request("POST", path, files=files, headers=headers, **kwargs)

        if resp.status_code >= 400:
            raise BishengAPIError(resp.status_code, resp.text)

        return resp.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
