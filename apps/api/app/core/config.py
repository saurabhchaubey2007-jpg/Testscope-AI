import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(default="sqlite:///./testscope.db", alias="DATABASE_URL")
    workspace_dir: str = Field(default="./workspace", alias="WORKSPACE_DIR")
    default_llm_provider: str = Field(default="gemini", alias="DEFAULT_LLM_PROVIDER")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    use_fake_llm: bool = Field(default=False, alias="USE_FAKE_LLM")

    # Auth
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, alias="JWT_EXPIRE_MINUTES")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Background execution
    max_concurrent_runs: int = Field(default=2, alias="MAX_CONCURRENT_RUNS")

    # GitHub
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
