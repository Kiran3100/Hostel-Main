# queue_processor_service.py

from typing import Dict, List, Any, Optional, Callable, Generic, TypeVar, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
import uuid
import json
from contextlib import contextmanager

T = TypeVar('T')

class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class MessageStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"

@dataclass
class Message(Generic[T]):
    """Queue message with metadata"""
    message_id: str
    queue_name: str
    payload: T
    priority: MessagePriority
    status: MessageStatus
    created_at: datetime
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = None

    @classmethod
    def create(
        cls,
        queue_name: str,
        payload: T,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> 'Message[T]':
        return cls(
            message_id=str(uuid.uuid4()),
            queue_name=queue_name,
            payload=payload,
            priority=priority,
            status=MessageStatus.PENDING,
            created_at=datetime.utcnow(),
            metadata={}
        )

class MessageProcessor:
    """Processes queue messages"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_handler(
        self,
        queue_name: str,
        handler: Callable
    ) -> None:
        """Register message handler"""
        self._handlers[queue_name] = handler
        self.logger.info(f"Registered handler for queue: {queue_name}")

    def add_middleware(self, middleware: Callable) -> None:
        """Add processing middleware"""
        self._middleware.append(middleware)
        self.logger.info(f"Added middleware: {middleware.__name__}")

    async def process_message(
        self,
        message: Message
    ) -> None:
        """Process a message"""
        handler = self._handlers.get(message.queue_name)
        if not handler:
            raise ValueError(f"No handler for queue: {message.queue_name}")

        message.status = MessageStatus.PROCESSING
        message.processed_at = datetime.utcnow()

        try:
            # Execute middleware chain
            payload = message.payload
            for middleware in self._middleware:
                payload = await middleware(payload, message)

            # Execute handler
            await handler(payload, message)
            message.status = MessageStatus.COMPLETED
        except Exception as e:
            message.status = MessageStatus.FAILED
            message.error = str(e)
            raise

class DeadLetterHandler:
    """Handles failed messages"""
    
    def __init__(self):
        self._dead_letter_queues: Dict[str, List[Message]] = {}
        self._handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_handler(
        self,
        queue_name: str,
        handler: Callable
    ) -> None:
        """Add dead letter handler"""
        self._handlers[queue_name] = handler
        self.logger.info(f"Added dead letter handler for {queue_name}")

    async def handle_failed_message(
        self,
        message: Message
    ) -> None:
        """Handle failed message"""
        if message.queue_name not in self._dead_letter_queues:
            self._dead_letter_queues[message.queue_name] = []

        message.status = MessageStatus.DEAD_LETTER
        self._dead_letter_queues[message.queue_name].append(message)
        
        handler = self._handlers.get(message.queue_name)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                self.logger.error(
                    f"Dead letter handler failed for {message.message_id}: {str(e)}"
                )

    async def retry_messages(
        self,
        queue_name: str
    ) -> List[Message]:
        """Retry dead letter messages"""
        messages = self._dead_letter_queues.get(queue_name, [])
        self._dead_letter_queues[queue_name] = []
        return messages

class PriorityProcessor:
    """Handles priority-based message processing"""
    
    def __init__(self):
        self._queues: Dict[MessagePriority, asyncio.PriorityQueue] = {
            priority: asyncio.PriorityQueue()
            for priority in MessagePriority
        }
        self.logger = logging.getLogger(self.__class__.__name__)

    async def enqueue(self, message: Message) -> None:
        """Enqueue message with priority"""
        queue = self._queues[message.priority]
        await queue.put((message.priority.value, message))
        self.logger.debug(f"Enqueued message: {message.message_id}")

    async def dequeue(self) -> Optional[Message]:
        """Get next message by priority"""
        for priority in sorted(
            MessagePriority,
            key=lambda x: x.value,
            reverse=True
        ):
            queue = self._queues[priority]
            if not queue.empty():
                _, message = await queue.get()
                return message
        return None

class BatchProcessor:
    """Processes messages in batches"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self._batches: Dict[str, List[Message]] = {}
        self._handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_handler(
        self,
        queue_name: str,
        handler: Callable
    ) -> None:
        """Register batch handler"""
        self._handlers[queue_name] = handler
        self.logger.info(f"Registered batch handler for {queue_name}")

    async def add_to_batch(
        self,
        message: Message
    ) -> bool:
        """Add message to batch"""
        if message.queue_name not in self._batches:
            self._batches[message.queue_name] = []

        batch = self._batches[message.queue_name]
        batch.append(message)

        if len(batch) >= self.batch_size:
            await self.process_batch(message.queue_name)
            return True
        return False

    async def process_batch(
        self,
        queue_name: str
    ) -> None:
        """Process message batch"""
        batch = self._batches.get(queue_name, [])
        if not batch:
            return

        handler = self._handlers.get(queue_name)
        if not handler:
            raise ValueError(f"No batch handler for queue: {queue_name}")

        try:
            await handler(batch)
            for message in batch:
                message.status = MessageStatus.COMPLETED
        except Exception as e:
            for message in batch:
                message.status = MessageStatus.FAILED
                message.error = str(e)
            raise
        finally:
            self._batches[queue_name] = []

class ErrorHandler:
    """Handles processing errors"""
    
    def __init__(self):
        self._error_handlers: Dict[type, Callable] = {}
        self._retry_policies: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_error_handler(
        self,
        error_type: type,
        handler: Callable
    ) -> None:
        """Add error handler"""
        self._error_handlers[error_type] = handler
        self.logger.info(f"Added handler for {error_type.__name__}")

    def set_retry_policy(
        self,
        queue_name: str,
        max_retries: int,
        retry_delay: int
    ) -> None:
        """Set retry policy"""
        self._retry_policies[queue_name] = {
            'max_retries': max_retries,
            'retry_delay': retry_delay
        }

    async def handle_error(
        self,
        error: Exception,
        message: Message
    ) -> bool:
        """Handle processing error"""
        for error_type, handler in self._error_handlers.items():
            if isinstance(error, error_type):
                try:
                    await handler(error, message)
                    return True
                except Exception as e:
                    self.logger.error(
                        f"Error handler failed: {str(e)}"
                    )
                    break

        # Check retry policy
        policy = self._retry_policies.get(message.queue_name, {})
        max_retries = policy.get('max_retries', 3)
        
        if message.retry_count < max_retries:
            message.retry_count += 1
            return True
        
        return False

class PerformanceMonitor:
    """Monitors queue performance"""
    
    def __init__(self):
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._start_times: Dict[str, datetime] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def start_processing(
        self,
        message: Message
    ) -> None:
        """Record processing start"""
        self._start_times[message.message_id] = datetime.utcnow()

    def end_processing(
        self,
        message: Message
    ) -> None:
        """Record processing end"""
        start_time = self._start_times.pop(message.message_id, None)
        if not start_time:
            return

        duration = (datetime.utcnow() - start_time).total_seconds()
        queue_metrics = self._metrics.get(message.queue_name, {
            'total_messages': 0,
            'successful_messages': 0,
            'failed_messages': 0,
            'total_duration': 0,
            'average_duration': 0
        })

        queue_metrics['total_messages'] += 1
        queue_metrics['total_duration'] += duration
        queue_metrics['average_duration'] = (
            queue_metrics['total_duration'] / queue_metrics['total_messages']
        )

        if message.status == MessageStatus.COMPLETED:
            queue_metrics['successful_messages'] += 1
        elif message.status == MessageStatus.FAILED:
            queue_metrics['failed_messages'] += 1

        self._metrics[message.queue_name] = queue_metrics

    def get_metrics(
        self,
        queue_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get performance metrics"""
        if queue_name:
            return self._metrics.get(queue_name, {})
        return self._metrics

class QueueOptimizer:
    """Optimizes queue processing"""
    
    def __init__(self):
        self._queue_stats: Dict[str, Dict[str, Any]] = {}
        self._optimization_rules: List[Callable] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_optimization_rule(
        self,
        rule: Callable
    ) -> None:
        """Add optimization rule"""
        self._optimization_rules.append(rule)
        self.logger.info(f"Added optimization rule: {rule.__name__}")

    def update_stats(
        self,
        queue_name: str,
        processed: int,
        duration: float
    ) -> None:
        """Update queue statistics"""
        if queue_name not in self._queue_stats:
            self._queue_stats[queue_name] = {
                'processed_count': 0,
                'total_duration': 0,
                'average_duration': 0
            }

        stats = self._queue_stats[queue_name]
        stats['processed_count'] += processed
        stats['total_duration'] += duration
        stats['average_duration'] = (
            stats['total_duration'] / stats['processed_count']
        )

    async def optimize_queue(
        self,
        queue_name: str
    ) -> Dict[str, Any]:
        """Run queue optimization"""
        stats = self._queue_stats.get(queue_name, {})
        optimizations = {}

        for rule in self._optimization_rules:
            try:
                result = await rule(queue_name, stats)
                optimizations.update(result)
            except Exception as e:
                self.logger.error(
                    f"Optimization rule failed: {str(e)}"
                )

        return optimizations

class QueueProcessorService:
    """Main queue processor service"""
    
    def __init__(self):
        self.processor = MessageProcessor()
        self.dead_letter = DeadLetterHandler()
        self.priority = PriorityProcessor()
        self.batch = BatchProcessor()
        self.error = ErrorHandler()
        self.monitor = PerformanceMonitor()
        self.optimizer = QueueOptimizer()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start(self) -> None:
        """Start queue processor"""
        self._running = True
        self._processor_task = asyncio.create_task(self._run_processor())
        self.logger.info("Queue processor started")

    async def stop(self) -> None:
        """Stop queue processor"""
        self._running = False
        if self._processor_task:
            await self._processor_task
        self.logger.info("Queue processor stopped")

    async def enqueue(
        self,
        queue_name: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Message:
        """Enqueue message"""
        message = Message.create(queue_name, payload, priority)
        await self.priority.enqueue(message)
        return message

    async def _run_processor(self) -> None:
        """Main processing loop"""
        while self._running:
            try:
                message = await self.priority.dequeue()
                if not message:
                    await asyncio.sleep(0.1)
                    continue

                self.monitor.start_processing(message)

                try:
                    if await self.batch.add_to_batch(message):
                        continue

                    await self.processor.process_message(message)
                except Exception as e:
                    if not await self.error.handle_error(e, message):
                        await self.dead_letter.handle_failed_message(message)
                finally:
                    self.monitor.end_processing(message)

            except Exception as e:
                self.logger.error(f"Processor error: {str(e)}")
                await asyncio.sleep(1)

    def register_handler(
        self,
        queue_name: str,
        handler: Callable
    ) -> None:
        """Register message handler"""
        self.processor.register_handler(queue_name, handler)

    def register_batch_handler(
        self,
        queue_name: str,
        handler: Callable
    ) -> None:
        """Register batch handler"""
        self.batch.register_handler(queue_name, handler)

    def add_middleware(
        self,
        middleware: Callable
    ) -> None:
        """Add processing middleware"""
        self.processor.add_middleware(middleware)

    def set_retry_policy(
        self,
        queue_name: str,
        max_retries: int,
        retry_delay: int
    ) -> None:
        """Set retry policy"""
        self.error.set_retry_policy(queue_name, max_retries, retry_