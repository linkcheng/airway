from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8090


class BishengConfig(BaseModel):
    base_url: str = "http://localhost:7860"
    admin_user: str = "admin"
    admin_password: str = ""


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://airway:airway@localhost:5432/airway_db"


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379/0"
    key_prefix: str = "airway:"


class KnowledgeBaseEntry(BaseModel):
    name: str
    bisheng_knowledge_id: int
    description: str = ""


class AppConfig(BaseSettings):
    server: ServerConfig = ServerConfig()
    bisheng: BishengConfig = BishengConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    knowledge_bases: list[KnowledgeBaseEntry] = []

    def kb_name_to_id(self, name: str) -> int:
        for kb in self.knowledge_bases:
            if kb.name == name:
                return kb.bisheng_knowledge_id
        raise AirwayError("KB_NOT_FOUND", f'知识库 "{name}" 不存在')


class AirwayError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _resolve_env_vars(value: str) -> str:
    if isinstance(value, str) and "${" in value:
        start = value.index("${") + 2
        end = value.index("}", start)
        env_var = value[start:end]
        env_val = os.environ.get(env_var, "")
        return value[: start - 2] + env_val + value[end + 1 :]
    return value


def _resolve_dict(d: dict) -> dict:
    resolved: dict = {}
    for k, v in d.items():
        if isinstance(v, str):
            resolved[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            resolved[k] = _resolve_dict(v)
        elif isinstance(v, list):
            resolved[k] = [
                _resolve_dict(item) if isinstance(item, dict) else _resolve_env_vars(item) if isinstance(item, str) else item
                for item in v
            ]
        else:
            resolved[k] = v
    return resolved


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        resolved = _resolve_dict(raw)
        return AppConfig(**resolved)
    return AppConfig()
