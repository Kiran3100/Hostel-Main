"""
Configuration package for the hostel management system.

This package contains all configuration modules for the application,
including environment settings, database connections, caching,
logging, security, and third-party integrations.
"""

from app.config.settings import settings
from app.config.database import get_db_session
from app.config.redis import get_redis_client
from app.config.security import SecurityConfig

__all__ = ['settings', 'get_db_session', 'get_redis_client', 'SecurityConfig']