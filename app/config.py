from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://poidem:poidem@localhost:5432/poidem"
    parser_scheduler_enabled: bool = False
    parser_request_timeout_seconds: float = 20
    parser_max_retries: int = 3
    parser_request_delay_seconds: float = 1
    stale_after_days: int = 7
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def debug_auth_enabled(self) -> bool:
        return self.app_env in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

