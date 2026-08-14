import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    EIGI_API_KEY: str = "mock_eigi_key"
    EIGI_AGENT_ID: str = "agent_cod_recovery_v1"
    EIGI_BASE_URL: str = "https://api.eigi.ai/v1"
    EIGI_WEBHOOK_SECRET: str = "demo_webhook_secret"
    EIGI_TELEPHONY_PROVIDER: str = "PLIVO"

    TELEPHONY_PROVIDER: str = "eigi"
    ANDROID_GATEWAY_URL: str = "http://192.0.0.4:8080"
    DEFAULT_TEST_PHONE: str = "+919319297977"
    CALLER_ID_NUMBER: Optional[str] = None

    MERCHANT_NAME: str = "ShopAura"
    DATABASE_URL: str = "sqlite:///./recovery_engine.db"
    SIMULATION_MODE: bool = False

    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""


settings = Settings()
