import pytest
import yaml


@pytest.fixture
def write_config(tmp_path):
    def _write(data: dict):
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(data, default_flow_style=False))
        return str(path)
    return _write


def make_valid_config() -> dict:
    return {
        "server": {
            "host": "0.0.0.0",
            "port": 8090,
        },
        "bisheng": {
            "v2_api_url": "http://bisheng-backend:7860/api/v2",
            "v1_api_url": "http://bisheng-backend:7860/api/v1",
            "admin_username": "${BISHENG_ADMIN_USER}",
            "admin_password": "${BISHENG_ADMIN_PASS}",
            "redis_url": "redis://redis:6379/0",
            "knowledge_bases": [
                {
                    "name": "产品文档",
                    "assistant_id": "asst_xxx",
                    "kb_id": "kb_xxx",
                },
            ],
        },
    }


def test_load_config_from_yaml(write_config, monkeypatch):
    config_path = write_config(make_valid_config())
    monkeypatch.setenv("BISHENG_ADMIN_USER", "admin")
    monkeypatch.setenv("BISHENG_ADMIN_PASS", "pass123")

    from config import load_config

    cfg = load_config(config_path)

    assert cfg.server.host == "0.0.0.0", "server.host 应为配置文件中的值"
    assert cfg.server.port == 8090, "server.port 应为配置文件中的值"
    assert cfg.bisheng.v2_api_url == "http://bisheng-backend:7860/api/v2", "bisheng.v2_api_url 应正确加载"


def test_env_var_substitution(write_config, monkeypatch):
    monkeypatch.setenv("BISHENG_ADMIN_USER", "test_admin")
    monkeypatch.setenv("BISHENG_ADMIN_PASS", "s3cret!")

    config_path = write_config(make_valid_config())

    from config import load_config

    cfg = load_config(config_path)

    assert cfg.bisheng.admin_username == "test_admin", "${BISHENG_ADMIN_USER} 应被替换为环境变量值"
    assert cfg.bisheng.admin_password == "s3cret!", "${BISHENG_ADMIN_PASS} 应被替换为环境变量值"


def test_missing_env_var_raises(write_config, monkeypatch):
    monkeypatch.delenv("BISHENG_ADMIN_USER", raising=False)
    monkeypatch.delenv("BISHENG_ADMIN_PASS", raising=False)

    config_path = write_config(make_valid_config())

    from config import load_config

    with pytest.raises(ValueError, match="环境变量.*未设置"):
        load_config(config_path)


def test_default_values(write_config, monkeypatch):
    monkeypatch.setenv("BISHENG_ADMIN_USER", "admin")
    monkeypatch.setenv("BISHENG_ADMIN_PASS", "pass")

    minimal = {
        "bisheng": {
            "v2_api_url": "http://bisheng-backend:7860/api/v2",
            "v1_api_url": "http://bisheng-backend:7860/api/v1",
            "admin_username": "${BISHENG_ADMIN_USER}",
            "admin_password": "${BISHENG_ADMIN_PASS}",
            "redis_url": "redis://redis:6379/0",
            "knowledge_bases": [],
        },
    }
    config_path = write_config(minimal)

    from config import load_config

    cfg = load_config(config_path)

    assert cfg.server.host == "0.0.0.0", "默认 host 应为 0.0.0.0"
    assert cfg.server.port == 8090, "默认 port 应为 8090"


def test_knowledge_base_map(write_config, monkeypatch):
    monkeypatch.setenv("BISHENG_ADMIN_USER", "admin")
    monkeypatch.setenv("BISHENG_ADMIN_PASS", "pass")

    data = make_valid_config()
    data["bisheng"]["knowledge_bases"] = [
        {"name": "产品文档", "assistant_id": "asst_aaa", "kb_id": "kb_aaa"},
        {"name": "FAQ", "assistant_id": "asst_bbb", "kb_id": "kb_bbb"},
    ]
    config_path = write_config(data)

    from config import load_config

    cfg = load_config(config_path)
    kb_map = cfg.knowledge_base_map

    assert "产品文档" in kb_map, "knowledge_base_map 应包含产品文档"
    assert kb_map["产品文档"].assistant_id == "asst_aaa", "产品文档的 assistant_id 应正确"
    assert "FAQ" in kb_map, "knowledge_base_map 应包含 FAQ"
    assert kb_map["FAQ"].kb_id == "kb_bbb", "FAQ 的 kb_id 应正确"
