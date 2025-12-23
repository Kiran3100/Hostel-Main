"""
Domain event dispatcher for event-driven architecture.
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
import asyncio

from app.core.logging import get_logger
from app.core.events.event_bus import EventBus
from app.schemas.core.domain_events import BaseDomainEvent


@dataclass
class DispatchedEvent:
    """Result of event dispatch operation."""
    
    event: BaseDomainEvent
    dispatched: bool
    error: Optional[str] = None
    dispatched_at: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class DispatchResult:
    """Aggregated result of multiple event dispatches."""
    
    total: int
    successful: int
    failed: int
    events: List[DispatchedEvent] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return (self.successful / self.total * 100) if self.total > 0 else 0.0


class EventDispatcher:
    """
    Dispatches domain events to the application's event bus with:
    - Synchronous and asynchronous dispatch
    - Batch dispatching
    - Retry mechanisms
    - Event filtering and transformation
    - Dispatch auditing
    """

    def __init__(
        self,
        bus: EventBus,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ):
        """
        Initialize event dispatcher.
        
        Args:
            bus: Event bus instance
            max_retries: Maximum retry attempts for failed dispatches
            retry_delay: Delay between retries in seconds
        """
        self.bus = bus
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._logger = get_logger(self.__class__.__name__)
        self._filters: List[Callable[[BaseDomainEvent], bool]] = []
        self._transformers: List[Callable[[BaseDomainEvent], BaseDomainEvent]] = []

    # -------------------------------------------------------------------------
    # Event Dispatching
    # -------------------------------------------------------------------------

    def dispatch(
        self,
        event: BaseDomainEvent,
        retry: bool = True,
    ) -> DispatchedEvent:
        """
        Dispatch a single domain event.
        
        Args:
            event: Domain event to dispatch
            retry: Whether to retry on failure
            
        Returns:
            DispatchedEvent with result information
        """
        # Apply filters
        if not self._should_dispatch(event):
            self._logger.debug(
                f"Event filtered out: {event.__class__.__name__}",
                extra={"event_type": event.__class__.__name__}
            )
            return DispatchedEvent(
                event=event,
                dispatched=False,
                error="Filtered by dispatch filter"
            )
        
        # Apply transformers
        transformed_event = self._transform_event(event)
        
        # Attempt dispatch with retries
        attempts = 0
        last_error = None
        
        while attempts < (self.max_retries if retry else 1):
            try:
                self.bus.publish(transformed_event)
                
                self._logger.info(
                    f"Event dispatched: {transformed_event.__class__.__name__}",
                    extra={
                        "event_type": transformed_event.__class__.__name__,
                        "event_data": transformed_event.model_dump() if hasattr(transformed_event, 'model_dump') else {},
                        "attempt": attempts + 1,
                    }
                )
                
                return DispatchedEvent(
                    event=transformed_event,
                    dispatched=True
                )
                
            except Exception as e:
                attempts += 1
                last_error = str(e)
                
                self._logger.warning(
                    f"Event dispatch failed (attempt {attempts}/{self.max_retries}): {e}",
                    extra={
                        "event_type": transformed_event.__class__.__name__,
                        "attempt": attempts,
                        "error": str(e),
                    }
                )
                
                # Wait before retry
                if retry and attempts < self.max_retries:
                    import time
                    time.sleep(self.retry_delay * attempts)  # Exponential backoff
        
        # All retries failed
        self._logger.error(
            f"Failed to dispatch event after {attempts} attempts",
            exc_info=True,
            extra={
                "event_type": transformed_event.__class__.__name__,
                "event_data": transformed_event.model_dump() if hasattr(transformed_event, 'model_dump') else {},
            }
        )
        
        return DispatchedEvent(
            event=transformed_event,
            dispatched=False,
            error=last_error
        )

    def dispatch_many(
        self,
        events: List[BaseDomainEvent],
        stop_on_error: bool = False,
        retry: bool = True,
    ) -> DispatchResult:
        """
        Dispatch multiple events.
        
        Args:
            events: List of domain events to dispatch
            stop_on_error: Stop dispatching if an error occurs
            retry: Whether to retry failed dispatches
            
        Returns:
            DispatchResult with aggregated statistics
        """
        dispatched_events = []
        successful = 0
        failed = 0
        
        for event in events:
            result = self.dispatch(event, retry=retry)
            dispatched_events.append(result)
            
            if result.dispatched:
                successful += 1
            else:
                failed += 1
                if stop_on_error:
                    self._logger.warning(
                        f"Stopping batch dispatch due to error at event {len(dispatched_events)}/{len(events)}"
                    )
                    break
        
        dispatch_result = DispatchResult(
            total=len(events),
            successful=successful,
            failed=failed,
            events=dispatched_events,
        )
        
        self._logger.info(
            f"Batch dispatch complete: {successful}/{len(events)} successful ({dispatch_result.success_rate:.1f}%)",
            extra={
                "total": len(events),
                "successful": successful,
                "failed": failed,
                "success_rate": dispatch_result.success_rate,
            }
        )
        
        return dispatch_result

    async def dispatch_async(
        self,
        event: BaseDomainEvent,
        retry: bool = True,
    ) -> DispatchedEvent:
        """
        Asynchronously dispatch a single event.
        
        Args:
            event: Domain event to dispatch
            retry: Whether to retry on failure
            
        Returns:
            DispatchedEvent with result information
        """
        # Run sync dispatch in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.dispatch,
            event,
            retry
        )

    async def dispatch_many_async(
        self,
        events: List[BaseDomainEvent],
        concurrent: bool = True,
        retry: bool = True,
    ) -> DispatchResult:
        """
        Asynchronously dispatch multiple events.
        
        Args:
            events: List of domain events
            concurrent: Whether to dispatch concurrently
            retry: Whether to retry failed dispatches
            
        Returns:
            DispatchResult with aggregated statistics
        """
        if concurrent:
            # Dispatch all events concurrently
            tasks = [
                self.dispatch_async(event, retry=retry)
                for event in events
            ]
            dispatched_events = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions from gather
            processed_events = []
            for i, result in enumerate(dispatched_events):
                if isinstance(result, Exception):
                    processed_events.append(
                        DispatchedEvent(
                            event=events[i],
                            dispatched=False,
                            error=str(result)
                        )
                    )
                else:
                    processed_events.append(result)
            
            dispatched_events = processed_events
        else:
            # Dispatch sequentially
            dispatched_events = []
            for event in events:
                result = await self.dispatch_async(event, retry=retry)
                dispatched_events.append(result)
        
        successful = sum(1 for e in dispatched_events if e.dispatched)
        failed = len(dispatched_events) - successful
        
        return DispatchResult(
            total=len(events),
            successful=successful,
            failed=failed,
            events=dispatched_events,
        )

    # -------------------------------------------------------------------------
    # Filtering and Transformation
    # -------------------------------------------------------------------------

    def add_filter(self, filter_func: Callable[[BaseDomainEvent], bool]) -> None:
        """
        Add event filter.
        
        Args:
            filter_func: Function that returns True if event should be dispatched
        """
        self._filters.append(filter_func)
        self._logger.debug(f"Added event filter: {filter_func.__name__}")

    def add_transformer(
        self,
        transformer_func: Callable[[BaseDomainEvent], BaseDomainEvent]
    ) -> None:
        """
        Add event transformer.
        
        Args:
            transformer_func: Function that transforms event before dispatch
        """
        self._transformers.append(transformer_func)
        self._logger.debug(f"Added event transformer: {transformer_func.__name__}")

    def clear_filters(self) -> None:
        """Clear all event filters."""
        self._filters.clear()
        self._logger.debug("Cleared all event filters")

    def clear_transformers(self) -> None:
        """Clear all event transformers."""
        self._transformers.clear()
        self._logger.debug("Cleared all event transformers")

    def _should_dispatch(self, event: BaseDomainEvent) -> bool:
        """
        Check if event should be dispatched based on filters.
        
        Args:
            event: Event to check
            
        Returns:
            True if event should be dispatched
        """
        for filter_func in self._filters:
            try:
                if not filter_func(event):
                    return False
            except Exception as e:
                self._logger.error(
                    f"Error in event filter {filter_func.__name__}: {e}",
                    exc_info=True
                )
                # Continue with other filters on error
        
        return True

    def _transform_event(self, event: BaseDomainEvent) -> BaseDomainEvent:
        """
        Apply all transformers to event.
        
        Args:
            event: Event to transform
            
        Returns:
            Transformed event
        """
        transformed = event
        
        for transformer_func in self._transformers:
            try:
                transformed = transformer_func(transformed)
            except Exception as e:
                self._logger.error(
                    f"Error in event transformer {transformer_func.__name__}: {e}",
                    exc_info=True
                )
                # Continue with original event on error
        
        return transformed

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get dispatcher statistics.
        
        Returns:
            Dictionary with dispatcher statistics
        """
        return {
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "active_filters": len(self._filters),
            "active_transformers": len(self._transformers),
        }


class EventDispatcherFactory:
    """Factory for creating configured event dispatchers."""
    
    @staticmethod
    def create_default(bus: EventBus) -> EventDispatcher:
        """
        Create dispatcher with default configuration.
        
        Args:
            bus: Event bus instance
            
        Returns:
            Configured EventDispatcher
        """
        return EventDispatcher(bus=bus, max_retries=3, retry_delay=0.5)
    
    @staticmethod
    def create_with_filters(
        bus: EventBus,
        filters: List[Callable[[BaseDomainEvent], bool]],
    ) -> EventDispatcher:
        """
        Create dispatcher with pre-configured filters.
        
        Args:
            bus: Event bus instance
            filters: List of filter functions
            
        Returns:
            Configured EventDispatcher
        """
        dispatcher = EventDispatcher(bus=bus)
        for filter_func in filters:
            dispatcher.add_filter(filter_func)
        return dispatcher