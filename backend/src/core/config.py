import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENV: str = Field(default="dev")
    DEBUG: bool = Field(default=True)
    PROJECT_NAME: str = Field(default="NEWPOD Escrow Platform")
    API_V1_STR: str = Field(default="/api/v1")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://newpod_user:newpod_secure_password@localhost:5433/newpod_db"
    )

    # Redis & Celery
    REDIS_URL: str = Field(default="redis://localhost:6380/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = Field(default="super_secure_secret_key_change_me_in_prod_12345")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = Field(default=["*"])

    # Paystack Integration
    PAYSTACK_SECRET_KEY: str = Field(default="sk_test_mock_secret_key_for_development")
    PAYSTACK_BASE_URL: str = Field(default="https://api.paystack.co")

    # KYC & Identity
    MOCK_KYC_VERIFICATION: bool = Field(default=True)

settings = Settings()
