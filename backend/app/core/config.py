from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_FRONTEND_ORIGIN = "http://localhost:5173"


class Settings(BaseSettings):
    app_name: str = "Gestor Inteligente de Reviews"
    env: str = "development"
    database_url: str = "sqlite:///./gestor_reviews.db"
    secret_key: str = "CHANGE_ME"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
