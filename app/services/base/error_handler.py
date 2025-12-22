# error_handler.py

from typing import Dict, List, Any, Optional, Type, Callable, Union
from dataclasses import dataclass
from datetime import datetime
import logging
import traceback
import sys
import json
from enum import Enum
import asyncio
from contextlib import contextmanager

class ErrorSeverity(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3
    FATAL = 4

class ErrorCategory(Enum):
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    DATABASE = "database"
    INTEGRATION = "integration"
    NETWORK = "network"
    SYSTEM = "system"
    UNKNOWN = "unknown"

@dataclass
class ErrorContext:
    """Context information for error handling"""
    error_id: str
    timestamp: datetime
    service: str
    operation: str
    user_id: Optional[str]
    trace_id: Optional[str]
    correlation_id: Optional[str]
    metadata: Dict[str, Any]

    @classmethod
    def create(
        cls,
        service: str,
        operation: str,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> 'ErrorContext':
        from uuid import uuid4
        return cls(
            error_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            service=service,
            operation=operation,
            user_id=user_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
            metadata={}
        )

@dataclass
class ErrorDetails:
    """Detailed error information"""
    message: str
    code: str
    category: ErrorCategory
    severity: ErrorSeverity
    stack_trace: Optional[str]
    cause: Optional[Exception]
    context: ErrorContext
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'error_id': self.context.error_id,
            'timestamp': self.context.timestamp.isoformat(),
            'message': self.message,
            'code': self.code,
            'category': self.category.value,
            'severity': self.severity.value,
            'service': self.context.service,
            'operation': self.context.operation,
            'user_id': self.context.user_id,
            'trace_id': self.context.trace_id,
            'correlation_id': self.context.correlation_id,
            'stack_trace': self.stack_trace,
            'metadata': {**self.context.metadata, **self.metadata}
        }

class ExceptionMapper:
    """Maps exceptions to error categories and severities"""
    
    def __init__(self):
        self._mappings: Dict[Type[Exception], tuple[ErrorCategory, ErrorSeverity]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_mapping(
        self,
        exception_type: Type[Exception],
        category: ErrorCategory,
        severity: ErrorSeverity
    ) -> None:
        """Add exception mapping"""
        self._mappings[exception_type] = (category, severity)
        self.logger.info(
            f"Added mapping for {exception_type.__name__}: "
            f"{category.value}/{severity.value}"
        )

    def get_mapping(
        self,
        exception: Exception
    ) -> tuple[ErrorCategory, ErrorSeverity]:
        """Get mapping for exception"""
        for exc_type, mapping in self._mappings.items():
            if isinstance(exception, exc_type):
                return mapping
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM

class ErrorLogger:
    """Handles error logging and persistence"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._handlers: List[Callable] = []

    def add_handler(self, handler: Callable) -> None:
        """Add error handler"""
        self._handlers.append(handler)
        self.logger.info(f"Added error handler: {handler.__name__}")

    async def log_error(self, error: ErrorDetails) -> None:
        """Log error details"""
        # Log to system logger
        log_level = self._get_log_level(error.severity)
        self.logger.log(
            log_level,
            f"Error {error.context.error_id}: {error.message}",
            extra=error.to_dict()
        )

        # Execute handlers
        for handler in self._handlers:
            try:
                await handler(error)
            except Exception as e:
                self.logger.error(f"Error handler failed: {str(e)}")

    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Map severity to log level"""
        return {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.FATAL: logging.CRITICAL
        }.get(severity, logging.ERROR)

class ErrorRecovery:
    """Handles error recovery strategies"""
    
    def __init__(self):
        self._strategies: Dict[ErrorCategory, List[Callable]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_strategy(
        self,
        category: ErrorCategory,
        strategy: Callable
    ) -> None:
        """Add recovery strategy"""
        if category not in self._strategies:
            self._strategies[category] = []
        self._strategies[category].append(strategy)
        self.logger.info(
            f"Added recovery strategy for {category.value}: {strategy.__name__}"
        )

    async def attempt_recovery(
        self,
        error: ErrorDetails
    ) -> bool:
        """Attempt to recover from error"""
        strategies = self._strategies.get(error.category, [])
        
        for strategy in strategies:
            try:
                if await strategy(error):
                    self.logger.info(
                        f"Recovery successful for {error.context.error_id}"
                    )
                    return True
            except Exception as e:
                self.logger.error(
                    f"Recovery strategy failed: {str(e)}"
                )
        
        return False

class ErrorReporter:
    """Generates error reports and notifications"""
    
    def __init__(self):
        self._notifiers: List[Callable] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_notifier(self, notifier: Callable) -> None:
        """Add error notifier"""
        self._notifiers.append(notifier)
        self.logger.info(f"Added error notifier: {notifier.__name__}")

    async def report_error(self, error: ErrorDetails) -> None:
        """Report error to configured notifiers"""
        if error.severity >= ErrorSeverity.HIGH:
            for notifier in self._notifiers:
                try:
                    await notifier(error)
                except Exception as e:
                    self.logger.error(
                        f"Error notification failed: {str(e)}"
                    )

class FallbackHandler:
    """Handles fallback operations for critical failures"""
    
    def __init__(self):
        self._fallbacks: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_fallback(
        self,
        operation: str,
        fallback: Callable
    ) -> None:
        """Register fallback operation"""
        self._fallbacks[operation] = fallback
        self.logger.info(f"Registered fallback for {operation}")

    async def execute_fallback(
        self,
        operation: str,
        error: ErrorDetails,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute fallback operation"""
        fallback = self._fallbacks.get(operation)
        if not fallback:
            self.logger.warning(f"No fallback for {operation}")
            return None

        try:
            result = await fallback(error, *args, **kwargs)
            self.logger.info(
                f"Fallback executed for {operation}"
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Fallback execution failed: {str(e)}"
            )
            return None

class ErrorHandler:
    """Main error handling interface"""
    
    def __init__(self):
        self.mapper = ExceptionMapper()
        self.logger = ErrorLogger()
        self.recovery = ErrorRecovery()
        self.reporter = ErrorReporter()
        self.fallback = FallbackHandler()
        self._service_logger = logging.getLogger(self.__class__.__name__)

    def configure(self) -> None:
        """Configure default error handling"""
        # Add default exception mappings
        self.mapper.add_mapping(
            ValueError,
            ErrorCategory.VALIDATION,
            ErrorSeverity.LOW
        )
        self.mapper.add_mapping(
            PermissionError,
            ErrorCategory.AUTHORIZATION,
            ErrorSeverity.MEDIUM
        )
        self.mapper.add_mapping(
            ConnectionError,
            ErrorCategory.NETWORK,
            ErrorSeverity.HIGH
        )

    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext
    ) -> ErrorDetails:
        """Handle an error"""
        try:
            # Map error
            category, severity = self.mapper.get_mapping(error)
            
            # Create error details
            details = ErrorDetails(
                message=str(error),
                code=error.__class__.__name__,
                category=category,
                severity=severity,
                stack_trace=traceback.format_exc(),
                cause=error.__cause__,
                context=context,
                metadata={}
            )

            # Log error
            await self.logger.log_error(details)

            # Attempt recovery
            if await self.recovery.attempt_recovery(details):
                details.metadata['recovered'] = True
            
            # Report if necessary
            await self.reporter.report_error(details)

            return details
        except Exception as e:
            self._service_logger.error(
                f"Error handling failed: {str(e)}"
            )
            raise

    @contextmanager
    async def error_context(
        self,
        service: str,
        operation: str,
        **kwargs: Any
    ):
        """Context manager for error handling"""
        context = ErrorContext.create(service, operation, **kwargs)
        try:
            yield context
        except Exception as e:
            error_details = await self.handle_error(e, context)
            
            # Execute fallback if available
            await self.fallback.execute_fallback(
                operation,
                error_details
            )
            raise

    async def handle_errors(
        self,
        service: str,
        operation: str
    ):
        """Decorator for error handling"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                async with self.error_context(service, operation, **kwargs):
                    return await func(*args, **kwargs)
            return wrapper
        return decorator

    def add_error_mapping(
        self,
        exception_type: Type[Exception],
        category: ErrorCategory,
        severity: ErrorSeverity
    ) -> None:
        """Add custom error mapping"""
        self.mapper.add_mapping(exception_type, category, severity)

    def add_recovery_strategy(
        self,
        category: ErrorCategory,
        strategy: Callable
    ) -> None:
        """Add custom recovery strategy"""
        self.recovery.add_strategy(category, strategy)

    def add_error_notifier(self, notifier: Callable) -> None:
        """Add custom error notifier"""
        self.reporter.add_notifier(notifier)

    def add_fallback(
        self,
        operation: str,
        fallback: Callable
    ) -> None:
        """Add custom fallback operation"""
        self.fallback.register_fallback(operation, fallback)

    async def get_error_stats(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Get error statistics"""
        # Implement error statistics collection
        return {}

    async def cleanup_errors(
        self,
        older_than: datetime
    ) -> None:
        """Clean up old error logs"""
        # Implement error log cleanup
        pass