import os
import tempfile

import pytest

from airway.config import AppConfig, AirwayError, load_config


def test_load_yaml_config():
    yaml_content = """
server:
  host: "0.0.0.0"
  port: 9090
bisheng:
  base_url: "http://test:7860"
  admin_user: "admin"
  admin_password: "secret"
knowledge_bases:
  - name: "test-kb"
    bisheng_knowledge_id: 42
    description: "Test KB"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)

    assert config.server.port == 9090
    assert config.bisheng.base_url == "http://test:7860"
    assert len(config.knowledge_bases) == 1
    assert config.knowledge_bases[0].name == "test-kb"
    assert config.knowledge_bases[0].bisheng_knowledge_id == 42


def test_load_config_missing_file():
    config = load_config("/nonexistent/config.yaml")
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8090
    assert config.knowledge_bases == []


def test_env_var_override():
    yaml_content = """
bisheng:
  admin_password: "${TEST_BISHENG_PW}"
"""
    os.environ["TEST_BISHENG_PW"] = "env_secret"
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(f.name)
        os.unlink(f.name)
        assert config.bisheng.admin_password == "env_secret"
    finally:
        del os.environ["TEST_BISHENG_PW"]


def test_kb_name_to_id():
    config = AppConfig(
        knowledge_bases=[
            {"name": "faq", "bisheng_knowledge_id": 1},
            {"name": "docs", "bisheng_knowledge_id": 2},
        ]
    )
    assert config.kb_name_to_id("faq") == 1
    assert config.kb_name_to_id("docs") == 2

    with pytest.raises(AirwayError) as exc_info:
        config.kb_name_to_id("nonexistent")
    assert "不存在" in exc_info.value.message


def test_default_values():
    config = AppConfig()
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8090
    assert config.bisheng.base_url == "http://localhost:7860"
    assert config.database.url.startswith("postgresql+asyncpg")
    assert config.redis.key_prefix == "airway:"
    assert config.knowledge_bases == []


def test_invalid_type_raises_validation_error():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AppConfig(server={"port": "not_a_number"})

    with pytest.raises(ValidationError):
        AppConfig(knowledge_bases=[{"name": 123}])


def test_empty_knowledge_bases():
    yaml_content = """
server:
  host: "127.0.0.1"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)

    assert config.knowledge_bases == []
    assert config.server.host == "127.0.0.1"
