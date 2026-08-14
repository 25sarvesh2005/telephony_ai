import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class D2CSettings(BaseSettings):
    """Configuration settings for the D2C E-commerce Application."""
    
    STORE_NAME: str = "Aura Luxe Direct"
    STORE_CURRENCY: str = "INR"
    DEFAULT_SHIPPING_FEE: float = 0.0  # Free shipping threshold
    FREE_SHIPPING_MIN_ORDER: float = 999.0
    STANDARD_SHIPPING_FEE: float = 99.0
    
    # Database
    DATABASE_URL: str = "sqlite:///./d2c_store.db"
    
    # AI Telephony Recovery Engine API URL
    RECOVERY_ENGINE_URL: str = "http://127.0.0.1:8000"
    AUTO_TRIGGER_VOICE_RECOVERY_ON_NDR: bool = True
    
    # Telephony Provider Preference for D2C ('eigi', 'android_jio', 'simulation')
    DEFAULT_TELEPHONY_PROVIDER: str = "eigi"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


d2c_settings = D2CSettings()
