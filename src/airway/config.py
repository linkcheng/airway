# src/airway/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bisheng
    bisheng_base_url: str = "http://localhost:7860"
    bisheng_admin_user: str = "admin"
    bisheng_admin_password: str

    # Clawith
    clawith_jwt_secret: str
    clawith_jwt_algorithm: str = "HS256"

    # PostgreSQL
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "airway:"

    # Airway
    airway_log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
