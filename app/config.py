from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Google Drive settings
    GOOGLE_SERVICE_ACCOUNT_FILE: Path = None
    GOOGLE_SERVICE_ACCOUNT_JSON: str = None
    
    # Dify settings
    DIFY_BASE_URL: str = "https://api.dify.ai/v1"
    DIFY_API_KEY: str
    DIFY_DATASET_ID: str
    
    # App settings
    WEBHOOK_URL: str
    DATABASE_URL: str = "sqlite:///./app.db"
    TEMP_DOWNLOAD_PATH: Path = Path("./temp")
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
