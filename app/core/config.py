"""
Configuration Management

Centralized configuration management using Pydantic Settings for type safety
and environment variable integration.
"""

import os
from typing import Optional, List, Dict, Any
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from pydantic.networks import AnyHttpUrl


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    
    DB_HOST: str = Field(default="localhost", env="DB_HOST")
    DB_PORT: int = Field(default=5432, env="DB_PORT")
    DB_USER: str = Field(default="hostel_user", env="DB_USER")
    DB_PASSWORD: str = Field(default="password", env="DB_PASSWORD")
    DB_NAME: str = Field(default="hostel_db", env="DB_NAME")
    DB_DRIVER: str = Field(default="postgresql+asyncpg", env="DB_DRIVER")
    
    # Connection pool settings
    DB_POOL_SIZE: int = Field(default=20, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=30, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # Advanced settings
    DB_ECHO: bool = Field(default=False, env="DB_ECHO")
    DB_ECHO_POOL: bool = Field(default=False, env="DB_ECHO_POOL")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }
    
    @property
    def database_url(self) -> str:
        """Generate database URL from components"""
        return f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def sync_database_url(self) -> str:
        """Generate synchronous database URL"""
        driver = self.DB_DRIVER.replace("+asyncpg", "").replace("+aiomysql", "")
        return f"{driver}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


class RedisSettings(BaseSettings):
    """Redis configuration settings"""
    
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_SSL: bool = Field(default=False, env="REDIS_SSL")
    
    # Connection settings
    REDIS_MAX_CONNECTIONS: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    REDIS_RETRY_ON_TIMEOUT: bool = Field(default=True, env="REDIS_RETRY_ON_TIMEOUT")
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(default=5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    REDIS_SOCKET_TIMEOUT: int = Field(default=30, env="REDIS_SOCKET_TIMEOUT")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }
    
    @property
    def redis_url(self) -> str:
        """Generate Redis URL"""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        protocol = "rediss" if self.REDIS_SSL else "redis"
        return f"{protocol}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class SecuritySettings(BaseSettings):
    """Security configuration settings"""
    
    SECRET_KEY: str = Field(
        default="09f26e402586e2faa8da4c98a35f1b20d6b033c6097befa8be3486a829587fe2f90a832bd3ff9d42710a4da095a2ce285b009f0c3730cd9b8e1af3eb84df6611",
        env="SECRET_KEY",
        min_length=32
    )
    ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Password settings
    PASSWORD_MIN_LENGTH: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    PASSWORD_REQUIRE_UPPERCASE: bool = Field(default=True, env="PASSWORD_REQUIRE_UPPERCASE")
    PASSWORD_REQUIRE_LOWERCASE: bool = Field(default=True, env="PASSWORD_REQUIRE_LOWERCASE")
    PASSWORD_REQUIRE_NUMBERS: bool = Field(default=True, env="PASSWORD_REQUIRE_NUMBERS")
    PASSWORD_REQUIRE_SPECIAL: bool = Field(default=True, env="PASSWORD_REQUIRE_SPECIAL")
    
    # Session settings
    SESSION_TIMEOUT_MINUTES: int = Field(default=60, env="SESSION_TIMEOUT_MINUTES")
    MAX_LOGIN_ATTEMPTS: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    LOCKOUT_DURATION_MINUTES: int = Field(default=30, env="LOCKOUT_DURATION_MINUTES")
    
    # Security headers
    ENABLE_SECURITY_HEADERS: bool = Field(default=True, env="ENABLE_SECURITY_HEADERS")
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class CacheSettings(BaseSettings):
    """Cache configuration settings"""
    
    CACHE_BACKEND: str = Field(default="redis", env="CACHE_BACKEND")
    CACHE_DEFAULT_TIMEOUT: int = Field(default=300, env="CACHE_DEFAULT_TIMEOUT")
    CACHE_KEY_PREFIX: str = Field(default="hostel:", env="CACHE_KEY_PREFIX")
    
    # Cache timeouts for different data types
    CACHE_USER_TIMEOUT: int = Field(default=600, env="CACHE_USER_TIMEOUT")
    CACHE_PERMISSION_TIMEOUT: int = Field(default=300, env="CACHE_PERMISSION_TIMEOUT")
    CACHE_DASHBOARD_TIMEOUT: int = Field(default=180, env="CACHE_DASHBOARD_TIMEOUT")
    CACHE_STATS_TIMEOUT: int = Field(default=900, env="CACHE_STATS_TIMEOUT")
    
    # Cache size limits
    CACHE_MAX_SIZE: int = Field(default=10000, env="CACHE_MAX_SIZE")
    CACHE_CLEANUP_INTERVAL: int = Field(default=3600, env="CACHE_CLEANUP_INTERVAL")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


class LoggingSettings(BaseSettings):
    """Logging configuration settings"""
    
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")  # json or text
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")
    LOG_ROTATION: str = Field(default="daily", env="LOG_ROTATION")
    LOG_RETENTION: int = Field(default=30, env="LOG_RETENTION")  # days
    
    # Structured logging
    ENABLE_STRUCTURED_LOGGING: bool = Field(default=True, env="ENABLE_STRUCTURED_LOGGING")
    LOG_REQUEST_ID: bool = Field(default=True, env="LOG_REQUEST_ID")
    LOG_SQL_QUERIES: bool = Field(default=False, env="LOG_SQL_QUERIES")
    
    # External logging
    ENABLE_EXTERNAL_LOGGING: bool = Field(default=False, env="ENABLE_EXTERNAL_LOGGING")
    EXTERNAL_LOG_ENDPOINT: Optional[str] = Field(default=None, env="EXTERNAL_LOG_ENDPOINT")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of {valid_levels}')
        return v.upper()


class MonitoringSettings(BaseSettings):
    """Monitoring and metrics configuration"""
    
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_ENDPOINT: str = Field(default="/metrics", env="METRICS_ENDPOINT")
    METRICS_PORT: int = Field(default=8090, env="METRICS_PORT")
    
    # Performance monitoring
    TRACK_RESPONSE_TIME: bool = Field(default=True, env="TRACK_RESPONSE_TIME")
    TRACK_DATABASE_QUERIES: bool = Field(default=True, env="TRACK_DATABASE_QUERIES")
    TRACK_CACHE_HITS: bool = Field(default=True, env="TRACK_CACHE_HITS")
    
    # Health checks
    HEALTH_CHECK_INTERVAL: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    ENABLE_DEPENDENCY_CHECKS: bool = Field(default=True, env="ENABLE_DEPENDENCY_CHECKS")
    
    # External monitoring
    PROMETHEUS_ENABLED: bool = Field(default=False, env="PROMETHEUS_ENABLED")
    GRAFANA_ENABLED: bool = Field(default=False, env="GRAFANA_ENABLED")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


class NotificationSettings(BaseSettings):
    """Notification system configuration"""
    
    # Email settings
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    
    # Email templates
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@hostel.com", env="EMAIL_FROM_ADDRESS")
    EMAIL_FROM_NAME: str = Field(default="Hostel Management", env="EMAIL_FROM_NAME")
    EMAIL_TEMPLATE_DIR: str = Field(default="templates/email", env="EMAIL_TEMPLATE_DIR")
    
    # Push notifications
    ENABLE_PUSH_NOTIFICATIONS: bool = Field(default=False, env="ENABLE_PUSH_NOTIFICATIONS")
    FIREBASE_CREDENTIALS_FILE: Optional[str] = Field(default=None, env="FIREBASE_CREDENTIALS_FILE")
    
    # SMS settings
    SMS_PROVIDER: Optional[str] = Field(default=None, env="SMS_PROVIDER")  # twilio, aws_sns
    SMS_API_KEY: Optional[str] = Field(default=None, env="SMS_API_KEY")
    SMS_API_SECRET: Optional[str] = Field(default=None, env="SMS_API_SECRET")
    
    # Notification preferences
    DEFAULT_NOTIFICATION_CHANNELS: List[str] = Field(
        default=["email"], 
        env="DEFAULT_NOTIFICATION_CHANNELS"
    )
    MAX_RETRY_ATTEMPTS: int = Field(default=3, env="NOTIFICATION_MAX_RETRY_ATTEMPTS")
    RETRY_DELAY_SECONDS: int = Field(default=60, env="NOTIFICATION_RETRY_DELAY")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


class APISettings(BaseSettings):
    """API configuration settings"""
    
    API_V1_PREFIX: str = Field(default="/api/v1", env="API_V1_PREFIX")
    API_VERSION: str = Field(default="1.0.0", env="API_VERSION")
    API_TITLE: str = Field(default="Hostel Management API", env="API_TITLE")
    API_DESCRIPTION: str = Field(default="Comprehensive hostel management system", env="API_DESCRIPTION")
    
    # Rate limiting
    ENABLE_RATE_LIMITING: bool = Field(default=True, env="ENABLE_RATE_LIMITING")
    DEFAULT_RATE_LIMIT: int = Field(default=100, env="DEFAULT_RATE_LIMIT")  # requests per minute
    ADMIN_API_RATE_LIMIT: int = Field(default=200, env="ADMIN_API_RATE_LIMIT")
    ADMIN_API_BURST_SIZE: int = Field(default=50, env="ADMIN_API_BURST_SIZE")
    
    # Request/Response settings
    MAX_REQUEST_SIZE: int = Field(default=10485760, env="MAX_REQUEST_SIZE")  # 10MB
    REQUEST_TIMEOUT: int = Field(default=30, env="REQUEST_TIMEOUT")
    
    # Features
    ENABLE_API_MONITORING: bool = Field(default=True, env="ENABLE_API_MONITORING")
    ENABLE_REQUEST_LOGGING: bool = Field(default=True, env="ENABLE_REQUEST_LOGGING")
    ENABLE_RESPONSE_COMPRESSION: bool = Field(default=True, env="ENABLE_RESPONSE_COMPRESSION")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


class BackgroundTaskSettings(BaseSettings):
    """Background task configuration"""
    
    TASK_BACKEND: str = Field(default="redis", env="TASK_BACKEND")  # redis, database, memory
    TASK_BROKER_URL: Optional[str] = Field(default=None, env="TASK_BROKER_URL")
    TASK_RESULT_BACKEND: Optional[str] = Field(default=None, env="TASK_RESULT_BACKEND")
    
    # Worker settings
    WORKER_CONCURRENCY: int = Field(default=4, env="WORKER_CONCURRENCY")
    TASK_TIMEOUT: int = Field(default=300, env="TASK_TIMEOUT")  # 5 minutes
    TASK_MAX_RETRIES: int = Field(default=3, env="TASK_MAX_RETRIES")
    
    # Queue settings
    DEFAULT_QUEUE: str = Field(default="default", env="DEFAULT_QUEUE")
    HIGH_PRIORITY_QUEUE: str = Field(default="high", env="HIGH_PRIORITY_QUEUE")
    LOW_PRIORITY_QUEUE: str = Field(default="low", env="LOW_PRIORITY_QUEUE")
    
    # Task scheduling
    ENABLE_PERIODIC_TASKS: bool = Field(default=True, env="ENABLE_PERIODIC_TASKS")
    TASK_CLEANUP_INTERVAL: int = Field(default=86400, env="TASK_CLEANUP_INTERVAL")  # 24 hours
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


class Settings(BaseSettings):
    """Main application settings"""
    
    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    TESTING: bool = Field(default=False, env="TESTING")
    
    # Project information
    PROJECT_NAME: str = Field(default="Hostel Management System", env="PROJECT_NAME")
    PROJECT_VERSION: str = Field(default="2.0.0", env="PROJECT_VERSION")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")
    
    # Include all sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    security: SecuritySettings = SecuritySettings()
    cache: CacheSettings = CacheSettings()
    logging: LoggingSettings = LoggingSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    notifications: NotificationSettings = NotificationSettings()
    api: APISettings = APISettings()
    tasks: BackgroundTaskSettings = BackgroundTaskSettings()
    
    # Feature flags
    ENABLE_ADMIN_PANEL: bool = Field(default=True, env="ENABLE_ADMIN_PANEL")
    ENABLE_GUEST_PORTAL: bool = Field(default=True, env="ENABLE_GUEST_PORTAL")
    ENABLE_MOBILE_API: bool = Field(default=True, env="ENABLE_MOBILE_API")
    ENABLE_WEBSOCKETS: bool = Field(default=False, env="ENABLE_WEBSOCKETS")
    
    # Maintenance
    MAINTENANCE_MODE: bool = Field(default=False, env="MAINTENANCE_MODE")
    MAINTENANCE_MESSAGE: str = Field(
        default="System under maintenance. Please try again later.",
        env="MAINTENANCE_MESSAGE"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }
        
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production', 'testing']
        if v not in valid_envs:
            raise ValueError(f'Environment must be one of {valid_envs}')
        return v
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()


# Global settings instance
settings = get_settings()

# Convenience aliases for frequently used settings
DATABASE_URL = settings.database.database_url
REDIS_URL = settings.redis.redis_url
SECRET_KEY = settings.security.SECRET_KEY
DEBUG = settings.DEBUG
ENVIRONMENT = settings.ENVIRONMENT