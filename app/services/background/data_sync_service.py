# data_sync_service.py

from typing import Dict, List, Any, Optional, Callable, Set, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
import uuid
import json
from contextlib import contextmanager

class SyncDirection(Enum):
    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"

class SyncStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"

@dataclass
class SyncConfig:
    """Synchronization configuration"""
    source: str
    destination: str
    direction: SyncDirection
    interval_seconds: int
    batch_size: int = 1000
    conflict_resolution: str = "latest"
    retry_attempts: int = 3
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = None

@dataclass
class SyncOperation:
    """Individual sync operation"""
    operation_id: str
    config: SyncConfig
    status: SyncStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    items_processed: int = 0
    items_failed: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    @classmethod
    def create(cls, config: SyncConfig) -> 'SyncOperation':
        return cls(
            operation_id=str(uuid.uuid4()),
            config=config,
            status=SyncStatus.PENDING,
            start_time=datetime.utcnow(),
            metadata={}
        )

class SyncOrchestrator:
    """Orchestrates sync operations"""
    
    def __init__(self):
        self._configs: Dict[str, SyncConfig] = {}
        self._operations: Dict[str, SyncOperation] = {}
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_sync_config(
        self,
        sync_id: str,
        config: SyncConfig
    ) -> None:
        """Add sync configuration"""
        self._configs[sync_id] = config
        self.logger.info(f"Added sync config: {sync_id}")

    def register_handler(
        self,
        source: str,
        handler: Callable
    ) -> None:
        """Register sync handler"""
        self._handlers[source] = handler
        self.logger.info(f"Registered handler for {source}")

    async def start(self) -> None:
        """Start sync orchestrator"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        self.logger.info("Sync orchestrator started")

    async def stop(self) -> None:
        """Stop sync orchestrator"""
        self._running = False
        if self._scheduler_task:
            await self._scheduler_task
        self.logger.info("Sync orchestrator stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop"""
        while self._running:
            try:
                for sync_id, config in self._configs.items():
                    last_operation = self._get_last_operation(sync_id)
                    
                    if not last_operation or (
                        last_operation.end_time and
                        (datetime.utcnow() - last_operation.end_time).total_seconds() >=
                        config.interval_seconds
                    ):
                        await self.trigger_sync(sync_id)
                
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Scheduler error: {str(e)}")
                await asyncio.sleep(5)

    def _get_last_operation(
        self,
        sync_id: str
    ) -> Optional[SyncOperation]:
        """Get last sync operation"""
        operations = [
            op for op in self._operations.values()
            if op.config == self._configs[sync_id]
        ]
        return max(operations, key=lambda x: x.start_time) if operations else None

    async def trigger_sync(
        self,
        sync_id: str
    ) -> SyncOperation:
        """Trigger sync operation"""
        config = self._configs.get(sync_id)
        if not config:
            raise ValueError(f"No sync config found: {sync_id}")

        operation = SyncOperation.create(config)
        self._operations[operation.operation_id] = operation

        try:
            handler = self._handlers.get(config.source)
            if not handler:
                raise ValueError(f"No handler for source: {config.source}")

            operation.status = SyncStatus.IN_PROGRESS
            await handler(operation)
            
            operation.status = SyncStatus.COMPLETED
            operation.end_time = datetime.utcnow()
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error = str(e)
            operation.end_time = datetime.utcnow()
            raise
        finally:
            self.logger.info(
                f"Sync operation {operation.operation_id} completed with status {operation.status}"
            )

        return operation

class ChangeDetector:
    """Detects changes for synchronization"""
    
    def __init__(self):
        self._checksums: Dict[str, Dict[str, str]] = {}
        self._timestamps: Dict[str, Dict[str, datetime]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def record_state(
        self,
        source: str,
        entity_id: str,
        data: Any
    ) -> None:
        """Record entity state"""
        if source not in self._checksums:
            self._checksums[source] = {}
            self._timestamps[source] = {}

        checksum = self._calculate_checksum(data)
        self._checksums[source][entity_id] = checksum
        self._timestamps[source][entity_id] = datetime.utcnow()

    def detect_changes(
        self,
        source: str,
        entity_id: str,
        data: Any
    ) -> bool:
        """Detect if entity has changed"""
        if source not in self._checksums:
            return True

        current_checksum = self._calculate_checksum(data)
        stored_checksum = self._checksums[source].get(entity_id)
        
        return current_checksum != stored_checksum

    def _calculate_checksum(self, data: Any) -> str:
        """Calculate data checksum"""
        import hashlib
        return hashlib.md5(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

class ConflictResolver:
    """Resolves sync conflicts"""
    
    def __init__(self):
        self._strategies: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_strategy(
        self,
        name: str,
        strategy: Callable
    ) -> None:
        """Add conflict resolution strategy"""
        self._strategies[name] = strategy
        self.logger.info(f"Added conflict strategy: {name}")

    async def resolve_conflict(
        self,
        source_data: Any,
        destination_data: Any,
        strategy: str = "latest"
    ) -> Any:
        """Resolve data conflict"""
        resolver = self._strategies.get(strategy)
        if not resolver:
            raise ValueError(f"Unknown conflict strategy: {strategy}")

        try:
            result = await resolver(source_data, destination_data)
            self.logger.debug(
                f"Resolved conflict using strategy {strategy}"
            )
            return result
        except Exception as e:
            self.logger.error(f"Conflict resolution failed: {str(e)}")
            raise

class DataTransformer:
    """Transforms data during sync"""
    
    def __init__(self):
        self._transformers: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_transformer(
        self,
        data_type: str,
        transformer: Callable
    ) -> None:
        """Add data transformer"""
        if data_type not in self._transformers:
            self._transformers[data_type] = []
        self._transformers[data_type].append(transformer)
        self.logger.info(f"Added transformer for {data_type}")

    async def transform_data(
        self,
        data: Any,
        data_type: str
    ) -> Any:
        """Transform data"""
        transformers = self._transformers.get(data_type, [])
        
        transformed_data = data
        for transformer in transformers:
            try:
                transformed_data = await transformer(transformed_data)
            except Exception as e:
                self.logger.error(f"Transformation failed: {str(e)}")
                raise

        return transformed_data

class SyncValidator:
    """Validates sync data and operations"""
    
    def __init__(self):
        self._validators: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_validator(
        self,
        data_type: str,
        validator: Callable
    ) -> None:
        """Add data validator"""
        if data_type not in self._validators:
            self._validators[data_type] = []
        self._validators[data_type].append(validator)
        self.logger.info(f"Added validator for {data_type}")

    async def validate_data(
        self,
        data: Any,
        data_type: str
    ) -> bool:
        """Validate data"""
        validators = self._validators.get(data_type, [])
        
        for validator in validators:
            try:
                if not await validator(data):
                    return False
            except Exception as e:
                self.logger.error(f"Validation failed: {str(e)}")
                return False

        return True

class SyncMonitor:
    """Monitors sync operations"""
    
    def __init__(self):
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._active_operations: Set[str] = set()
        self.logger = logging.getLogger(self.__class__.__name__)

    def start_operation(
        self,
        operation: SyncOperation
    ) -> None:
        """Record operation start"""
        self._active_operations.add(operation.operation_id)
        
        if operation.config.source not in self._metrics:
            self._metrics[operation.config.source] = {
                'total_operations': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'total_items': 0,
                'failed_items': 0,
                'average_duration': 0
            }

    def end_operation(
        self,
        operation: SyncOperation
    ) -> None:
        """Record operation end"""
        self._active_operations.remove(operation.operation_id)
        
        metrics = self._metrics[operation.config.source]
        metrics['total_operations'] += 1
        metrics['total_items'] += operation.items_processed
        metrics['failed_items'] += operation.items_failed

        if operation.status == SyncStatus.COMPLETED:
            metrics['successful_operations'] += 1
        elif operation.status == SyncStatus.FAILED:
            metrics['failed_operations'] += 1

        if operation.end_time:
            duration = (operation.end_time - operation.start_time).total_seconds()
            metrics['average_duration'] = (
                (metrics['average_duration'] * (metrics['total_operations'] - 1) + duration) /
                metrics['total_operations']
            )

    def get_metrics(
        self,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get sync metrics"""
        if source:
            return self._metrics.get(source, {})
        return self._metrics

    def get_active_operations(self) -> List[str]:
        """Get active operation IDs"""
        return list(self._active_operations)

class DataSyncService:
    """Main data sync service"""
    
    def __init__(self):
        self.orchestrator = SyncOrchestrator()
        self.detector = ChangeDetector()
        self.resolver = ConflictResolver()
        self.transformer = DataTransformer()
        self.validator = SyncValidator()
        self.monitor = SyncMonitor()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start(self) -> None:
        """Start sync service"""
        await self.orchestrator.start()
        self.logger.info("Data sync service started")

    async def stop(self) -> None:
        """Stop sync service"""
        await self.orchestrator.stop()
        self.logger.info("Data sync service stopped")

    def add_sync_config(
        self,
        sync_id: str,
        source: str,
        destination: str,
        **kwargs: Any
    ) -> None:
        """Add sync configuration"""
        config = SyncConfig(
            source=source,
            destination=destination,
            **kwargs
        )
        self.orchestrator.add_sync_config(sync_id, config)

    def register_handler(
        self,
        source: str,
        handler: Callable
    ) -> None:
        """Register sync handler"""
        self.orchestrator.register_handler(source, handler)

    def add_transformer(
        self,
        data_type: str,
        transformer: Callable
    ) -> None:
        """Add data transformer"""
        self.transformer.add_transformer(data_type, transformer)

    def add_validator(
        self,
        data_type: str,
        validator: Callable
    ) -> None:
        """Add data validator"""
        self.validator.add_validator(data_type, validator)

    def add_conflict_strategy(
        self,
        name: str,
        strategy: Callable
    ) -> None:
        """Add conflict resolution strategy"""
        self.resolver.add_strategy(name, strategy)

    async def trigger_sync(
        self,
        sync_id: str
    ) -> SyncOperation:
        """Trigger manual sync"""
        return await self.orchestrator.trigger_sync(sync_id)

    def get_metrics(
        self,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get sync metrics"""
        return self.monitor.get_metrics(source)

    async def validate_data(
        self,
        data: Any,
        data_type: str
    ) -> bool:
        """Validate sync data"""
        return await self.validator.validate_data(data, data_type)

    async def transform_data(
        self,
        data: Any,
        data_type: str
    ) -> Any:
        """Transform sync data"""
        return await self.transformer.transform_data(data, data_type)

    async def resolve_conflict(
        self,
        source_data: Any,
        destination_data: Any,
        strategy: str = "latest"
    ) -> Any:
        """Resolve data conflict"""
        return await self.resolver.resolve_conflict(
            source_data,
            destination_data,
            strategy
        )