import redis.asyncio as aioredis
from sqlmodel import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from airway.client.bisheng import BishengClient
from airway.models.mapping import UserMapping


class AuthProxy:
    def __init__(
        self,
        client: BishengClient,
        redis: aioredis.Redis | None,
        session_factory: async_sessionmaker,
        key_prefix: str = "airway:",
        session_ttl: int = 3600,
    ):
        self._client = client
        self._redis = redis
        self._session_factory = session_factory
        self._key_prefix = key_prefix
        self._session_ttl = session_ttl

    def _cache_key(self, clawith_uid: str) -> str:
        return f"{self._key_prefix}session:{clawith_uid}"

    async def get_session(self, clawith_uid: str) -> str:
        if self._redis:
            cached = await self._redis.get(self._cache_key(clawith_uid))
            if cached:
                return cached.decode()
        return await self._acquire_session(clawith_uid)

    async def refresh_session(self, clawith_uid: str) -> str:
        if self._redis:
            await self._redis.delete(self._cache_key(clawith_uid))
        return await self._acquire_session(clawith_uid)

    async def _acquire_session(self, clawith_uid: str) -> str:
        token = await self._login_for_user(clawith_uid)
        if self._redis:
            await self._redis.set(
                self._cache_key(clawith_uid), token, ex=self._session_ttl,
            )
        return token

    async def _login_for_user(self, clawith_uid: str) -> str:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserMapping).where(UserMapping.clawith_uid == clawith_uid)
            )
            mapping = result.scalar_one_or_none()

            if mapping is None:
                bisheng_username = f"clawith_{clawith_uid}"
                token = await self._client.login(bisheng_username, bisheng_username)
                mapping = UserMapping(
                    clawith_uid=clawith_uid,
                    bisheng_uid=bisheng_username,
                    bisheng_username=bisheng_username,
                )
                session.add(mapping)
                await session.commit()
            else:
                token = await self._client.login(
                    mapping.bisheng_username, mapping.bisheng_username,
                )
        return token
