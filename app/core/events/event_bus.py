import asyncio
import time
import json
from typing import Dict, List, Any, Callable, Optional, Type, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class EventPriority(Enum):
    """Event priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class EventMetadata:
    """Event metadata for tracking and processing"""
    event_id: str
    timestamp: float
    priority: EventPriority
    source: str
    correlation_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    delay_until: Optional[float] = None

class EventBus:
    """Central event dispatching system"""
    
    def __init__(self, max_workers: int = 10):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.dead_letter_queue: List[Any] = []
        self.processing = False
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "events_retried": 0
        }
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed to event: {event_type} -> {handler.__name__}")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from event type"""
        if handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            logger.info(f"Unsubscribed from event: {event_type} -> {handler.__name__}")
    
    async def publish(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
        delay: Optional[float] = None
    ):
        """Publish event to the bus"""
        metadata = EventMetadata(
            event_id=f"event_{int(time.time() * 1000000)}",
            timestamp=time.time(),
            priority=priority,
            source=event.__class__.__name__,
            correlation_id=correlation_id,
            delay_until=time.time() + delay if delay else None
        )
        
        await self.event_queue.put((event, metadata))
        self.metrics["events_published"] += 1
        
        logger.debug(
            f"Event published: {event.__class__.__name__} "
            f"(id: {metadata.event_id}, priority: {priority.name})"
        )
    
    async def start_processing(self):
        """Start event processing loop"""
        if self.processing:
            return
        
        self.processing = True
        logger.info("Event bus processing started")
        
        # Start multiple worker tasks
        tasks = []
        for i in range(self.max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            tasks.append(task)
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Event processing error: {str(e)}")
        finally:
            self.processing = False
    
    async def stop_processing(self):
        """Stop event processing"""
        self.processing = False
        logger.info("Event bus processing stopped")
    
    async def _worker(self, worker_name: str):
        """Worker task for processing events"""
        logger.info(f"Event worker {worker_name} started")
        
        while self.processing:
            try:
                # Get event from queue with timeout
                try:
                    event, metadata = await asyncio.wait_for(
                        self.event_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check if event should be delayed
                if metadata.delay_until and time.time() < metadata.delay_until:
                    # Put back in queue for later processing
                    await asyncio.sleep(0.1)
                    await self.event_queue.put((event, metadata))
                    continue
                
                # Process event
                await self._process_event(event, metadata, worker_name)
                
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {str(e)}")
                await asyncio.sleep(0.1)
        
        logger.info(f"Event worker {worker_name} stopped")
    
    async def _process_event(self, event: Any, metadata: EventMetadata, worker_name: str):
        """Process individual event"""
        event_type = event.__class__.__name__
        handlers = self.subscribers.get(event_type, [])
        
        if not handlers:
            logger.warning(f"No handlers for event: {event_type}")
            return
        
        logger.debug(
            f"Processing event: {event_type} "
            f"(id: {metadata.event_id}, worker: {worker_name})"
        )
        
        # Process handlers concurrently
        handler_tasks = []
        for handler in handlers:
            task = asyncio.create_task(
                self._execute_handler(handler, event, metadata)
            )
            handler_tasks.append(task)
        
        # Wait for all handlers to complete
        results = await asyncio.gather(*handler_tasks, return_exceptions=True)
        
        # Check for failures
        failures = [r for r in results if isinstance(r, Exception)]
        if failures:
            await self._handle_processing_failures(event, metadata, failures)
        else:
            self.metrics["events_processed"] += 1
    
    async def _execute_handler(self, handler: Callable, event: Any, metadata: EventMetadata):
        """Execute single event handler"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event, metadata)
            else:
                # Run synchronous handler in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, handler, event, metadata)
                
        except Exception as e:
            logger.error(
                f"Handler {handler.__name__} failed for event "
                f"{event.__class__.__name__}: {str(e)}"
            )
            raise
    
    async def _handle_processing_failures(
        self, event: Any, metadata: EventMetadata, failures: List[Exception]
    ):
        """Handle event processing failures"""
        self.metrics["events_failed"] += 1
        
        # Check if we should retry
        if metadata.retry_count < metadata.max_retries:
            metadata.retry_count += 1
            metadata.delay_until = time.time() + (2 ** metadata.retry_count)  # Exponential backoff
            
            await self.event_queue.put((event, metadata))
            self.metrics["events_retried"] += 1
            
            logger.warning(
                f"Event {metadata.event_id} failed, retrying "
                f"({metadata.retry_count}/{metadata.max_retries})"
            )
        else:
            # Send to dead letter queue
            self.dead_letter_queue.append({
                "event": event,
                "metadata": asdict(metadata),
                "failures": [str(f) for f in failures],
                "failed_at": time.time()
            })
            
            logger.error(
                f"Event {metadata.event_id} failed permanently, "
                f"moved to dead letter queue"
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get event bus metrics"""
        return {
            **self.metrics,
            "queue_size": self.event_queue.qsize(),
            "dead_letter_count": len(self.dead_letter_queue),
            "active_workers": self.max_workers,
            "subscribers_count": {
                event_type: len(handlers)
                for event_type, handlers in self.subscribers.items()
            }
        }

class EventDispatcher:
    """Event distribution manager"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.middleware: List[Callable] = []
    
    def add_middleware(self, middleware: Callable):
        """Add middleware for event processing"""
        self.middleware.append(middleware)
        logger.info(f"Added event middleware: {middleware.__name__}")
    
    async def dispatch(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Dispatch event through middleware chain"""
        # Apply middleware chain
        processed_event = event
        event_context = context or {}
        
        for middleware in self.middleware:
            try:
                if asyncio.iscoroutinefunction(middleware):
                    processed_event = await middleware(processed_event, event_context)
                else:
                    processed_event = middleware(processed_event, event_context)
                
                if processed_event is None:
                    logger.info(f"Event filtered by middleware: {middleware.__name__}")
                    return
                    
            except Exception as e:
                logger.error(f"Middleware {middleware.__name__} failed: {str(e)}")
                # Continue with original event if middleware fails
                break
        
        # Dispatch processed event
        await self.event_bus.publish(
            processed_event,
            priority=priority,
            correlation_id=correlation_id
        )

class AsyncEventBus:
    """Asynchronous event processing bus"""
    
    def __init__(self, buffer_size: int = 1000):
        self.event_buffer: asyncio.Queue = asyncio.Queue(maxsize=buffer_size)
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.processing_tasks: List[asyncio.Task] = []
        self.is_running = False
    
    async def start(self):
        """Start async event processing"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start processing tasks
        for i in range(3):  # 3 concurrent processors
            task = asyncio.create_task(self._process_events(f"processor-{i}"))
            self.processing_tasks.append(task)
        
        logger.info("Async event bus started")
    
    async def stop(self):
        """Stop async event processing"""
        self.is_running = False
        
        # Cancel processing tasks
        for task in self.processing_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.processing_tasks, return_exceptions=True)
        self.processing_tasks.clear()
        
        logger.info("Async event bus stopped")
    
    async def emit(self, event: Any, **kwargs):
        """Emit event asynchronously"""
        try:
            await self.event_buffer.put_nowait((event, kwargs, time.time()))
        except asyncio.QueueFull:
            logger.warning("Event buffer full, dropping event")
    
    def on(self, event_type: str, handler: Callable):
        """Register event handler"""
        self.subscribers[event_type].append(handler)
    
    async def _process_events(self, processor_name: str):
        """Process events from buffer"""
        logger.info(f"Event processor {processor_name} started")
        
        while self.is_running:
            try:
                event, kwargs, timestamp = await asyncio.wait_for(
                    self.event_buffer.get(),
                    timeout=1.0
                )
                
                event_type = event.__class__.__name__
                handlers = self.subscribers.get(event_type, [])
                
                # Execute handlers concurrently
                if handlers:
                    tasks = [
                        self._execute_async_handler(handler, event, kwargs)
                        for handler in handlers
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processor {processor_name} error: {str(e)}")
        
        logger.info(f"Event processor {processor_name} stopped")
    
    async def _execute_async_handler(
        self, handler: Callable, event: Any, kwargs: Dict[str, Any]
    ):
        """Execute async event handler"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event, **kwargs)
            else:
                handler(event, **kwargs)
        except Exception as e:
            logger.error(f"Async handler {handler.__name__} failed: {str(e)}")

class EventQueue:
    """Event queuing and processing manager"""
    
    def __init__(self, max_size: int = 10000):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self.processing = False
        self.batch_size = 10
        self.batch_timeout = 1.0
    
    async def enqueue(
        self,
        event: Any,
        priority: int = EventPriority.NORMAL.value,
        delay: float = 0
    ):
        """Add event to priority queue"""
        scheduled_time = time.time() + delay
        queue_item = (priority, scheduled_time, event)
        
        try:
            await self.queue.put(queue_item)
        except asyncio.QueueFull:
            logger.warning("Event queue is full, dropping event")
    
    async def start_batch_processing(self, processor: Callable):
        """Start batch processing of events"""
        self.processing = True
        logger.info("Event queue batch processing started")
        
        while self.processing:
            batch = []
            batch_start = time.time()
            
            # Collect batch
            while (
                len(batch) < self.batch_size and 
                (time.time() - batch_start) < self.batch_timeout
            ):
                try:
                    priority, scheduled_time, event = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=0.1
                    )
                    
                    # Check if event should be processed now
                    if time.time() >= scheduled_time:
                        batch.append(event)
                    else:
                        # Put back for later
                        await self.queue.put((priority, scheduled_time, event))
                        
                except asyncio.TimeoutError:
                    break
            
            # Process batch if not empty
            if batch:
                try:
                    await processor(batch)
                except Exception as e:
                    logger.error(f"Batch processing failed: {str(e)}")
            
            # Small delay to prevent busy waiting
            await asyncio.sleep(0.01)
    
    def stop_processing(self):
        """Stop event processing"""
        self.processing = False
        logger.info("Event queue processing stopped")

class EventRouter:
    """Event routing and filtering"""
    
    def __init__(self):
        self.routes: Dict[str, List[Dict]] = defaultdict(list)
        self.filters: List[Callable] = []
    
    def add_route(
        self,
        event_type: str,
        handler: Callable,
        condition: Optional[Callable] = None,
        priority: int = 0
    ):
        """Add event route with optional condition"""
        route = {
            "handler": handler,
            "condition": condition,
            "priority": priority
        }
        
        self.routes[event_type].append(route)
        
        # Sort by priority
        self.routes[event_type].sort(key=lambda x: x["priority"], reverse=True)
        
        logger.info(f"Added route for {event_type} -> {handler.__name__}")
    
    def add_filter(self, filter_func: Callable):
        """Add global event filter"""
        self.filters.append(filter_func)
    
    async def route_event(self, event: Any, context: Optional[Dict] = None):
        """Route event to appropriate handlers"""
        event_type = event.__class__.__name__
        
        # Apply global filters
        for filter_func in self.filters:
            if not filter_func(event, context):
                logger.debug(f"Event filtered: {event_type}")
                return
        
        # Find matching routes
        routes = self.routes.get(event_type, [])
        
        for route in routes:
            condition = route["condition"]
            
            # Check condition if specified
            if condition and not condition(event, context):
                continue
            
            # Execute handler
            try:
                handler = route["handler"]
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, context)
                else:
                    handler(event, context)
                    
            except Exception as e:
                logger.error(
                    f"Route handler {route['handler'].__name__} failed "
                    f"for event {event_type}: {str(e)}"
                )

class EventPriorityManager:
    """Event priority and ordering manager"""
    
    def __init__(self):
        self.priority_queues: Dict[EventPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in EventPriority
        }
        self.processing_order = [
            EventPriority.CRITICAL,
            EventPriority.HIGH,
            EventPriority.NORMAL,
            EventPriority.LOW
        ]
    
    async def enqueue_by_priority(self, event: Any, priority: EventPriority):
        """Enqueue event by priority"""
        await self.priority_queues[priority].put(event)
        logger.debug(f"Event enqueued with priority {priority.name}")
    
    async def dequeue_by_priority(self) -> Optional[tuple]:
        """Dequeue event by priority order"""
        for priority in self.processing_order:
            queue = self.priority_queues[priority]
            
            if not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.01)
                    return event, priority
                except asyncio.TimeoutError:
                    continue
        
        return None
    
    async def process_by_priority(self, processor: Callable):
        """Process events in priority order"""
        while True:
            result = await self.dequeue_by_priority()
            
            if result is None:
                await asyncio.sleep(0.01)
                continue
            
            event, priority = result
            
            try:
                await processor(event, priority)
            except Exception as e:
                logger.error(f"Priority processor failed: {str(e)}")

class EventBatch:
    """Batch event processing manager"""
    
    def __init__(self, batch_size: int = 50, timeout: float = 5.0):
        self.batch_size = batch_size
        self.timeout = timeout
        self.current_batch: List[Any] = []
        self.last_batch_time = time.time()
        self.processors: List[Callable] = []
    
    def add_processor(self, processor: Callable):
        """Add batch processor"""
        self.processors.append(processor)
    
    async def add_event(self, event: Any):
        """Add event to current batch"""
        self.current_batch.append(event)
        
        # Check if batch should be processed
        if (
            len(self.current_batch) >= self.batch_size or
            (time.time() - self.last_batch_time) >= self.timeout
        ):
            await self._process_batch()
    
    async def _process_batch(self):
        """Process current batch"""
        if not self.current_batch:
            return
        
        batch = self.current_batch.copy()
        self.current_batch.clear()
        self.last_batch_time = time.time()
        
        logger.debug(f"Processing batch of {len(batch)} events")
        
        # Send batch to all processors
        for processor in self.processors:
            try:
                if asyncio.iscoroutinefunction(processor):
                    await processor(batch)
                else:
                    processor(batch)
            except Exception as e:
                logger.error(f"Batch processor failed: {str(e)}")
    
    async def flush(self):
        """Flush remaining events in batch"""
        if self.current_batch:
            await self._process_batch()