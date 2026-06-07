import time

import jwt
import pytest

from airway.auth.jwt import verify_clawith_jwt


SECRET = "test_secret_key"


def test_verify_valid_jwt():
    token = jwt.encode({"sub": "user_123"}, SECRET, algorithm="HS256")
    user_id = verify_clawith_jwt(token, SECRET)
    assert user_id == "user_123"


def test_verify_expired_jwt():
    payload = {"sub": "user_123", "exp": time.time() - 3600}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_clawith_jwt(token, SECRET)


def test_verify_invalid_signature():
    token = jwt.encode({"sub": "user_123"}, "wrong_secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        verify_clawith_jwt(token, SECRET)


def test_verify_with_algorithm_mismatch():
    token = jwt.encode({"sub": "user_123"}, SECRET, algorithm="HS384")
    with pytest.raises(jwt.InvalidAlgorithmError):
        verify_clawith_jwt(token, SECRET, algorithm="HS256")
