from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    ANTHROPIC_API_KEY: str
    SCHWAB_CLIENT_ID: str = ""
    SCHWAB_CLIENT_SECRET: str = ""
    ALPHA_VANTAGE_KEY: str
    DATABASE_URL: str
    SUPABASE_URL: str  # e.g. https://xxx.supabase.co
    ALLOWED_EMAIL: str
    CORS_ORIGINS: str = "http://localhost:3060"  # comma-separated
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_PAPER: bool = True
    SLACK_WEBHOOK_URL: str = ""


settings = Settings()
