"""
Core Module

This module provides essential infrastructure components for the hostel management system.
Includes configuration, security, caching, logging, and other foundational services.
"""

from .config import settings
from .exceptions import *
from .security import *
from .cache import *
from .logging import get_logger
from .background_tasks import *
from .notifications import *
from .monitoring import *
from .rate_limiting import *
from .database import *
from .validators import *
from .utils import *

__version__ = "2.0.0"
__author__ = "Hostel Management Team"

__all__ = [
    # Configuration
    "settings",
    
    # Exceptions
    "AdminAPIException",
    "AdminNotFoundError",
    "ValidationError",
    "PermissionError",
    "CacheError",
    
    # Security
    "PermissionValidator",
    "require_permission",
    "hash_password",
    "verify_password",
    
    # Cache
    "cache_result",
    "invalidate_cache",
    "cache_manager",
    
    # Logging
    "get_logger",
    
    # Background Tasks
    "enqueue_task",
    "background_task_manager",
    
    # Notifications
    "send_notification",
    "notification_manager",
    
    # Monitoring
    "track_api_performance",
    "monitor_manager",
    
    # Rate Limiting
    "rate_limit_middleware",
    "rate_limiter",
    
    # Database
    "get_db_session",
    "database_manager",
    
    # Validators
    "validate_email",
    "validate_phone",
    "validate_id",
    
    # Utils
    "generate_id",
    "format_datetime",
    "sanitize_input"
]