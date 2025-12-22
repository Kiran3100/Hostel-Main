"""
Environment configuration for the hostel management system.
Uses Pydantic's settings management to handle environment variables
with proper type validation and default values.
"""

import os
import json
from typing import Dict, List, Optional, Set, Any, Union
from pathlib import Path
from functools import lru_cache
from pydantic import BaseSettings, AnyHttpUrl, validator, Field
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application configuration
    APP_NAME: str = "Hostel Management System"
    API_VERSION: str = "v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    TIMEZONE: str = "UTC"
    SECRET_KEY: str = Field(..., min_length=32)
    
    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = Field(..., min_length=1)
    DB_NAME: str = "hostel_management"
    DB_POOL_SIZE: int = 20
    DB_POOL_OVERFLOW: int = 10
    DB_ECHO: bool = False
    DB_CONNECT_ARGS: Dict[str, Any] = {}
    
    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_POOL_SIZE: int = 10
    
    # Security configuration
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    PASSWORD_BCRYPT_ROUNDS: int = 12
    ENCRYPTION_KEY: str = Field(..., min_length=32)
    
    # Rate limiting
    RATE_LIMIT_DEFAULT: int = 100  # per minute
    RATE_LIMIT_PUBLIC_API: int = 20  # per minute
    
    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: Set[str] = {"jpg", "jpeg", "png", "pdf", "doc", "docx"}
    
    # Email configuration
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    EMAIL_FROM_NAME: str = "Hostel Management System"
    EMAIL_FROM_ADDRESS: Optional[str] = None
    
    # SMS configuration
    SMS_PROVIDER: Optional[str] = None
    SMS_API_KEY: Optional[str] = None
    SMS_FROM_NUMBER: Optional[str] = None
    
    # Third-party integrations
    PAYMENT_GATEWAY_API_KEY: Optional[str] = None
    PAYMENT_GATEWAY_SECRET: Optional[str] = None
    PAYMENT_GATEWAY_MODE: str = "sandbox"  # sandbox, production
    
    # Google authentication
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    
    # Monitoring and logging
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = False
    
    # Feature flags
    FEATURE_FLAGS: Dict[str, bool] = Field(default_factory=dict)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    # Validators
    @validator('CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS_ORIGINS from string to list"""
        if isinstance(v, str):
            return v.split(",")
        return v
    
    @validator('DB_CONNECT_ARGS', pre=True)
    def parse_db_connect_args(cls, v: Union[str, Dict]) -> Dict:
        """Parse DB_CONNECT_ARGS from JSON string to dict"""
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    @validator('FEATURE_FLAGS', pre=True)
    def parse_feature_flags(cls, v: Union[str, Dict]) -> Dict:
        """Parse FEATURE_FLAGS from JSON string to dict"""
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    def get_database_url(self) -> str:
        """Construct database URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    def get_redis_url(self) -> str:
        """Construct Redis URL"""
        auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    def get_api_url(self) -> str:
        """Get full API URL"""
        return f"http://{self.HOST}:{self.PORT}/api/{self.API_VERSION}"
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT == "development"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

settings = get_settings()