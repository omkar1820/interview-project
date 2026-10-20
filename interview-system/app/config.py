from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: Optional[str] = None
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "interview_db"
    db_ssl_ca: Optional[str] = None

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    llm_mode: str = "auto"  # auto | openai | mock

    admin_api_key: Optional[str] = None
    default_num_questions: int = 5
    answer_timeout_seconds: int = 900
    runner_mode: str = "socket"  # socket (isolated runner container) | local (tests/dev only)
    runner_socket: str = "/run/runner/sock"
    code_timeout_seconds: float = 5.0

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def use_llm(self) -> bool:
        if self.llm_mode == "mock":
            return False
        if self.llm_mode == "openai":
            return True
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
