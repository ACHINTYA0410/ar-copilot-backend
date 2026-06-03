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

    # ORP data source — swap to "mysql" or "api" when real ORP access arrives
    ORP_PROVIDER: str = "local_sqlite"


settings = Settings()
