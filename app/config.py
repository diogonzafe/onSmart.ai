from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Auth System"
    DEBUG: bool = True
    
    # LLM configs
    LLAMA_MODEL_PATH: str = ""
    LLAMA_N_CTX: int = 4096
    LLAMA_N_GPU_LAYERS: int = -1
    LLAMA_VERBOSE: bool = False
    
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "mistral-medium"
    MISTRAL_API_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_EMBEDDING_MODEL: str = "mistral-embed"
    
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_EMBEDDING_MODEL: str = "deepseek-embed"
    
    # LLM Server settings - Properly integrated into the class
    LLM_SERVER_URL: str = "http://192.168.15.35:8000"
    LLM_SERVER_TIMEOUT: int = 1000
    
    # Security - Adicionando valor padrão para testes
    SECRET_KEY: str = "development-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "onsmart"
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = "555634611246-qtte6m0p42ugvuq6k14vvb75jp3fqel2.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "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"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()