from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str
    UPSTASH_REDIS_REST_URL:str
    UPSTASH_REDIS_REST_TOKEN:str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    CLIENT_ID: str
    CLIENT_SECRET: str
    OPEN_AI_MODEL: str 
    BASE_URL: str
    MCP_URL:str
    LIQUID_MODEL: str 
    OPENROUTER_API_KEY: str = ""
    GOOGLE_REDIRECT_URI: str = "https://inbox-os-ai.onrender.com/gmail/g/callback"
    ALLOWED_ORIGINS: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


configure = Settings()