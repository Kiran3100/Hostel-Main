"""
Logging configuration for the hostel management system.
Provides structured logging with different handlers and formatters.
"""

import os
import json
import logging
import logging.config
from typing import Dict, Any
from pythonjsonlogger import jsonlogger
from datetime import datetime

from app.config.settings import settings

# Default log directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """Add custom fields to the log record"""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp with ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add environment
        log_record['environment'] = settings.ENVIRONMENT
        
        # Add correlation ID if available in record
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
        
        # Add request information if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
            
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
            
        if hasattr(record, 'tenant_id'):
            log_record['tenant_id'] = record.tenant_id
            
        if hasattr(record, 'ip_address'):
            log_record['ip_address'] = record.ip_address
        
        # Add exception info if available
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }

# Create logging config dictionary
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'json': {
            '()': CustomJsonFormatter,
            'format': '%(timestamp)s %(level)s %(logger)s %(message)s'
        },
        'colored': {
            '()': 'colorlog.ColoredFormatter',
            'format': '%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'log_colors': {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if settings.DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'colored' if settings.is_development() else 'standard'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'standard',
            'encoding': 'utf8'
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'error.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'standard',
            'encoding': 'utf8'
        },
        'json_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'app.json.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'json',
            'encoding': 'utf8'
        }
    },
    'loggers': {
        '': {  # Root logger
            'handlers': ['console', 'file', 'error_file', 'json_file'],
            'level': settings.LOG_LEVEL,
            'propagate': True
        },
        'app': {  # Application logger
            'handlers': ['console', 'file', 'error_file', 'json_file'],
            'level': settings.LOG_LEVEL,
            'propagate': False
        },
        'sqlalchemy.engine': {  # SQL query logger
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False
        },
        'uvicorn': {  # Uvicorn logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        },
        'uvicorn.access': {  # Uvicorn access logger
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

# If Sentry integration is enabled
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    # Set up Sentry integration
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # Log INFO and above to Sentry
        event_level=logging.ERROR  # Send errors as events
    )
    
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[sentry_logging],
        traces_sample_rate=0.2,
        send_default_pii=False
    )

def setup_logging():
    """Configure application logging"""
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger("app")
    logger.info(f"Logging initialized with level: {settings.LOG_LEVEL}")
    return logger

# Create a function to get a logger with context
def get_logger(name: str):
    """Get logger with context"""
    return logging.getLogger(name)

class LoggingContext:
    """Context manager for adding extra fields to logs"""
    
    def __init__(self, logger, **extra):
        self.logger = logger
        self.extra = extra
        self._old_context = {}
    
    def __enter__(self):
        # Save old context
        for key, value in self.extra.items():
            if hasattr(self.logger, key):
                self._old_context[key] = getattr(self.logger, key)
            setattr(self.logger, key, value)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old context
        for key in self.extra:
            if key in self._old_context:
                setattr(self.logger, key, self._old_context[key])
            else:
                delattr(self.logger, key)

# Log aggregation and search class
class LogAggregator:
    """Aggregate and search logs"""
    
    def __init__(self, log_dir: str = LOG_DIR):
        self.log_dir = log_dir
    
    def search_logs(self, query: str, log_level: str = None, start_date: str = None, 
                    end_date: str = None, limit: int = 100) -> list:
        """Search logs with filters"""
        results = []
        
        # Get json log file for structured searching
        json_log_path = os.path.join(self.log_dir, 'app.json.log')
        if not os.path.exists(json_log_path):
            return results
        
        with open(json_log_path, 'r') as log_file:
            for line in log_file:
                try:
                    log_entry = json.loads(line.strip())
                    
                    # Apply filters
                    if log_level and log_entry.get('level') != log_level:
                        continue
                    
                    if start_date and log_entry.get('timestamp', '') < start_date:
                        continue
                    
                    if end_date and log_entry.get('timestamp', '') > end_date:
                        continue
                    
                    # Check if query matches any field
                    if query and not any(query.lower() in str(v).lower() for v in log_entry.values()):
                        continue
                    
                    results.append(log_entry)
                    if len(results) >= limit:
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        return results
    
    def get_error_summary(self, days: int = 1) -> Dict[str, Any]:
        """Get summary of recent errors"""
        error_counts = {}
        total_errors = 0
        
        json_log_path = os.path.join(self.log_dir, 'app.json.log')
        if not os.path.exists(json_log_path):
            return {"total": 0, "errors": {}}
        
        # Calculate cutoff timestamp
        import time
        from datetime import datetime, timedelta
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        with open(json_log_path, 'r') as log_file:
            for line in log_file:
                try:
                    log_entry = json.loads(line.strip())
                    
                    # Only process error entries
                    if log_entry.get('level') not in ['ERROR', 'CRITICAL']:
                        continue
                    
                    # Check date
                    if log_entry.get('timestamp', '') < cutoff_date:
                        continue
                    
                    # Get error type
                    error_type = 'Unknown'
                    if 'exception' in log_entry:
                        error_type = log_entry['exception'].get('type', 'Unknown')
                    
                    # Count error
                    if error_type not in error_counts:
                        error_counts[error_type] = 0
                    error_counts[error_type] += 1
                    total_errors += 1
                        
                except json.JSONDecodeError:
                    continue
        
        return {
            "total": total_errors,
            "errors": error_counts
        }