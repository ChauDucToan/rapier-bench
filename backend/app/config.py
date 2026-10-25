from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./rapier.db"
    ARTIFACTS_DIR: str = "./artifacts"
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-prod"
    CUDA_VISIBLE_DEVICES: str = "0"
    HF_HOME: str = "~/.cache/huggingface"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    SECURE_COOKIES: bool = False
    ENV: str = "development"

    @property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS:
            return ["http://localhost:3000"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def artifacts_path(self) -> Path:
        p = Path(self.ARTIFACTS_DIR)
        return p.resolve()


settings = Settings()
