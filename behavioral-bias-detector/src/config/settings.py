from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Behavioral Bias Detection System"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    workers: int = 4
    benchmark_concurrency: int = 8

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "bias_detector"
    postgres_user: str = "postgres"
    postgres_password: str = "change_me"

    redis_host: str = "localhost"
    redis_port: int = 6379

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    together_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

