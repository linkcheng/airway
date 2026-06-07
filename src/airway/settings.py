from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bisheng_api_url: str = "http://localhost:7860"
    bisheng_token: str = ""
    bisheng_username: str = ""
    bisheng_password: str = ""
    server_host: str = "0.0.0.0"
    server_port: int = 8900
    api_timeout: float = 30.0

    model_config = {"env_file": ".env", "env_prefix": "AIRWAY_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
