from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_PORT: int = 8000
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./ar_copilot.db"

    FRONTEND_URL: str = "http://localhost:5173"

    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    AI_PROVIDER: str = "mock"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_MATCHING_MODEL: str = "llama-3.3-70b-versatile"

    USE_GROQ_FOR_PO: bool = True

    # Vision extraction provider — "groq" (active) or "gemini" (stubbed)
    VISION_PROVIDER: str = "groq"

    # Item matching provider for reconciliation — "groq" (active) or "gemini" (stubbed)
    MATCHING_PROVIDER: str = "groq"

    # ORP data source — swap to "mysql" or "api" when real ORP access arrives
    ORP_PROVIDER: str = "local_sqlite"

    # AWS S3 — PO document storage
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str | None = None


settings = Settings()
