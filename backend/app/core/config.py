from pydantic import AnyHttpUrl, Field, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_FRONTEND_ORIGIN = "http://localhost:5173"


class Settings(BaseSettings):
    app_name: str = "Gestor Inteligente de Reviews"
    env: str = "development"
    database_url: str = "sqlite:///./gestor_reviews.db"
    secret_key: str = "CHANGE_ME_USE_A_LONG_RANDOM_SECRET_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = Field(default_factory=lambda: [LOCAL_FRONTEND_ORIGIN])

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        validated = []
        for origin in origins:
            url = TypeAdapter(AnyHttpUrl).validate_python(origin.strip())
            if (
                url.username is not None
                or url.password is not None
                or url.path not in (None, "/")
                or url.query is not None
                or url.fragment is not None
                or "*" in str(url)
            ):
                raise ValueError("CORS_ORIGINS debe contener solo orígenes HTTP o HTTPS completos")
            normalized = str(url).rstrip("/")
            if normalized not in validated:
                validated.append(normalized)
        return validated

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
