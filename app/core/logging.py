"""
Logging Configuration and Utilities

Comprehensive logging system with structured logging, 
multiple handlers, and integration with external logging services.
"""

import sys
import json
import logging
import logging.handlers
from typing import Any, Dict, Optional, Union
from datetime import datetime
from pathlib import Path
from contextvars import ContextVar
from functools import wraps

import structlog
from pythonjsonlogger import jsonlogger

from .config import settings

# Context variables for request tracking
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class RequestContextProcessor:
    """Add request context to log records"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add request ID if available
        req_id = request_id.get()
        if req_id:
            event_dict['request_id'] = req_id
        
        # Add user ID if available
        uid = user_id.get()
        if uid:
            event_dict['user_id'] = uid
        
        # Add timestamp
        event_dict['timestamp'] = datetime.utcnow().isoformat()
        
        # Add service information
        event_dict['service'] = 'hostel-management'
        event_dict['environment'] = settings.ENVIRONMENT
        
        return event_dict


class SecurityLogProcessor:
    """Process security-related logs"""
    
    def __call__(self, logger, method_name, event_dict):
        # Mark security events
        if any(keyword in str(event_dict.get('event', '')).lower() 
               for keyword in ['auth', 'login', 'permission', 'security', 'override']):
            event_dict['security_event'] = True
        
        # Sanitize sensitive data
        self._sanitize_event_dict(event_dict)
        
        return event_dict
    
    def _sanitize_event_dict(self, event_dict: Dict[str, Any]):
        """Remove or mask sensitive information"""
        sensitive_keys = [
            'password', 'token', 'secret', 'key', 'credentials',
            'authorization', 'cookie', 'session'
        ]
        
        for key in list(event_dict.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                event_dict[key] = '[REDACTED]'
            elif isinstance(event_dict[key], dict):
                self._sanitize_event_dict(event_dict[key])


class PerformanceLogProcessor:
    """Add performance metrics to logs"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add performance data if available
        if 'execution_time' in event_dict:
            # Categorize performance
            exec_time = event_dict['execution_time']
            if exec_time > 5.0:
                event_dict['performance_category'] = 'slow'
            elif exec_time > 1.0:
                event_dict['performance_category'] = 'moderate'
            else:
                event_dict['performance_category'] = 'fast'
        
        return event_dict


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Add thread and process info
        log_record['thread'] = record.thread
        log_record['process'] = record.process
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


class DatabaseLogHandler(logging.Handler):
    """Custom handler to store logs in database"""
    
    def __init__(self, db_url: Optional[str] = None):
        super().__init__()
        self.db_url = db_url or settings.database.database_url
        self._connection = None
    
    def emit(self, record):
        """Emit a log record to database"""
        try:
            # Implementation would store logs in database
            # This is a placeholder for actual database logging
            pass
        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)


class ExternalLogHandler(logging.Handler):
    """Handler for external logging services"""
    
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        super().__init__()
        self.endpoint = endpoint
        self.api_key = api_key
        self.session = None
    
    def emit(self, record):
        """Send log record to external service"""
        try:
            # Implementation would send to external logging service
            # (e.g., Elasticsearch, Splunk, CloudWatch)
            pass
        except Exception:
            self.handleError(record)


class LoggingConfig:
    """Centralized logging configuration"""
    
    @staticmethod
    def configure_structured_logging():
        """Configure structured logging with structlog"""
        
        processors = [
            RequestContextProcessor(),
            SecurityLogProcessor(),
            PerformanceLogProcessor(),
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]
        
        if settings.logging.LOG_FORMAT == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.processors.KeyValueRenderer())
        
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )
    
    @staticmethod
    def configure_standard_logging():
        """Configure standard Python logging"""
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.logging.LOG_LEVEL))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.logging.LOG_LEVEL))
        
        if settings.logging.LOG_FORMAT == "json":
            formatter = CustomJsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler if specified
        if settings.logging.LOG_FILE:
            log_path = Path(settings.logging.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            if settings.logging.LOG_ROTATION == "size":
                file_handler = logging.handlers.RotatingFileHandler(
                    log_path,
                    maxBytes=10*1024*1024,  # 10MB
                    backupCount=5
                )
            else:
                file_handler = logging.handlers.TimedRotatingFileHandler(
                    log_path,
                    when='midnight',
                    interval=1,
                    backupCount=settings.logging.LOG_RETENTION
                )
            
            file_handler.setLevel(getattr(logging, settings.logging.LOG_LEVEL))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # Database handler if enabled
        # if settings.logging.ENABLE_DATABASE_LOGGING:
        #     db_handler = DatabaseLogHandler()
        #     db_handler.setLevel(logging.WARNING)  # Only warnings and errors
        #     root_logger.addHandler(db_handler)
        
        # External logging handler if enabled
        if (settings.logging.ENABLE_EXTERNAL_LOGGING and 
            settings.logging.EXTERNAL_LOG_ENDPOINT):
            external_handler = ExternalLogHandler(
                settings.logging.EXTERNAL_LOG_ENDPOINT
            )
            external_handler.setLevel(logging.ERROR)  # Only errors
            root_logger.addHandler(external_handler)
        
        # Configure specific loggers
        LoggingConfig._configure_library_loggers()
    
    @staticmethod
    def _configure_library_loggers():
        """Configure logging for external libraries"""
        
        # Reduce noise from external libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        
        # Database logging
        if settings.logging.LOG_SQL_QUERIES:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        else:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        
        # Redis logging
        logging.getLogger("redis").setLevel(logging.WARNING)
        
        # HTTP client logging
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


class LoggerAdapter:
    """Enhanced logger adapter with context management"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._context = {}
    
    def add_context(self, **kwargs):
        """Add context to all log messages"""
        self._context.update(kwargs)
        return self
    
    def remove_context(self, *keys):
        """Remove context keys"""
        for key in keys:
            self._context.pop(key, None)
        return self
    
    def clear_context(self):
        """Clear all context"""
        self._context.clear()
        return self
    
    def _log(self, level: int, message: str, *args, **kwargs):
        """Internal log method with context"""
        extra = kwargs.get('extra', {})
        extra.update(self._context)
        kwargs['extra'] = extra
        
        self.logger.log(level, message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        self._log(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self._log(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self._log(logging.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self._log(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        self._log(logging.CRITICAL, message, *args, **kwargs)


def get_logger(name: Optional[str] = None) -> LoggerAdapter:
    """
    Get configured logger instance.
    
    Args:
        name: Logger name (defaults to caller's module)
        
    Returns:
        Enhanced logger adapter
    """
    if name is None:
        import inspect
        frame = inspect.currentframe()
        caller_frame = frame.f_back
        name = caller_frame.f_globals.get('__name__', 'hostel')
    
    logger = logging.getLogger(name)
    return LoggerAdapter(logger)


def log_execution_time(logger_name: Optional[str] = None):
    """
    Decorator to log function execution time.
    
    Args:
        logger_name: Custom logger name
    """
    def decorator(func):
        logger = get_logger(logger_name or func.__module__)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(f"Function executed successfully", extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                })
                
                return result
                
            except Exception as e:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.error(f"Function execution failed", extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                })
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(f"Function executed successfully", extra={
                    'function': func.__name__,
                    'execution_time': execution_time
                })
                
                return result
                
            except Exception as e:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.error(f"Function execution failed", extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                })
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def setup_logging():
    """Initialize logging configuration"""
    try:
        if settings.logging.ENABLE_STRUCTURED_LOGGING:
            LoggingConfig.configure_structured_logging()
        
        LoggingConfig.configure_standard_logging()
        
        logger = get_logger(__name__)
        logger.info("Logging system initialized", extra={
            'log_level': settings.logging.LOG_LEVEL,
            'log_format': settings.logging.LOG_FORMAT,
            'structured_logging': settings.logging.ENABLE_STRUCTURED_LOGGING
        })
        
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        # Fallback to basic console logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


# Initialize logging when module is imported
setup_logging()

# Export main functions and classes
__all__ = [
    'get_logger',
    'setup_logging',
    'log_execution_time',
    'LoggerAdapter',
    'LoggingConfig',
    'request_id',
    'user_id'
]