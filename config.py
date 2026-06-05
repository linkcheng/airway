import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8090


class KnowledgeBase(BaseModel):
    name: str
    assistant_id: str
    kb_id: str


class BishengConfig(BaseModel):
    v2_api_url: str
    v1_api_url: str
    admin_username: str
    admin_password: str
    redis_url: str
    knowledge_bases: list[KnowledgeBase] = []


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    bisheng: BishengConfig

    @property
    def knowledge_base_map(self) -> dict[str, KnowledgeBase]:
        return {kb.name: kb for kb in self.bisheng.knowledge_bases}


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _substitute_env_vars(value: str) -> str:
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"环境变量 {var_name} 未设置")
        return env_value
    return _ENV_VAR_PATTERN.sub(_replace, value)


def _substitute_dict(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        elif isinstance(value, list):
            result[key] = [_substitute_dict(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            result[key] = _substitute_dict(value)
        else:
            result[key] = value
    return result


def load_config(path: str) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text())
    resolved = _substitute_dict(raw)
    return AppConfig(**resolved)
