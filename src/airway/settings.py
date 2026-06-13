from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bisheng_api_url: str = "http://localhost:7860"
    bisheng_token: str = ""
    bisheng_username: str = ""
    bisheng_password: str = ""
    server_host: str = "0.0.0.0"
    server_port: int = 8900
    api_timeout: float = 30.0
    user_tokens: dict[str, str] = {}
    bisheng_user_tokens: str = ""

    @field_validator("user_tokens", mode="before")
    @classmethod
    def parse_user_tokens(cls, v: str | dict[str, str]) -> dict[str, str]:
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v:
            tokens = {}
            for pair in v.split(","):
                pair = pair.strip()
                if ":" in pair:
                    uid, token = pair.split(":", 1)
                    tokens[uid.strip()] = token.strip()
            return tokens
        return {}

    model_config = {"env_file": ".env", "env_prefix": "AIRWAY_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
