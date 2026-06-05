import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

from adapters.bisheng.auth import BishengV1Client

BASE_URL = "http://test"


def _generate_rsa_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_key, public_pem


@respx.mock
async def test_login_success():
    private_key, public_pem = _generate_rsa_key_pair()

    respx.post(f"{BASE_URL}/api/v1/user/public_key").mock(
        return_value=httpx.Response(200, json={"public_key": public_pem})
    )
    respx.post(f"{BASE_URL}/api/v1/user/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok123", "refresh_token": "tok123"}
        )
    )

    client = BishengV1Client(
        base_url=BASE_URL, username="admin", password="secret"
    )
    await client.login()

    assert client.access_token == "tok123"


@respx.mock
async def test_login_encrypts_password_with_rsa():
    private_key, public_pem = _generate_rsa_key_pair()

    respx.post(f"{BASE_URL}/api/v1/user/public_key").mock(
        return_value=httpx.Response(200, json={"public_key": public_pem})
    )

    login_route = respx.post(f"{BASE_URL}/api/v1/user/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "refresh_token": "tok"}
        )
    )

    client = BishengV1Client(
        base_url=BASE_URL, username="admin", password="my_secret"
    )
    await client.login()

    login_request = login_route.calls[0].request
    body = json.loads(login_request.read().decode())

    encrypted_bytes = base64.b64decode(body["password"])
    decrypted = private_key.decrypt(encrypted_bytes, padding.PKCS1v15())
    assert decrypted.decode() == "my_secret"


@respx.mock
async def test_token_auto_refresh_before_expiry():
    private_key, public_pem = _generate_rsa_key_pair()

    respx.post(f"{BASE_URL}/api/v1/user/public_key").mock(
        return_value=httpx.Response(200, json={"public_key": public_pem})
    )
    login_route = respx.post(f"{BASE_URL}/api/v1/user/login").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "old_tok", "refresh_token": "old_tok"}),
            httpx.Response(200, json={"access_token": "new_tok", "refresh_token": "new_tok"}),
        ]
    )

    client = BishengV1Client(
        base_url=BASE_URL, username="admin", password="secret"
    )
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    with patch("adapters.bisheng.auth.datetime") as mock_dt:
        mock_dt.now.return_value = now
        await client.login()

    assert client.access_token == "old_tok"

    now_plus_23h = now + timedelta(hours=23)
    with patch("adapters.bisheng.auth.datetime") as mock_dt:
        mock_dt.now.return_value = now_plus_23h
        await client.ensure_token()

    assert client.access_token == "new_tok"
    assert login_route.call_count == 2


@respx.mock
async def test_token_still_valid_skips_refresh():
    private_key, public_pem = _generate_rsa_key_pair()

    respx.post(f"{BASE_URL}/api/v1/user/public_key").mock(
        return_value=httpx.Response(200, json={"public_key": public_pem})
    )
    login_route = respx.post(f"{BASE_URL}/api/v1/user/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "refresh_token": "tok"}
        )
    )

    client = BishengV1Client(
        base_url=BASE_URL, username="admin", password="secret"
    )
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    with patch("adapters.bisheng.auth.datetime") as mock_dt:
        mock_dt.now.return_value = now
        await client.login()

    now_plus_10h = now + timedelta(hours=10)
    with patch("adapters.bisheng.auth.datetime") as mock_dt:
        mock_dt.now.return_value = now_plus_10h
        await client.ensure_token()

    assert client.access_token == "tok"
    assert login_route.call_count == 1


@respx.mock
async def test_login_failure_raises():
    private_key, public_pem = _generate_rsa_key_pair()

    respx.post(f"{BASE_URL}/api/v1/user/public_key").mock(
        return_value=httpx.Response(200, json={"public_key": public_pem})
    )
    respx.post(f"{BASE_URL}/api/v1/user/login").mock(
        return_value=httpx.Response(401, json={"message": "Invalid credentials"})
    )

    client = BishengV1Client(
        base_url=BASE_URL, username="admin", password="wrong"
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.login()

    assert client.access_token is None
