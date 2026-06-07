import pytest
import fakeredis.aioredis

from airway.auth.proxy import AuthProxy
from airway.models.mapping import UserMapping


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


@pytest.fixture
def mock_client():
    class MockClient:
        async def login(self, username, password):
            if password == "wrong":
                raise Exception("Login failed")
            return f"token_{username}"

    return MockClient()


@pytest.fixture
def proxy(mock_client, redis, session_factory):
    return AuthProxy(
        client=mock_client,
        redis=redis,
        session_factory=session_factory,
        key_prefix="airway:",
    )


@pytest.mark.asyncio
async def test_get_session_cache_hit(proxy, redis):
    await redis.set("airway:session:u_test", "cached_token_123")
    token = await proxy.get_session("u_test")
    assert token == "cached_token_123"


@pytest.mark.asyncio
async def test_get_session_from_mapping(proxy, redis, session_factory):
    async with session_factory() as session:
        from sqlmodel import select

        mapping = UserMapping(
            clawith_uid="u_abc", bisheng_uid="42", bisheng_username="clawith_u_abc",
        )
        session.add(mapping)
        await session.commit()

    token = await proxy.get_session("u_abc")
    assert token == "token_clawith_u_abc"

    cached = await redis.get("airway:session:u_abc")
    assert cached == b"token_clawith_u_abc"


@pytest.mark.asyncio
async def test_get_session_auto_register(proxy, redis, session_factory):
    token = await proxy.get_session("u_new")
    assert token == "token_clawith_u_new"

    async with session_factory() as session:
        from sqlmodel import select

        result = await session.execute(
            select(UserMapping).where(UserMapping.clawith_uid == "u_new")
        )
        mapping = result.scalar_one()
    assert mapping.bisheng_username == "clawith_u_new"

    cached = await redis.get("airway:session:u_new")
    assert cached == b"token_clawith_u_new"
