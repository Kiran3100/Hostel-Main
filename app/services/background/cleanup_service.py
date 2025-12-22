# cleanup_service.py

from typing import Dict, List, Any, Optional, Callable, Set, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
import os
import shutil
import glob
import json
from pathlib import Path

class CleanupStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class CleanupTask:
    """Cleanup task definition"""
    task_id: str
    task_type: str
    target: str
    criteria: Dict[str, Any]
    status: CleanupStatus
    items_processed: int = 0
    items_removed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    @classmethod
    def create(
        cls,
        task_type: str,
        target: str,
        criteria: Dict[str, Any]
    ) -> 'CleanupTask':
        from uuid import uuid4
        return cls(
            task_id=str(uuid4()),
            task_type=task_type,
            target=target,
            criteria=criteria,
            status=CleanupStatus.PENDING,
            metadata={}
        )

class OrphanCleaner:
    """Cleans orphaned resources"""
    
    def __init__(self):
        self._cleaners: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_cleaner(
        self,
        resource_type: str,
        cleaner: Callable
    ) -> None:
        """Register resource cleaner"""
        self._cleaners[resource_type] = cleaner
        self.logger.info(f"Registered cleaner for {resource_type}")

    async def cleanup_orphans(
        self,
        resource_type: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Clean orphaned resources"""
        cleaner = self._cleaners.get(resource_type)
        if not cleaner:
            raise ValueError(f"No cleaner for {resource_type}")

        try:
            result = await cleaner(criteria)
            self.logger.info(
                f"Cleaned {result.get('removed', 0)} orphaned {resource_type}"
            )
            return result
        except Exception as e:
            self.logger.error(f"Orphan cleanup failed: {str(e)}")
            raise

class ArchivalManager:
    """Manages data archival"""
    
    def __init__(self):
        self._archive_path: Optional[str] = None
        self._archivers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def configure(
        self,
        archive_path: str
    ) -> None:
        """Configure archive location"""
        self._archive_path = archive_path
        os.makedirs(archive_path, exist_ok=True)
        self.logger.info(f"Configured archive path: {archive_path}")

    def register_archiver(
        self,
        data_type: str,
        archiver: Callable
    ) -> None:
        """Register data archiver"""
        self._archivers[data_type] = archiver
        self.logger.info(f"Registered archiver for {data_type}")

    async def archive_data(
        self,
        data_type: str,
        data: Any,
        metadata: Dict[str, Any]
    ) -> str:
        """Archive data"""
        if not self._archive_path:
            raise ValueError("Archive path not configured")

        archiver = self._archivers.get(data_type)
        if not archiver:
            raise ValueError(f"No archiver for {data_type}")

        try:
            archive_id = await archiver(data, self._archive_path, metadata)
            self.logger.info(f"Archived {data_type} with ID {archive_id}")
            return archive_id
        except Exception as e:
            self.logger.error(f"Archival failed: {str(e)}")
            raise

class DataRetentionEnforcer:
    """Enforces data retention policies"""
    
    def __init__(self):
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_policy(
        self,
        data_type: str,
        retention_days: int,
        archive: bool = False
    ) -> None:
        """Set retention policy"""
        self._policies[data_type] = {
            'retention_days': retention_days,
            'archive': archive
        }
        self.logger.info(
            f"Set {retention_days} days retention for {data_type}"
        )

    def register_handler(
        self,
        data_type: str,
        handler: Callable
    ) -> None:
        """Register retention handler"""
        self._handlers[data_type] = handler
        self.logger.info(f"Registered handler for {data_type}")

    async def enforce_retention(
        self,
        data_type: str
    ) -> Dict[str, Any]:
        """Enforce retention policy"""
        policy = self._policies.get(data_type)
        if not policy:
            raise ValueError(f"No policy for {data_type}")

        handler = self._handlers.get(data_type)
        if not handler:
            raise ValueError(f"No handler for {data_type}")

        try:
            cutoff_date = datetime.utcnow() - timedelta(
                days=policy['retention_days']
            )
            result = await handler(cutoff_date, policy['archive'])
            self.logger.info(
                f"Enforced retention for {data_type}: {result}"
            )
            return result
        except Exception as e:
            self.logger.error(f"Retention enforcement failed: {str(e)}")
            raise

class TempFileRemover:
    """Removes temporary files"""
    
    def __init__(self):
        self._temp_dirs: List[str] = []
        self._patterns: Dict[str, str] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_temp_directory(
        self,
        directory: str
    ) -> None:
        """Add temporary directory"""
        self._temp_dirs.append(directory)
        self.logger.info(f"Added temp directory: {directory}")

    def add_pattern(
        self,
        name: str,
        pattern: str
    ) -> None:
        """Add file pattern"""
        self._patterns[name] = pattern
        self.logger.info(f"Added pattern {name}: {pattern}")

    async def cleanup_files(
        self,
        older_than_days: int = 1
    ) -> Dict[str, int]:
        """Clean up temporary files"""
        results = {'total': 0}
        cutoff_time = datetime.utcnow() - timedelta(days=older_than_days)

        for directory in self._temp_dirs:
            for name, pattern in self._patterns.items():
                try:
                    path_pattern = os.path.join(directory, pattern)
                    count = 0
                    
                    for filepath in glob.glob(path_pattern):
                        if os.path.getmtime(filepath) < cutoff_time.timestamp():
                            os.remove(filepath)
                            count += 1
                    
                    results[name] = count
                    results['total'] += count
                except Exception as e:
                    self.logger.error(
                        f"Failed to clean {name} in {directory}: {str(e)}"
                    )

        self.logger.info(f"Removed {results['total']} temporary files")
        return results

class SessionCleaner:
    """Cleans expired sessions"""
    
    def __init__(self):
        self._cleaners: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_cleaner(
        self,
        session_type: str,
        cleaner: Callable
    ) -> None:
        """Register session cleaner"""
        self._cleaners[session_type] = cleaner
        self.logger.info(f"Registered cleaner for {session_type}")

    async def cleanup_sessions(
        self,
        session_type: str,
        expired_before: datetime
    ) -> int:
        """Clean expired sessions"""
        cleaner = self._cleaners.get(session_type)
        if not cleaner:
            raise ValueError(f"No cleaner for {session_type}")

        try:
            count = await cleaner(expired_before)
            self.logger.info(
                f"Cleaned {count} expired {session_type} sessions"
            )
            return count
        except Exception as e:
            self.logger.error(f"Session cleanup failed: {str(e)}")
            raise

class LogRotator:
    """Rotates and archives logs"""
    
    def __init__(self):
        self._log_configs: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_log_config(
        self,
        log_type: str,
        file_pattern: str,
        max_size_mb: int,
        retention_days: int,
        compress: bool = True
    ) -> None:
        """Add log rotation config"""
        self._log_configs[log_type] = {
            'file_pattern': file_pattern,
            'max_size_mb': max_size_mb,
            'retention_days': retention_days,
            'compress': compress
        }
        self.logger.info(f"Added config for {log_type} logs")

    async def rotate_logs(
        self,
        log_type: str
    ) -> Dict[str, Any]:
        """Rotate logs"""
        config = self._log_configs.get(log_type)
        if not config:
            raise ValueError(f"No config for {log_type}")

        try:
            results = {
                'rotated': 0,
                'archived': 0,
                'deleted': 0
            }

            for filepath in glob.glob(config['file_pattern']):
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                if size_mb >= config['max_size_mb']:
                    # Rotate file
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    new_path = f"{filepath}.{timestamp}"
                    os.rename(filepath, new_path)
                    results['rotated'] += 1

                    # Compress if needed
                    if config['compress']:
                        import gzip
                        with open(new_path, 'rb') as f_in:
                            with gzip.open(f"{new_path}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(new_path)
                        results['archived'] += 1

            # Clean old rotated logs
            cutoff_time = datetime.utcnow() - timedelta(
                days=config['retention_days']
            )
            pattern = f"{config['file_pattern']}.*"
            
            for filepath in glob.glob(pattern):
                if os.path.getmtime(filepath) < cutoff_time.timestamp():
                    os.remove(filepath)
                    results['deleted'] += 1

            self.logger.info(f"Rotated {log_type} logs: {results}")
            return results
        except Exception as e:
            self.logger.error(f"Log rotation failed: {str(e)}")
            raise

class StorageOptimizer:
    """Optimizes storage usage"""
    
    def __init__(self):
        self._optimizers: Dict[str, Callable] = {}
        self._thresholds: Dict[str, float] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_optimizer(
        self,
        storage_type: str,
        optimizer: Callable,
        threshold_percent: float = 90.0
    ) -> None:
        """Register storage optimizer"""
        self._optimizers[storage_type] = optimizer
        self._thresholds[storage_type] = threshold_percent
        self.logger.info(
            f"Registered optimizer for {storage_type} "
            f"(threshold: {threshold_percent}%)"
        )

    async def check_storage(
        self,
        storage_type: str
    ) -> Dict[str, Any]:
        """Check storage usage"""
        # Implement storage check
        return {}

    async def optimize_storage(
        self,
        storage_type: str
    ) -> Dict[str, Any]:
        """Optimize storage usage"""
        optimizer = self._optimizers.get(storage_type)
        if not optimizer:
            raise ValueError(f"No optimizer for {storage_type}")

        try:
            usage = await self.check_storage(storage_type)
            if usage.get('percent_used', 0) > self._thresholds[storage_type]:
                result = await optimizer(usage)
                self.logger.info(
                    f"Optimized {storage_type} storage: {result}"
                )
                return result
            return {'optimized': False, 'reason': 'threshold not reached'}
        except Exception as e:
            self.logger.error(f"Storage optimization failed: {str(e)}")
            raise

class CleanupService:
    """Main cleanup service"""
    
    def __init__(self):
        self.orphan_cleaner = OrphanCleaner()
        self.archival_manager = ArchivalManager()
        self.retention_enforcer = DataRetentionEnforcer()
        self.temp_remover = TempFileRemover()
        self.session_cleaner = SessionCleaner()
        self.log_rotator = LogRotator()
        self.storage_optimizer = StorageOptimizer()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start(self) -> None:
        """Start cleanup service"""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._run_cleanup())
        self.logger.info("Cleanup service started")

    async def stop(self) -> None:
        """Stop cleanup service"""
        self._running = False
        if self._cleanup_task:
            await self._cleanup_task
        self.logger.info("Cleanup service stopped")

    async def _run_cleanup(self) -> None:
        """Main cleanup loop"""
        while self._running:
            try:
                # Run various cleanup tasks
                await self._cleanup_temp_files()
                await self._cleanup_sessions()
                await self._rotate_logs()
                await self._optimize_storage()
                
                # Sleep between cleanup cycles
                await asyncio.sleep(3600)  # 1 hour
            except Exception as e:
                self.logger.error(f"Cleanup cycle failed: {str(e)}")
                await asyncio.sleep(300)  # 5 minutes on error

    async def _cleanup_temp_files(self) -> None:
        """Clean temporary files"""
        await self.temp_remover.cleanup_files()

    async def _cleanup_sessions(self) -> None:
        """Clean expired sessions"""
        expired_before = datetime.utcnow() - timedelta(days=1)
        for session_type in self.session_cleaner._cleaners:
            await self.session_cleaner.cleanup_sessions(
                session_type,
                expired_before
            )

    async def _rotate_logs(self) -> None:
        """Rotate logs"""
        for log_type in self.log_rotator._log_configs:
            await self.log_rotator.rotate_logs(log_type)

    async def _optimize_storage(self) -> None:
        """Optimize storage"""
        for storage_type in self.storage_optimizer._optimizers:
            await self.storage_optimizer.optimize_storage(storage_type)

    async def cleanup_orphans(
        self,
        resource_type: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Clean orphaned resources"""
        return await self.orphan_cleaner.cleanup_orphans(
            resource_type,
            criteria
        )

    async def archive_data(
        self,
        data_type: str,
        data: Any,
        metadata: Dict[str, Any]
    ) -> str:
        """Archive data"""
        return await self.archival_manager.archive_data(
            data_type,
            data,
            metadata
        )

    async def enforce_retention(
        self,
        data_type: str
    ) -> Dict[str, Any]:
        """Enforce data retention"""
        return await self.retention_enforcer.enforce_retention(data_type)