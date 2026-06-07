from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_USER_IDS: str = ""
    OPENAI_API_KEY: str = ""
    AGENT_SECRET: str = "change-me-to-a-long-random-string"
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT: str = "30/minute"
    WEBHOOK_URL: str = ""
    TTS_VOICE: str = "nova"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"

    class Config:
        env_file = ".env"


settings = Settings()
