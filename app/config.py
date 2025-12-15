# app/config.py
from __future__ import annotations

import json
import logging
import secrets
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import (
    EmailStr,
    Field,
    field_validator,
    model_validator,
    SecretStr,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security import JWTSettings


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels."""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class SMSProvider(str, Enum):
    """Supported SMS providers."""
    TWILIO = "twilio"
    MSG91 = "msg91"
    TEXTLOCAL = "textlocal"
    AWS_SNS = "aws_sns"
    GUPSHUP = "gupshup"
    FAST2SMS = "fast2sms"


class EmailProvider(str, Enum):
    """Supported email providers."""
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    AWS_SES = "aws_ses"


class CacheBackend(str, Enum):
    """Supported cache backends."""
    REDIS = "redis"
    MEMCACHED = "memcached"
    MEMORY = "memory"


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # Main database
    DATABASE_URL: str = Field(default="sqlite:///./app.db")
    DATABASE_ECHO: bool = Field(default=False)
    
    # Connection pool settings
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)
    DATABASE_POOL_RECYCLE: int = Field(default=3600)
    
    # Connection retry settings
    DATABASE_RETRY_ATTEMPTS: int = Field(default=3)
    DATABASE_RETRY_DELAY: float = Field(default=1.0)
    
    # Read replica (optional)
    DATABASE_READ_URL: Optional[str] = Field(default=None)
    
    # Backup settings
    BACKUP_RETENTION_DAYS: int = Field(default=30)
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("Database URL cannot be empty")
        
        # Basic validation for common database types
        valid_schemes = ["postgresql", "mysql", "sqlite", "oracle", "mssql"]
        scheme = v.split("://")[0].split("+")[0] if "://" in v else ""
        
        if scheme not in valid_schemes:
            logging.warning(f"Unrecognized database scheme: {scheme}")
        
        return v
    
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return self.DATABASE_URL.startswith("sqlite")
    
    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL."""
        return "postgresql" in self.DATABASE_URL
    
    @property
    def is_mysql(self) -> bool:
        """Check if using MySQL."""
        return "mysql" in self.DATABASE_URL


class SecuritySettings(BaseSettings):
    """Security configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # JWT Settings
    JWT_SECRET_KEY: SecretStr = Field(default="CHANGE_ME_IN_PRODUCTION_min32chars")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)
    
    # Password settings
    PASSWORD_MIN_LENGTH: int = Field(default=8)
    PASSWORD_REQUIRE_UPPERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_LOWERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_NUMBERS: bool = Field(default=True)
    PASSWORD_REQUIRE_SPECIAL: bool = Field(default=True)
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_PER_HOUR: int = Field(default=1000)
    RATE_LIMIT_PER_DAY: int = Field(default=10000)
    
    # Account security
    MAX_LOGIN_ATTEMPTS: int = Field(default=5)
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = Field(default=30)
    
    # Session settings
    SESSION_TIMEOUT_MINUTES: int = Field(default=480)  # 8 hours
    REMEMBER_ME_DAYS: int = Field(default=30)
    
    # HTTPS settings
    FORCE_HTTPS: bool = Field(default=False)
    SECURE_COOKIES: bool = Field(default=False)
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(default_factory=list)
    
    # API Security
    API_KEY_HEADER: str = Field(default="X-API-Key")
    REQUIRE_API_KEY: bool = Field(default=False)
    
    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: SecretStr) -> SecretStr:
        """Validate JWT secret key."""
        secret = v.get_secret_value()
        if "CHANGE_ME" in secret:
            logging.warning("Using default JWT secret key - CHANGE THIS IN PRODUCTION!")
        
        if len(secret) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        
        return v
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Empty string
            if not v:
                return []
            # Try JSON parsing first
            if v.startswith('['):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Comma-separated
            return [i.strip() for i in v.split(",") if i.strip()]
        return []
    
    @property
    def jwt_settings(self) -> JWTSettings:
        """Build JWTSettings instance."""
        return JWTSettings(
            secret_key=self.JWT_SECRET_KEY.get_secret_value(),
            algorithm=self.JWT_ALGORITHM,
            access_token_expires_minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES,
            refresh_token_expires_days=self.REFRESH_TOKEN_EXPIRE_DAYS,
        )


class EmailSettings(BaseSettings):
    """Email configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # Provider settings
    EMAIL_PROVIDER: EmailProvider = Field(default=EmailProvider.SMTP)
    
    # SMTP settings
    SMTP_HOST: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str = Field(default="")
    SMTP_PASSWORD: SecretStr = Field(default="")
    SMTP_USE_TLS: bool = Field(default=True)
    SMTP_USE_SSL: bool = Field(default=False)
    
    # Email settings
    FROM_EMAIL: EmailStr = Field(default="noreply@example.com")
    FROM_NAME: str = Field(default="Hostel Management")
    
    # SendGrid
    SENDGRID_API_KEY: SecretStr = Field(default="")
    
    # Mailgun
    MAILGUN_API_KEY: SecretStr = Field(default="")
    MAILGUN_DOMAIN: str = Field(default="")
    
    # AWS SES
    AWS_ACCESS_KEY_ID: str = Field(default="")
    AWS_SECRET_ACCESS_KEY: SecretStr = Field(default="")
    AWS_REGION: str = Field(default="us-east-1")
    
    # Email limits
    EMAIL_RATE_LIMIT_PER_HOUR: int = Field(default=100)
    EMAIL_BATCH_SIZE: int = Field(default=50)
    
    # Templates
    EMAIL_TEMPLATE_DIR: str = Field(default="templates/email")
    
    @model_validator(mode="after")
    def validate_email_config(self):
        """Validate email configuration based on provider."""
        provider = self.EMAIL_PROVIDER
        
        if provider == EmailProvider.SMTP:
            if not self.SMTP_HOST or not self.SMTP_PORT:
                logging.warning("SMTP_HOST and SMTP_PORT should be configured for SMTP provider")
        
        elif provider == EmailProvider.SENDGRID:
            if not self.SENDGRID_API_KEY or not self.SENDGRID_API_KEY.get_secret_value():
                logging.warning("SENDGRID_API_KEY should be configured for SendGrid provider")
        
        elif provider == EmailProvider.MAILGUN:
            if not self.MAILGUN_API_KEY or not self.MAILGUN_DOMAIN:
                logging.warning("MAILGUN_API_KEY and MAILGUN_DOMAIN should be configured for Mailgun provider")
        
        return self


class SMSSettings(BaseSettings):
    """SMS configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # Provider settings
    SMS_PROVIDER: SMSProvider = Field(default=SMSProvider.TWILIO)
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = Field(default="")
    TWILIO_AUTH_TOKEN: SecretStr = Field(default="")
    TWILIO_FROM_NUMBER: str = Field(default="")
    
    # MSG91
    MSG91_API_KEY: SecretStr = Field(default="")
    MSG91_SENDER_ID: str = Field(default="")
    
    # TextLocal
    TEXTLOCAL_API_KEY: SecretStr = Field(default="")
    TEXTLOCAL_SENDER: str = Field(default="")
    
    # SMS limits
    SMS_RATE_LIMIT_PER_MINUTE: int = Field(default=100)
    SMS_RATE_LIMIT_PER_HOUR: int = Field(default=1000)
    SMS_RATE_LIMIT_PER_DAY: int = Field(default=10000)
    
    # Retry settings
    SMS_RETRY_ATTEMPTS: int = Field(default=3)
    SMS_RETRY_DELAY: float = Field(default=1.0)
    SMS_TIMEOUT: int = Field(default=30)
    
    @model_validator(mode="after")
    def validate_sms_config(self):
        """Validate SMS configuration based on provider."""
        provider = self.SMS_PROVIDER
        
        if provider == SMSProvider.TWILIO:
            if not self.TWILIO_ACCOUNT_SID or not self.TWILIO_AUTH_TOKEN:
                logging.warning("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN should be configured for Twilio provider")
        
        elif provider == SMSProvider.MSG91:
            if not self.MSG91_API_KEY:
                logging.warning("MSG91_API_KEY should be configured for MSG91 provider")
        
        elif provider == SMSProvider.TEXTLOCAL:
            if not self.TEXTLOCAL_API_KEY:
                logging.warning("TEXTLOCAL_API_KEY should be configured for TextLocal provider")
        
        return self


class FileStorageSettings(BaseSettings):
    """File storage configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # Local storage
    UPLOAD_DIR: str = Field(default="uploads")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024)  # 10MB
    ALLOWED_FILE_EXTENSIONS: Set[str] = Field(
        default_factory=lambda: {".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx"}
    )
    
    # AWS S3
    AWS_S3_BUCKET: str = Field(default="")
    AWS_S3_REGION: str = Field(default="us-east-1")
    AWS_S3_ACCESS_KEY: str = Field(default="")
    AWS_S3_SECRET_KEY: SecretStr = Field(default="")
    AWS_S3_CUSTOM_DOMAIN: Optional[str] = Field(default=None)
    
    # File processing
    IMAGE_MAX_WIDTH: int = Field(default=1920)
    IMAGE_MAX_HEIGHT: int = Field(default=1080)
    IMAGE_QUALITY: int = Field(default=85)
    
    @field_validator("ALLOWED_FILE_EXTENSIONS", mode="before")
    @classmethod
    def parse_file_extensions(cls, v):
        """Parse file extensions from string or set."""
        if isinstance(v, set):
            return v
        if isinstance(v, list):
            return set(v)
        if isinstance(v, str):
            # Empty string
            if not v:
                return {".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx"}
            # Try JSON parsing first
            if v.startswith('[') or v.startswith('{'):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, (list, set)):
                        return set(parsed)
                except json.JSONDecodeError:
                    pass
            # Comma-separated
            return {ext.strip() for ext in v.split(",") if ext.strip()}
        return {".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx"}


class CacheSettings(BaseSettings):
    """Cache configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    CACHE_BACKEND: CacheBackend = Field(default=CacheBackend.MEMORY)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: SecretStr = Field(default="")
    REDIS_DB: int = Field(default=0)
    REDIS_MAX_CONNECTIONS: int = Field(default=20)
    
    # Memcached
    MEMCACHED_SERVERS: List[str] = Field(
        default_factory=lambda: ["127.0.0.1:11211"]
    )
    
    # Cache TTL (seconds)
    CACHE_DEFAULT_TTL: int = Field(default=300)  # 5 minutes
    CACHE_USER_TTL: int = Field(default=900)  # 15 minutes
    CACHE_SETTINGS_TTL: int = Field(default=3600)  # 1 hour
    
    @field_validator("MEMCACHED_SERVERS", mode="before")
    @classmethod
    def parse_memcached_servers(cls, v):
        """Parse MEMCACHED_SERVERS from various formats."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Empty string
            if not v:
                return ["127.0.0.1:11211"]
            # Try JSON parsing first
            if v.startswith('['):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Comma-separated
            if ',' in v:
                return [x.strip() for x in v.split(',') if x.strip()]
            # Single value
            return [v]
        return ["127.0.0.1:11211"]


class MonitoringSettings(BaseSettings):
    """Monitoring and logging configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # Logging
    LOG_LEVEL: LogLevel = Field(default=LogLevel.INFO)
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    LOG_FILE: Optional[str] = Field(default=None)
    LOG_ROTATION: str = Field(default="midnight")
    LOG_RETENTION: int = Field(default=30)  # days
    
    # Sentry
    SENTRY_DSN: Optional[str] = Field(default=None)
    SENTRY_ENVIRONMENT: Optional[str] = Field(default=None)
    SENTRY_RELEASE: Optional[str] = Field(default=None)
    
    # Metrics
    ENABLE_METRICS: bool = Field(default=True)
    METRICS_PORT: int = Field(default=9090)
    
    # Health checks
    HEALTH_CHECK_ENABLED: bool = Field(default=True)
    HEALTH_CHECK_TIMEOUT: int = Field(default=30)


class PaymentSettings(BaseSettings):
    """Payment gateway configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # Razorpay (popular in India)
    RAZORPAY_KEY_ID: str = Field(default="")
    RAZORPAY_KEY_SECRET: SecretStr = Field(default="")
    RAZORPAY_WEBHOOK_SECRET: SecretStr = Field(default="")
    
    # Stripe
    STRIPE_PUBLISHABLE_KEY: str = Field(default="")
    STRIPE_SECRET_KEY: SecretStr = Field(default="")
    STRIPE_WEBHOOK_SECRET: SecretStr = Field(default="")
    
    # PayPal
    PAYPAL_CLIENT_ID: str = Field(default="")
    PAYPAL_CLIENT_SECRET: SecretStr = Field(default="")
    PAYPAL_MODE: str = Field(default="sandbox")  # sandbox or live
    
    # Payment settings
    CURRENCY: str = Field(default="INR")
    PAYMENT_TIMEOUT_MINUTES: int = Field(default=15)


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    # ------------------------------------------------------------------ #
    # General
    # ------------------------------------------------------------------ #
    PROJECT_NAME: str = Field(default="Hostel Management SaaS API")
    PROJECT_VERSION: str = Field(default="1.0.0")
    PROJECT_DESCRIPTION: str = Field(
        default="Complete hostel management solution with booking, payments, and analytics"
    )
    
    ENVIRONMENT: Environment = Field(default=Environment.DEVELOPMENT)
    DEBUG: bool = Field(default=False)
    
    # API settings
    API_V1_STR: str = Field(default="/api/v1")
    API_DOCS_URL: Optional[str] = Field(default="/docs")
    API_REDOC_URL: Optional[str] = Field(default="/redoc")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    WORKERS: int = Field(default=1)
    
    # Timezone
    TIMEZONE: str = Field(default="Asia/Kolkata")
    
    # ------------------------------------------------------------------ #
    # Sub-configurations
    # ------------------------------------------------------------------ #
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    sms: SMSSettings = Field(default_factory=SMSSettings)
    storage: FileStorageSettings = Field(default_factory=FileStorageSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    
    # ------------------------------------------------------------------ #
    # Feature Flags
    # ------------------------------------------------------------------ #
    FEATURE_REGISTRATION: bool = Field(default=True)
    FEATURE_EMAIL_VERIFICATION: bool = Field(default=True)
    FEATURE_SMS_VERIFICATION: bool = Field(default=True)
    FEATURE_PAYMENTS: bool = Field(default=True)
    FEATURE_ANALYTICS: bool = Field(default=True)
    FEATURE_NOTIFICATIONS: bool = Field(default=True)
    
    # ------------------------------------------------------------------ #
    # Business Logic
    # ------------------------------------------------------------------ #
    # Booking settings
    BOOKING_ADVANCE_DAYS: int = Field(default=365)
    BOOKING_CANCELLATION_HOURS: int = Field(default=24)
    BOOKING_MODIFICATION_HOURS: int = Field(default=2)
    
    # Payment settings
    ADVANCE_PAYMENT_PERCENTAGE: int = Field(default=20)
    LATE_PAYMENT_PENALTY_PERCENTAGE: int = Field(default=5)
    
    # Notification settings
    NOTIFICATION_REMINDER_HOURS: List[int] = Field(
        default_factory=lambda: [72, 24, 2]
    )
    
    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment."""
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    @field_validator("DEBUG")
    @classmethod
    def validate_debug(cls, v, info):
        """Debug should be False in production."""
        env = info.data.get("ENVIRONMENT")
        if env == Environment.PRODUCTION and v:
            logging.warning("Debug mode is enabled in production environment!")
        return v
    
    @field_validator("NOTIFICATION_REMINDER_HOURS", mode="before")
    @classmethod
    def parse_reminder_hours(cls, v):
        """Parse NOTIFICATION_REMINDER_HOURS from various formats."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Empty string
            if not v:
                return [72, 24, 2]
            # Try JSON parsing first
            if v.startswith('['):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [int(x) for x in parsed]
                except (json.JSONDecodeError, ValueError):
                    pass
            # Comma-separated
            if ',' in v:
                try:
                    return [int(x.strip()) for x in v.split(',') if x.strip()]
                except ValueError:
                    pass
            # Single value
            try:
                return [int(v)]
            except ValueError:
                pass
        # Return default if all parsing fails
        return [72, 24, 2]
    
    @model_validator(mode="after")
    def validate_production_settings(self):
        """Validate production-specific settings."""
        if self.ENVIRONMENT == Environment.PRODUCTION:
            # Check critical production settings
            if isinstance(self.security, SecuritySettings):
                jwt_secret = self.security.JWT_SECRET_KEY.get_secret_value()
                if "CHANGE_ME" in jwt_secret:
                    logging.warning("JWT secret should be changed in production")
                
                if not self.security.FORCE_HTTPS:
                    logging.warning("HTTPS is not enforced in production")
                
                if not self.security.SECURE_COOKIES:
                    logging.warning("Secure cookies are not enabled in production")
        
        return self
    
    # ------------------------------------------------------------------ #
    # Backward Compatibility Properties
    # ------------------------------------------------------------------ #
    @property
    def DATABASE_URL(self) -> str:
        """Backward compatibility for DATABASE_URL."""
        return self.database.DATABASE_URL
    
    @property
    def JWT_SECRET_KEY(self) -> str:
        """Backward compatibility for JWT_SECRET_KEY."""
        return self.security.JWT_SECRET_KEY.get_secret_value()
    
    @property
    def JWT_ALGORITHM(self) -> str:
        """Backward compatibility for JWT_ALGORITHM."""
        return self.security.JWT_ALGORITHM
    
    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        """Backward compatibility for ACCESS_TOKEN_EXPIRE_MINUTES."""
        return self.security.ACCESS_TOKEN_EXPIRE_MINUTES
    
    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        """Backward compatibility for REFRESH_TOKEN_EXPIRE_DAYS."""
        return self.security.REFRESH_TOKEN_EXPIRE_DAYS
    
    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        """Backward compatibility for BACKEND_CORS_ORIGINS."""
        return self.security.BACKEND_CORS_ORIGINS
    
    @property
    def jwt_settings(self) -> JWTSettings:
        """Backward compatibility for jwt_settings."""
        return self.security.jwt_settings
    
    # ------------------------------------------------------------------ #
    # Utility Methods
    # ------------------------------------------------------------------ #
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == Environment.DEVELOPMENT
    
    def is_testing(self) -> bool:
        """Check if running in testing."""
        return self.ENVIRONMENT == Environment.TESTING
    
    def get_database_url(self, read_replica: bool = False) -> str:
        """Get database URL (with optional read replica)."""
        if read_replica and self.database.DATABASE_READ_URL:
            return self.database.DATABASE_READ_URL
        return self.database.DATABASE_URL
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins based on environment."""
        if self.is_development():
            base_origins = self.security.BACKEND_CORS_ORIGINS or []
            dev_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
            ]
            return base_origins + dev_origins
        return self.security.BACKEND_CORS_ORIGINS


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance.
    
    The @lru_cache decorator ensures this function is only called once,
    and the same Settings instance is returned on subsequent calls.
    """
    try:
        settings = Settings()
        
        # Log configuration summary
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Application starting with environment: {settings.ENVIRONMENT.value}")
        logging.info(f"Debug mode: {settings.DEBUG}")
        db_display = settings.database.DATABASE_URL.split('@')[-1] if '@' in settings.database.DATABASE_URL else 'Local'
        logging.info(f"Database: {db_display}")
        
        return settings
        
    except Exception as e:
        logging.error(f"Failed to load settings: {e}")
        raise


def get_test_settings() -> Settings:
    """Get settings for testing (not cached)."""
    return Settings(
        ENVIRONMENT=Environment.TESTING,
        DEBUG=True,
        database=DatabaseSettings(
            DATABASE_URL="sqlite:///./test.db",
            DATABASE_ECHO=False
        ),
        security=SecuritySettings(
            JWT_SECRET_KEY=SecretStr("test-secret-key-32-chars-minimum-length"),
            ACCESS_TOKEN_EXPIRE_MINUTES=15
        ),
    )


# Global settings instance
settings: Settings = get_settings()


# Configuration validation on import
def validate_configuration() -> None:
    """Validate configuration on application startup."""
    try:
        settings = get_settings()
        
        # Check required directories exist
        upload_dir = Path(settings.storage.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate critical settings in production
        if settings.is_production():
            critical_checks = [
                (
                    "CHANGE_ME" not in settings.security.JWT_SECRET_KEY.get_secret_value(),
                    "JWT secret must be changed"
                ),
                (
                    settings.database.DATABASE_URL != "sqlite:///./app.db",
                    "Production database should not be SQLite"
                ),
                (
                    settings.security.FORCE_HTTPS,
                    "HTTPS should be enforced in production"
                ),
                (
                    settings.monitoring.SENTRY_DSN is not None,
                    "Sentry should be configured in production"
                ),
            ]
            
            for check, message in critical_checks:
                if not check:
                    logging.warning(f"Production configuration warning: {message}")
        
        logging.info("Configuration validation completed successfully")
        
    except Exception as e:
        logging.error(f"Configuration validation failed: {e}")
        raise


# Validate configuration on import
if __name__ != "__main__":
    validate_configuration()