# transaction_manager.py

from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import uuid
import logging
from threading import Lock
import asyncio

@dataclass
class TransactionContext:
    """Context for transaction execution"""
    transaction_id: str
    start_time: datetime
    user_id: Optional[str]
    metadata: Dict[str, Any]
    parent_id: Optional[str] = None
    isolation_level: str = "READ_COMMITTED"
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 3

    @classmethod
    def create(cls, user_id: Optional[str] = None) -> 'TransactionContext':
        return cls(
            transaction_id=str(uuid.uuid4()),
            start_time=datetime.utcnow(),
            user_id=user_id,
            metadata={}
        )

@dataclass
class TransactionLog:
    """Transaction execution log entry"""
    transaction_id: str
    operation: str
    status: str
    timestamp: datetime
    details: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: Optional[float] = None

class TransactionCoordinator:
    """Coordinates distributed transactions across services"""
    
    def __init__(self):
        self._active_transactions: Dict[str, TransactionContext] = {}
        self._locks: Dict[str, Lock] = {}
        self._logs: List[TransactionLog] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    async def prepare(self, context: TransactionContext) -> bool:
        """Prepare all participants for transaction"""
        try:
            self._active_transactions[context.transaction_id] = context
            self._locks[context.transaction_id] = Lock()
            self.logger.info(f"Prepared transaction: {context.transaction_id}")
            return True
        except Exception as e:
            self.logger.error(f"Transaction preparation failed: {str(e)}")
            return False

    async def commit(self, transaction_id: str) -> bool:
        """Commit the transaction"""
        try:
            context = self._active_transactions.get(transaction_id)
            if not context:
                raise ValueError(f"Transaction {transaction_id} not found")

            self._log_transaction(
                transaction_id,
                "COMMIT",
                "SUCCESS",
                "Transaction committed successfully"
            )
            self.cleanup(transaction_id)
            return True
        except Exception as e:
            self._log_transaction(
                transaction_id,
                "COMMIT",
                "FAILED",
                str(e)
            )
            await self.rollback(transaction_id)
            return False

    async def rollback(self, transaction_id: str) -> None:
        """Rollback the transaction"""
        try:
            context = self._active_transactions.get(transaction_id)
            if not context:
                return

            self._log_transaction(
                transaction_id,
                "ROLLBACK",
                "SUCCESS",
                "Transaction rolled back"
            )
        finally:
            self.cleanup(transaction_id)

    def cleanup(self, transaction_id: str) -> None:
        """Clean up transaction resources"""
        self._active_transactions.pop(transaction_id, None)
        lock = self._locks.pop(transaction_id, None)
        if lock:
            try:
                lock.release()
            except:
                pass

    def _log_transaction(
        self,
        transaction_id: str,
        operation: str,
        status: str,
        details: Any
    ) -> None:
        """Log transaction operation"""
        log_entry = TransactionLog(
            transaction_id=transaction_id,
            operation=operation,
            status=status,
            timestamp=datetime.utcnow(),
            details={"message": str(details)}
        )
        self._logs.append(log_entry)
        self.logger.info(f"Transaction {operation}: {transaction_id} - {status}")

class DistributedTransaction:
    """Manages distributed transaction execution"""
    
    def __init__(self):
        self.coordinator = TransactionCoordinator()
        self.logger = logging.getLogger(self.__class__.__name__)

    @contextmanager
    async def transaction_scope(
        self,
        context: Optional[TransactionContext] = None
    ) -> TransactionContext:
        """Create a transaction scope"""
        ctx = context or TransactionContext.create()
        
        try:
            await self.coordinator.prepare(ctx)
            yield ctx
            await self.coordinator.commit(ctx.transaction_id)
        except Exception as e:
            self.logger.error(f"Transaction failed: {str(e)}")
            await self.coordinator.rollback(ctx.transaction_id)
            raise
        finally:
            self.coordinator.cleanup(ctx.transaction_id)

class TransactionManager:
    """Main transaction management interface"""
    
    def __init__(self):
        self.distributed_transaction = DistributedTransaction()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._active_transactions: Dict[str, TransactionContext] = {}

    async def begin_transaction(
        self,
        user_id: Optional[str] = None,
        isolation_level: str = "READ_COMMITTED",
        timeout_seconds: int = 30
    ) -> TransactionContext:
        """Begin a new transaction"""
        context = TransactionContext.create(user_id)
        context.isolation_level = isolation_level
        context.timeout_seconds = timeout_seconds
        
        self._active_transactions[context.transaction_id] = context
        self.logger.info(f"Started transaction: {context.transaction_id}")
        return context

    async def commit_transaction(self, transaction_id: str) -> bool:
        """Commit an active transaction"""
        try:
            context = self._active_transactions.get(transaction_id)
            if not context:
                raise ValueError(f"Transaction {transaction_id} not found")

            success = await self.distributed_transaction.coordinator.commit(transaction_id)
            if success:
                self.logger.info(f"Committed transaction: {transaction_id}")
            return success
        finally:
            self._active_transactions.pop(transaction_id, None)

    async def rollback_transaction(self, transaction_id: str) -> None:
        """Rollback an active transaction"""
        try:
            context = self._active_transactions.get(transaction_id)
            if not context:
                return

            await self.distributed_transaction.coordinator.rollback(transaction_id)
            self.logger.info(f"Rolled back transaction: {transaction_id}")
        finally:
            self._active_transactions.pop(transaction_id, None)

    @contextmanager
    async def transaction(
        self,
        auto_commit: bool = True,
        **kwargs: Any
    ) -> TransactionContext:
        """Transaction context manager"""
        context = await self.begin_transaction(**kwargs)
        
        try:
            async with self.distributed_transaction.transaction_scope(context) as tx_context:
                yield tx_context
                if auto_commit:
                    await self.commit_transaction(context.transaction_id)
        except Exception as e:
            await self.rollback_transaction(context.transaction_id)
            raise

    def get_active_transactions(self) -> Dict[str, TransactionContext]:
        """Get all active transactions"""
        return self._active_transactions.copy()

    async def execute_in_transaction(
        self,
        operation: Callable,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute an operation within a transaction"""
        async with self.transaction() as context:
            try:
                result = await operation(*args, **kwargs)
                return result
            except Exception as e:
                self.logger.error(f"Operation failed in transaction: {str(e)}")
                raise