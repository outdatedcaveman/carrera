from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 8000
    secret_key: str = "dev-secret-change-in-production"
    database_url: str = "sqlite:///./data/carrera.db"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email: str = ""

    request_timeout: int = 30
    request_delay_min: float = 1.0
    request_delay_max: float = 3.0
    max_jobs_per_run: int = 100

    scrape_schedule: str = "0 8,18 * * *"

    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # AI provider settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # PDF output directory
    pdf_output_dir: str = "./data/pdfs"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
