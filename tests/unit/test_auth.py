import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from airway.config import AppConfig, BishengConfig, RedisConfig


def _generate_real_public_key_pem() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.PKCS1,
    )
    return pem.decode()


REAL_PUBLIC_KEY = _generate_real_public_key_pem()


@pytest.fixture
def config():
    return AppConfig(
        bisheng=BishengConfig(
            base_url="http://bisheng-test:7860",
            admin_user="admin",
            admin_password="test_pass",
        ),
        redis=RedisConfig(url="redis://localhost:6379/0", key_prefix="airway:"),
    )


@pytest.mark.asyncio
async def test_fetch_rsa_public_key(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 200,
        "data": REAL_PUBLIC_KEY,
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(auth, "_redis_get", return_value=None),
        patch.object(auth, "_redis_set", new_callable=AsyncMock),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
    ):
        key = await auth.fetch_public_key()
        assert "BEGIN RSA PUBLIC KEY" in key


@pytest.mark.asyncio
async def test_encrypt_password(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)

    with patch.object(auth, "fetch_public_key", return_value=REAL_PUBLIC_KEY):
        encrypted = await auth.encrypt_password("mypassword")
        assert isinstance(encrypted, str)
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 0


@pytest.mark.asyncio
async def test_login_success(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)

    with (
        patch.object(auth, "encrypt_password", return_value="encrypted_pw"),
        patch.object(auth, "_redis_get", return_value=None),
        patch.object(auth, "_redis_set", new_callable=AsyncMock),
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 200,
            "data": {
                "access_token": "jwt_token_123",
                "user_id": 1,
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            token = await auth.login()
            assert token == "jwt_token_123"


@pytest.mark.asyncio
async def test_get_token_from_cache(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)

    with patch.object(auth, "_redis_get", return_value="cached_token"):
        token = await auth.get_token()
        assert token == "cached_token"


@pytest.mark.asyncio
async def test_get_token_cache_miss_triggers_login(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)

    with (
        patch.object(auth, "_redis_get", return_value=None),
        patch.object(auth, "login", return_value="fresh_token"),
    ):
        token = await auth.get_token()
        assert token == "fresh_token"


@pytest.mark.asyncio
async def test_register_user_success(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 200,
        "data": {"user_id": 42},
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(auth, "encrypt_password", return_value="enc_pw"),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response),
    ):
        user_id = await auth.register_user("clawith_user123", "airway_user123")
        assert user_id == 42


@pytest.mark.asyncio
async def test_register_user_conflict(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider
    from airway.config import AirwayError

    auth = BishengAuthProvider(config)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 10605,
        "status_message": "User Name already exist",
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(auth, "encrypt_password", return_value="enc_pw"),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response),
    ):
        with pytest.raises(AirwayError) as exc_info:
            await auth.register_user("clawith_existing", "airway_existing")
        assert exc_info.value.code == "USER_CONFLICT"


@pytest.mark.asyncio
async def test_login_user_success(config):
    from airway.adapters.bisheng.auth import BishengAuthProvider

    auth = BishengAuthProvider(config)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 200,
        "data": {
            "user_id": 42,
            "access_token": "user_jwt_token",
        },
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(auth, "encrypt_password", return_value="enc_pw"),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response),
    ):
        user_id, token = await auth.login_user("clawith_user123", "airway_user123")
        assert user_id == 42
        assert token == "user_jwt_token"
