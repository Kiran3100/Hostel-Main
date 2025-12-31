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
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator, Field
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    @staticmethod
    def get_secret_key_default() -> str:
        """Generate a default secret key if not provided"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    # Application configuration - using aliases to match your .env
    APP_NAME: str = Field(default="Hostel Management System", alias="PROJECT_NAME")
    API_VERSION: str = Field(default="v1", alias="PROJECT_VERSION")
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    TIMEZONE: str = Field(default="UTC", alias="TIMEZONE")
    SECRET_KEY: str = Field(default_factory=lambda: Settings.get_secret_key_default())
    
    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False
    CORS_ORIGINS: List[str] = Field(default=["*"], alias="BACKEND_CORS_ORIGINS")
    
    # Database configuration - support both individual fields and DATABASE_URL
    DATABASE_URL: Optional[str] = None
    DATABASE_ECHO: bool = Field(default=False, alias="DATABASE_ECHO")
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "0987654321"
    DB_NAME: str = "HostelDb"
    DB_POOL_SIZE: int = 20
    DB_POOL_OVERFLOW: int = 10  # Fixed: was DB_MAX_OVERFLOW
    DB_ECHO: bool = False
    DB_CONNECT_ARGS: Dict[str, Any] = {}
    
    # Redis configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_POOL_SIZE: int = 10
    
    # Security configuration
    JWT_SECRET_KEY: str = Field(default_factory=lambda: Settings.get_secret_key_default())
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_BCRYPT_ROUNDS: int = 12
    ENCRYPTION_KEY: str = Field(default_factory=lambda: Settings.get_secret_key_default())
    
    # Rate limiting
    RATE_LIMIT_DEFAULT: int = 100
    RATE_LIMIT_PUBLIC_API: int = 20
    
    # File storage
    UPLOAD_DIR: str = Field(default="uploads", alias="UPLOAD_DIR")
    MAX_UPLOAD_SIZE: int = Field(default=10485760, alias="MAX_FILE_SIZE")
    ALLOWED_EXTENSIONS: Set[str] = Field(
        default={"jpg", "jpeg", "png", "pdf"}, 
        alias="ALLOWED_FILE_EXTENSIONS"
    )
    
    # Email configuration
    EMAIL_PROVIDER: str = Field(default="smtp", alias="EMAIL_PROVIDER")
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = Field(default=None, alias="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    EMAIL_FROM_NAME: str = "Hostel Management System"
    EMAIL_FROM_ADDRESS: Optional[str] = Field(default=None, alias="FROM_EMAIL")
    
    # SMS configuration
    SMS_PROVIDER: Optional[str] = None
    SMS_API_KEY: Optional[str] = None
    SMS_FROM_NUMBER: Optional[str] = None
    MSG91_API_KEY: Optional[str] = None
    MSG91_SENDER_ID: Optional[str] = None
    
    # Cache settings
    CACHE_BACKEND: str = Field(default="memory", alias="CACHE_BACKEND")
    
    # Payment gateway
    CURRENCY: str = Field(default="INR", alias="CURRENCY")
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    PAYMENT_GATEWAY_API_KEY: Optional[str] = None
    PAYMENT_GATEWAY_SECRET: Optional[str] = None
    PAYMENT_GATEWAY_MODE: str = "sandbox"
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    
    # Business logic
    BOOKING_ADVANCE_DAYS: int = 365
    ADVANCE_PAYMENT_PERCENTAGE: int = 20
    NOTIFICATION_REMINDER_HOURS: List[int] = Field(default=[72, 24, 2])
    
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
        extra = "ignore"  # This will ignore extra fields from .env
    
    # Validators
    @validator('CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS_ORIGINS from string to list"""
        if isinstance(v, str):
            # Handle JSON string format from .env
            if v.startswith('[') and v.endswith(']'):
                try:
                    import json
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator('ALLOWED_EXTENSIONS', pre=True)
    def parse_allowed_extensions(cls, v: Union[str, Set[str], List[str]]) -> Set[str]:
        """Parse ALLOWED_EXTENSIONS from string to set"""
        if isinstance(v, str):
            if v.startswith('[') and v.endswith(']'):
                try:
                    import json
                    extensions = json.loads(v)
                    # Remove dots from extensions if present
                    return {ext.lstrip('.') for ext in extensions}
                except json.JSONDecodeError:
                    pass
            return {ext.strip().lstrip('.') for ext in v.split(",")}
        elif isinstance(v, list):
            return {ext.lstrip('.') for ext in v}
        return v
    
    @validator('NOTIFICATION_REMINDER_HOURS', pre=True)
    def parse_reminder_hours(cls, v: Union[str, List[int]]) -> List[int]:
        """Parse NOTIFICATION_REMINDER_HOURS from string to list"""
        if isinstance(v, str):
            if v.startswith('[') and v.endswith(']'):
                try:
                    import json
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [int(x.strip()) for x in v.split(",")]
        return v
    
    @validator('DATABASE_URL', pre=True, always=True)
    def validate_database_url(cls, v, values):
        """Validate and potentially construct DATABASE_URL"""
        if v:
            # If DATABASE_URL is provided, extract components for consistency
            import re
            pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
            match = re.match(pattern, v)
            if match:
                values['DB_USER'] = match.group(1)
                values['DB_PASSWORD'] = match.group(2)
                values['DB_HOST'] = match.group(3)
                values['DB_PORT'] = int(match.group(4))
                values['DB_NAME'] = match.group(5)
        return v
    
    def get_database_url(self) -> str:
        """Construct database URL from components or use provided URL"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # Construct from individual components
        url = f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return url
    
    def get_redis_url(self) -> str:
        """Get Redis URL"""
        return self.REDIS_URL
    
    def get_api_url(self) -> str:
        """Get full API URL"""
        return f"http://{self.HOST}:{self.PORT}{self.API_V1_STR}"
    
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