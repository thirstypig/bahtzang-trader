from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    ANTHROPIC_API_KEY: str
    SCHWAB_CLIENT_ID: str
    SCHWAB_CLIENT_SECRET: str
    ALPHA_VANTAGE_KEY: str
    DATABASE_URL: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    ALLOWED_EMAIL: str
    JWT_SECRET: str
    CORS_ORIGINS: str = "http://localhost:3000"  # comma-separated


settings = Settings()
