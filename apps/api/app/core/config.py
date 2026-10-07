import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+psycopg2://postgres:postgres@localhost:5432/testscope", alias="DATABASE_URL")
    workspace_dir: str = Field(default="./workspace", alias="WORKSPACE_DIR")
    default_llm_provider: str = Field(default="gemini", alias="DEFAULT_LLM_PROVIDER")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
