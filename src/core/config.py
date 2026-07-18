from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None

    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None

    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    SECRET_KEY: Optional[str] = None

    CLIENT_ID: Optional[str] = None
    CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/gmail/g/callback"

    GROQ_API_KEY: Optional[str] = None
    GROQ_AI_MODEL: str = "openai/gpt-oss-120b"
    MODEL_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    ALLOWED_ORIGINS: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
