# src/airway/auth/proxy.py
import redis.asyncio as aioredis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from airway.client.bisheng import BishengClient
from airway.models.mapping import UserMapping


class AuthProxy:
    def __init__(
        self,
        client: BishengClient,
        redis: aioredis.Redis,
        session: AsyncSession,
        key_prefix: str = "airway:",
        session_ttl: int = 3600,
    ):
        self._client = client
        self._redis = redis
        self._session = session
        self._key_prefix = key_prefix
        self._session_ttl = session_ttl

    def _cache_key(self, clawith_uid: str) -> str:
        return f"{self._key_prefix}session:{clawith_uid}"

    async def get_session(self, clawith_uid: str) -> str:
        # 1. Redis cache
        cache_key = self._cache_key(clawith_uid)
        cached = await self._redis.get(cache_key)
        if cached:
            return cached.decode()

        # 2. DB mapping
        result = await self._session.execute(
            select(UserMapping).where(UserMapping.clawith_uid == clawith_uid)
        )
        mapping = result.scalar_one_or_none()

        if mapping is None:
            # 3. Auto-register
            bisheng_username = f"clawith_{clawith_uid}"
            token = await self._client.login(bisheng_username, bisheng_username)
            mapping = UserMapping(
                clawith_uid=clawith_uid,
                bisheng_uid=bisheng_username,
                bisheng_username=bisheng_username,
            )
            self._session.add(mapping)
            await self._session.commit()
        else:
            # 4. Login with mapped account
            token = await self._client.login(
                mapping.bisheng_username, mapping.bisheng_username
            )

        # 5. Cache
        await self._redis.set(cache_key, token, ex=self._session_ttl)
        return token
