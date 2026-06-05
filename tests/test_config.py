# tests/test_config.py
import os

import pytest


def test_config_loads_from_env():
    os.environ["BISHENG_BASE_URL"] = "http://test:7860"
    os.environ["BISHENG_ADMIN_USER"] = "admin"
    os.environ["BISHENG_ADMIN_PASSWORD"] = "secret"
    os.environ["CLAWITH_JWT_SECRET"] = "jwt_secret"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://u:p@localhost/airway"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["REDIS_KEY_PREFIX"] = "test:"

    from airway.config import Settings

    s = Settings()
    assert s.bisheng_base_url == "http://test:7860"
    assert s.bisheng_admin_user == "admin"
    assert s.clawith_jwt_secret == "jwt_secret"
    assert s.redis_key_prefix == "test:"

    # cleanup
    for key in [
        "BISHENG_BASE_URL", "BISHENG_ADMIN_USER", "BISHENG_ADMIN_PASSWORD",
        "CLAWITH_JWT_SECRET", "DATABASE_URL", "REDIS_URL", "REDIS_KEY_PREFIX",
    ]:
        os.environ.pop(key, None)


def test_config_has_defaults():
    from airway.config import Settings

    s = Settings(
        bisheng_admin_password="x",
        clawith_jwt_secret="x",
        database_url="postgresql+asyncpg://u:p@h/d",
    )
    assert s.bisheng_base_url == "http://localhost:7860"
    assert s.clawith_jwt_algorithm == "HS256"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.redis_key_prefix == "airway:"
    assert s.airway_log_level == "INFO"
