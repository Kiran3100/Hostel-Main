import asyncio
import time
import inspect
from typing import Dict, List, Any, Callable, Optional, Type, get_type_hints
from dataclasses import dataclass
from abc import ABC, abstractmethod
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class EventHandlerRegistry:
    """Event handler registration and management"""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = {}
        self.handler_metadata: Dict[str, Dict] = {}
        self.middleware: List[Callable] = []
    
    def register(
        self,
        event_type: str,
        handler: Callable,
        priority: int = 0,
        condition: Optional[Callable] = None,
        retry_policy: Optional[Dict] = None
    ):
        """Register event handler"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        # Store handler with metadata
        handler_id = f"{handler.__module__}.{handler.__name__}"
        
        self.handlers[event_type].append(handler)
        self.handler_metadata[handler_id] = {
            "event_type": event_type,
            "priority": priority,
            "condition": condition,
            "retry_policy": retry_policy or {"max_retries": 3, "delay": 1.0},
            "registered_at": time.time(),
            "execution_count": 0,
            "failure_count": 0,
            "last_execution": None,
            "average_duration": 0.0
        }
        
        # Sort handlers by priority
        self.handlers[event_type].sort(
            key=lambda h: self.handler_metadata.get(
                f"{h.__module__}.{h.__name__}", {}
            ).get("priority", 0),
            reverse=True
        )
        
        logger.info(f"Registered handler {handler_id} for event {event_type}")
    
    def unregister(self, event_type: str, handler: Callable):
        """Unregister event handler"""
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            
            handler_id = f"{handler.__module__}.{handler.__name__}"
            if handler_id in self.handler_metadata:
                del self.handler_metadata[handler_id]
            
            logger.info(f"Unregistered handler {handler_id} for event {event_type}")
    
    def get_handlers(self, event_type: str) -> List[Callable]:
        """Get handlers for event type"""
        return self.handlers.get(event_type, [])
    
    def add_middleware(self, middleware: Callable):
        """Add middleware for handler execution"""
        self.middleware.append(middleware)
        logger.info(f"Added handler middleware: {middleware.__name__}")
    
    async def execute_handlers(self, event: Any, event_metadata: Optional[Dict] = None):
        """Execute all handlers for event"""
        event_type = event.__class__.__name__
        handlers = self.get_handlers(event_type)
        
        if not handlers:
            logger.debug(f"No handlers registered for event: {event_type}")
            return
        
        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(
                self._execute_handler_with_middleware(handler, event, event_metadata)
            )
            tasks.append(task)
        
        # Wait for all handlers with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler = handlers[i]
                handler_id = f"{handler.__module__}.{handler.__name__}"
                logger.error(f"Handler {handler_id} failed: {str(result)}")
                
                # Update failure metrics
                if handler_id in self.handler_metadata:
                    self.handler_metadata[handler_id]["failure_count"] += 1
    
    async def _execute_handler_with_middleware(
        self, handler: Callable, event: Any, event_metadata: Optional[Dict]
    ):
        """Execute handler with middleware chain"""
        # Apply middleware chain
        for middleware in self.middleware:
            try:
                # Middleware can modify the event or stop execution
                if asyncio.iscoroutinefunction(middleware):
                    result = await middleware(event, handler, event_metadata)
                else:
                    result = middleware(event, handler, event_metadata)
                
                # If middleware returns False, stop execution
                if result is False:
                    return
                
                # If middleware returns modified event, use it
                if result is not None and result is not True:
                    event = result
                    
            except Exception as e:
                logger.error(f"Middleware {middleware.__name__} failed: {str(e)}")
        
        # Execute the handler
        await self._execute_handler(handler, event, event_metadata)
    
    async def _execute_handler(
        self, handler: Callable, event: Any, event_metadata: Optional[Dict]
    ):
        """Execute individual handler with metrics tracking"""
        handler_id = f"{handler.__module__}.{handler.__name__}"
        metadata = self.handler_metadata.get(handler_id, {})
        
        # Check condition if specified
        condition = metadata.get("condition")
        if condition and not condition(event, event_metadata):
            logger.debug(f"Handler {handler_id} condition not met")
            return
        
        start_time = time.time()
        
        try:
            # Execute handler
            if asyncio.iscoroutinefunction(handler):
                await handler(event, event_metadata)
            else:
                # Run synchronous handler in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event, event_metadata)
            
            # Update success metrics
            duration = time.time() - start_time
            metadata["execution_count"] += 1
            metadata["last_execution"] = time.time()
            
            # Update average duration
            if metadata["average_duration"] == 0:
                metadata["average_duration"] = duration
            else:
                metadata["average_duration"] = (
                    metadata["average_duration"] * 0.9 + duration * 0.1
                )
            
        except Exception as e:
            # Handle failure with retry policy
            await self._handle_handler_failure(handler, event, event_metadata, e)
    
    async def _handle_handler_failure(
        self, handler: Callable, event: Any, event_metadata: Optional[Dict], error: Exception
    ):
        """Handle handler failure with retry policy"""
        handler_id = f"{handler.__module__}.{handler.__name__}"
        metadata = self.handler_metadata.get(handler_id, {})
        retry_policy = metadata.get("retry_policy", {})
        
        max_retries = retry_policy.get("max_retries", 3)
        delay = retry_policy.get("delay", 1.0)
        
        retry_count = getattr(event, "_retry_count", {}).get(handler_id, 0)
        
        if retry_count < max_retries:
            # Retry after delay
            retry_count += 1
            if not hasattr(event, "_retry_count"):
                event._retry_count = {}
            event._retry_count[handler_id] = retry_count
            
            logger.warning(
                f"Handler {handler_id} failed, retrying ({retry_count}/{max_retries}): {str(error)}"
            )
            
            # Schedule retry
            await asyncio.sleep(delay * retry_count)  # Exponential backoff
            await self._execute_handler(handler, event, event_metadata)
        else:
            # Max retries exceeded
            metadata["failure_count"] += 1
            logger.error(
                f"Handler {handler_id} failed permanently after {max_retries} retries: {str(error)}"
            )
            
            # Optionally send to dead letter queue
            await self._send_to_dead_letter_queue(handler, event, error)
    
    async def _send_to_dead_letter_queue(
        self, handler: Callable, event: Any, error: Exception
    ):
        """Send failed event to dead letter queue"""
        # Implementation would send to actual dead letter queue
        logger.info(f"Sending event to dead letter queue: {event.__class__.__name__}")
    
    def get_handler_statistics(self) -> Dict[str, Dict]:
        """Get handler execution statistics"""
        return self.handler_metadata.copy()

class BaseEventHandler(ABC):
    """Base class for all event handlers"""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.enabled = True
        self.execution_count = 0
        self.failure_count = 0
        self.last_execution = None
        self.processing_time_ms = 0.0
    
    @abstractmethod
    async def handle(self, event: Any, context: Optional[Dict] = None):
        """Handle the event - must be implemented by subclasses"""
        pass
    
    def can_handle(self, event: Any) -> bool:
        """Check if this handler can handle the event"""
        return True
    
    async def execute(self, event: Any, context: Optional[Dict] = None):
        """Execute the handler with metrics tracking"""
        if not self.enabled:
            logger.debug(f"Handler {self.name} is disabled")
            return
        
        if not self.can_handle(event):
            logger.debug(f"Handler {self.name} cannot handle event {event.__class__.__name__}")
            return
        
        start_time = time.time()
        
        try:
            await self.handle(event, context)
            
            # Update metrics
            self.execution_count += 1
            self.last_execution = time.time()
            self.processing_time_ms = (time.time() - start_time) * 1000
            
            logger.debug(
                f"Handler {self.name} executed successfully "
                f"({self.processing_time_ms:.2f}ms)"
            )
            
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Handler {self.name} failed: {str(e)}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "execution_count": self.execution_count,
            "failure_count": self.failure_count,
            "last_execution": self.last_execution,
            "processing_time_ms": self.processing_time_ms,
            "success_rate": (
                (self.execution_count - self.failure_count) / max(self.execution_count, 1)
            ) * 100
        }

class AsyncEventHandler(BaseEventHandler):
    """Asynchronous event handler base"""
    
    def __init__(self, name: str = None, max_concurrent: int = 10):
        super().__init__(name)
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks = 0
    
    async def execute(self, event: Any, context: Optional[Dict] = None):
        """Execute with concurrency control"""
        async with self.semaphore:
            self.active_tasks += 1
            try:
                await super().execute(event, context)
            finally:
                self.active_tasks -= 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics including concurrency info"""
        metrics = super().get_metrics()
        metrics.update({
            "max_concurrent": self.max_concurrent,
            "active_tasks": self.active_tasks
        })
        return metrics

class RetryableEventHandler(BaseEventHandler):
    """Event handler with retry capability"""
    
    def __init__(
        self, 
        name: str = None, 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        exponential_backoff: bool = True
    ):
        super().__init__(name)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.exponential_backoff = exponential_backoff
        self.retry_count = 0
    
    async def execute(self, event: Any, context: Optional[Dict] = None):
        """Execute with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                await super().execute(event, context)
                if attempt > 0:
                    logger.info(f"Handler {self.name} succeeded on retry {attempt}")
                return
                
            except Exception as e:
                last_exception = e
                self.retry_count += 1
                
                if attempt < self.max_retries:
                    delay = self.retry_delay
                    if self.exponential_backoff:
                        delay *= (2 ** attempt)
                    
                    logger.warning(
                        f"Handler {self.name} failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {str(e)}"
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Handler {self.name} failed after {self.max_retries} retries: {str(e)}"
                    )
                    raise last_exception
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics including retry info"""
        metrics = super().get_metrics()
        metrics.update({
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "exponential_backoff": self.exponential_backoff
        })
        return metrics

class EventHandlerChain:
    """Chain of responsibility for event handlers"""
    
    def __init__(self):
        self.handlers: List[BaseEventHandler] = []
        self.stop_on_failure = False
    
    def add_handler(self, handler: BaseEventHandler):
        """Add handler to chain"""
        self.handlers.append(handler)
        logger.info(f"Added handler to chain: {handler.name}")
    
    def remove_handler(self, handler: BaseEventHandler):
        """Remove handler from chain"""
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.info(f"Removed handler from chain: {handler.name}")
    
    async def process(self, event: Any, context: Optional[Dict] = None):
        """Process event through handler chain"""
        results = []
        
        for handler in self.handlers:
            try:
                await handler.execute(event, context)
                results.append({"handler": handler.name, "success": True, "error": None})
                
            except Exception as e:
                results.append({"handler": handler.name, "success": False, "error": str(e)})
                
                if self.stop_on_failure:
                    logger.warning(f"Stopping chain due to failure in {handler.name}")
                    break
        
        return results
    
    def get_chain_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all handlers in chain"""
        return [handler.get_metrics() for handler in self.handlers]

class EventHandlerMetrics:
    """Event handler performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict] = {}
        self.global_metrics = {
            "total_events_processed": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "peak_events_per_second": 0.0,
            "current_events_per_second": 0.0
        }
        self.recent_events: List[float] = []
        self.max_recent_events = 100
    
    def record_handler_execution(
        self, 
        handler_name: str, 
        event_type: str, 
        duration: float, 
        success: bool
    ):
        """Record handler execution metrics"""
        if handler_name not in self.metrics:
            self.metrics[handler_name] = {
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "total_duration": 0.0,
                "average_duration": 0.0,
                "min_duration": float('inf'),
                "max_duration": 0.0,
                "last_execution": None,
                "event_types": set()
            }
        
        metrics = self.metrics[handler_name]
        metrics["execution_count"] += 1
        metrics["total_duration"] += duration
        metrics["average_duration"] = metrics["total_duration"] / metrics["execution_count"]
        metrics["min_duration"] = min(metrics["min_duration"], duration)
        metrics["max_duration"] = max(metrics["max_duration"], duration)
        metrics["last_execution"] = time.time()
        metrics["event_types"].add(event_type)
        
        if success:
            metrics["success_count"] += 1
        else:
            metrics["failure_count"] += 1
        
        # Update global metrics
        self.global_metrics["total_events_processed"] += 1
        self.global_metrics["total_processing_time"] += duration
        self.global_metrics["average_processing_time"] = (
            self.global_metrics["total_processing_time"] / 
            self.global_metrics["total_events_processed"]
        )
        
        # Track recent events for rate calculation
        self.recent_events.append(time.time())
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events.pop(0)
        
        # Calculate events per second
        if len(self.recent_events) >= 2:
            time_span = self.recent_events[-1] - self.recent_events[0]
            if time_span > 0:
                current_rate = len(self.recent_events) / time_span
                self.global_metrics["current_events_per_second"] = current_rate
                self.global_metrics["peak_events_per_second"] = max(
                    self.global_metrics["peak_events_per_second"], 
                    current_rate
                )
    
    def get_handler_metrics(self, handler_name: str) -> Optional[Dict]:
        """Get metrics for specific handler"""
        metrics = self.metrics.get(handler_name)
        if metrics:
            # Convert set to list for JSON serialization
            metrics_copy = metrics.copy()
            metrics_copy["event_types"] = list(metrics["event_types"])
            return metrics_copy
        return None
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        handler_metrics = {}
        for handler_name, metrics in self.metrics.items():
            metrics_copy = metrics.copy()
            metrics_copy["event_types"] = list(metrics["event_types"])
            handler_metrics[handler_name] = metrics_copy
        
        return {
            "global_metrics": self.global_metrics,
            "handler_metrics": handler_metrics
        }
    
    def get_top_performers(self, limit: int = 10) -> List[Dict]:
        """Get top performing handlers by success rate"""
        handlers = []
        
        for handler_name, metrics in self.metrics.items():
            success_rate = (
                metrics["success_count"] / max(metrics["execution_count"], 1)
            ) * 100
            
            handlers.append({
                "handler_name": handler_name,
                "success_rate": success_rate,
                "execution_count": metrics["execution_count"],
                "average_duration": metrics["average_duration"]
            })
        
        # Sort by success rate, then by execution count
        handlers.sort(key=lambda x: (x["success_rate"], x["execution_count"]), reverse=True)
        
        return handlers[:limit]

class EventHandlerValidator:
    """Event handler validation utility"""
    
    @staticmethod
    def validate_handler(handler: Callable) -> Dict[str, Any]:
        """Validate event handler function"""
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "signature_info": {}
        }
        
        try:
            # Check if callable
            if not callable(handler):
                validation_result["valid"] = False
                validation_result["issues"].append("Handler must be callable")
                return validation_result
            
            # Analyze function signature
            sig = inspect.signature(handler)
            params = sig.parameters
            
            validation_result["signature_info"] = {
                "parameter_count": len(params),
                "parameter_names": list(params.keys()),
                "has_event_param": "event" in params,
                "has_context_param": "context" in params,
                "is_async": asyncio.iscoroutinefunction(handler)
            }
            
            # Check required parameters
            if len(params) < 1:
                validation_result["valid"] = False
                validation_result["issues"].append("Handler must accept at least one parameter (event)")
            
            # Check for event parameter
            if "event" not in params and len(params) > 0:
                first_param = list(params.keys())[0]
                validation_result["warnings"].append(
                    f"First parameter '{first_param}' should probably be named 'event'"
                )
            
            # Check type hints
            try:
                type_hints = get_type_hints(handler)
                validation_result["signature_info"]["type_hints"] = {
                    param: str(hint) for param, hint in type_hints.items()
                }
            except:
                validation_result["warnings"].append("Could not extract type hints")
            
            # Check return type for async functions
            if validation_result["signature_info"]["is_async"]:
                if sig.return_annotation != inspect.Signature.empty:
                    validation_result["warnings"].append(
                        "Async handlers should not return values"
                    )
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    @staticmethod
    def suggest_improvements(handler: Callable) -> List[str]:
        """Suggest improvements for event handler"""
        suggestions = []
        validation = EventHandlerValidator.validate_handler(handler)
        
        if not validation["signature_info"]["is_async"]:
            suggestions.append("Consider making handler async for better performance")
        
        if validation["signature_info"]["parameter_count"] < 2:
            suggestions.append("Consider adding context parameter for additional event metadata")
        
        if not validation["signature_info"].get("type_hints"):
            suggestions.append("Add type hints for better code documentation and IDE support")
        
        # Check if handler has error handling
        source = inspect.getsource(handler)
        if "try:" not in source:
            suggestions.append("Consider adding error handling within the handler")
        
        if "logger" not in source and "log" not in source:
            suggestions.append("Consider adding logging for debugging and monitoring")
        
        return suggestions

# Decorator for easy handler registration
def event_handler(
    event_type: str, 
    priority: int = 0, 
    registry: Optional[EventHandlerRegistry] = None
):
    """Decorator for registering event handlers"""
    def decorator(func):
        if registry:
            registry.register(event_type, func, priority=priority)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # Store metadata on function
        wrapper._event_type = event_type
        wrapper._priority = priority
        
        return wrapper
    
    return decorator