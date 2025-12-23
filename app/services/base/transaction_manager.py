"""
Transaction manager utilities for service layer operations.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Optional, Callable, Any, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger


@dataclass
class TransactionContext:
    """Context information for a transaction."""
    
    transaction_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime = field(default_factory=datetime.utcnow)
    committed: bool = False
    rolled_back: bool = False
    completed_at: Optional[datetime] = None
    error: Optional[Exception] = None
    savepoints: List[str] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get transaction duration in milliseconds."""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if transaction is completed."""
        return self.committed or self.rolled_back


class TransactionManager:
    """
    Advanced transaction management for service layer with:
    - Nested transaction support
    - Savepoint management
    - Transaction monitoring
    - Error handling and logging
    - Transaction hooks
    """

    def __init__(self, db_session: Session):
        """
        Initialize transaction manager.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self._logger = get_logger(self.__class__.__name__)
        self._active_transactions: List[TransactionContext] = []
        
        # Hooks
        self._before_commit_hooks: List[Callable[[TransactionContext], None]] = []
        self._after_commit_hooks: List[Callable[[TransactionContext], None]] = []
        self._on_rollback_hooks: List[Callable[[TransactionContext, Exception], None]] = []

    # -------------------------------------------------------------------------
    # Core Transaction Management
    # -------------------------------------------------------------------------

    @contextmanager
    def start(
        self,
        auto_commit: bool = True,
        isolation_level: Optional[str] = None,
    ) -> Iterator[TransactionContext]:
        """
        Start a new transaction.
        
        Args:
            auto_commit: Automatically commit on success
            isolation_level: Transaction isolation level
            
        Yields:
            TransactionContext instance
            
        Example:
            with transaction_manager.start() as ctx:
                # perform operations
                # automatic commit on success, rollback on exception
        """
        ctx = TransactionContext()
        self._active_transactions.append(ctx)
        
        # Set isolation level if specified
        if isolation_level:
            self.db.connection().execution_options(isolation_level=isolation_level)
        
        self._logger.debug(
            f"Transaction started: {ctx.transaction_id}",
            extra={
                "transaction_id": ctx.transaction_id,
                "auto_commit": auto_commit,
                "isolation_level": isolation_level,
            }
        )
        
        try:
            yield ctx
            
            if auto_commit and not ctx.committed and not ctx.rolled_back:
                self._commit(ctx)
                
        except Exception as exc:
            ctx.error = exc
            
            if not ctx.rolled_back:
                self._rollback(ctx, exc)
            
            raise
            
        finally:
            ctx.completed_at = datetime.utcnow()
            self._active_transactions.remove(ctx)
            
            self._logger.debug(
                f"Transaction completed: {ctx.transaction_id} "
                f"({'committed' if ctx.committed else 'rolled back'}) "
                f"in {ctx.duration_ms:.2f}ms",
                extra={
                    "transaction_id": ctx.transaction_id,
                    "committed": ctx.committed,
                    "rolled_back": ctx.rolled_back,
                    "duration_ms": ctx.duration_ms,
                }
            )

    @contextmanager
    def savepoint(self, name: Optional[str] = None) -> Iterator[str]:
        """
        Create a savepoint within a transaction.
        
        Args:
            name: Optional savepoint name
            
        Yields:
            Savepoint name
            
        Example:
            with transaction_manager.start() as ctx:
                # some operations
                with transaction_manager.savepoint("before_update"):
                    # risky operation
                    # will rollback to savepoint on error
        """
        savepoint_name = name or f"sp_{uuid4().hex[:8]}"
        
        try:
            self.db.begin_nested()
            
            if self._active_transactions:
                self._active_transactions[-1].savepoints.append(savepoint_name)
            
            self._logger.debug(f"Savepoint created: {savepoint_name}")
            
            yield savepoint_name
            
        except Exception as exc:
            self._logger.warning(
                f"Rolling back to savepoint: {savepoint_name}",
                extra={"savepoint": savepoint_name, "error": str(exc)}
            )
            self.db.rollback()
            raise

    def _commit(self, ctx: TransactionContext) -> None:
        """
        Commit the transaction.
        
        Args:
            ctx: Transaction context
        """
        try:
            # Execute before-commit hooks
            for hook in self._before_commit_hooks:
                try:
                    hook(ctx)
                except Exception as e:
                    self._logger.error(f"Before-commit hook failed: {e}", exc_info=True)
            
            self.db.commit()
            ctx.committed = True
            
            self._logger.info(
                f"Transaction committed: {ctx.transaction_id}",
                extra={"transaction_id": ctx.transaction_id}
            )
            
            # Execute after-commit hooks
            for hook in self._after_commit_hooks:
                try:
                    hook(ctx)
                except Exception as e:
                    self._logger.error(f"After-commit hook failed: {e}", exc_info=True)
                    
        except SQLAlchemyError as e:
            self._logger.error(
                f"Commit failed for transaction {ctx.transaction_id}: {e}",
                exc_info=True,
                extra={"transaction_id": ctx.transaction_id}
            )
            self._rollback(ctx, e)
            raise

    def _rollback(self, ctx: TransactionContext, exc: Exception) -> None:
        """
        Rollback the transaction.
        
        Args:
            ctx: Transaction context
            exc: Exception that caused rollback
        """
        try:
            self.db.rollback()
            ctx.rolled_back = True
            ctx.error = exc
            
            self._logger.warning(
                f"Transaction rolled back: {ctx.transaction_id} - {exc}",
                extra={
                    "transaction_id": ctx.transaction_id,
                    "error": str(exc),
                }
            )
            
            # Execute rollback hooks
            for hook in self._on_rollback_hooks:
                try:
                    hook(ctx, exc)
                except Exception as e:
                    self._logger.error(f"Rollback hook failed: {e}", exc_info=True)
                    
        except Exception as e:
            # Swallow rollback errors to avoid masking original exception
            self._logger.error(
                f"Rollback failed for transaction {ctx.transaction_id}: {e}",
                exc_info=True
            )

    # -------------------------------------------------------------------------
    # Hook Management
    # -------------------------------------------------------------------------

    def add_before_commit_hook(self, hook: Callable[[TransactionContext], None]) -> None:
        """
        Add hook to execute before commit.
        
        Args:
            hook: Callable that takes TransactionContext
        """
        self._before_commit_hooks.append(hook)
        self._logger.debug(f"Added before-commit hook: {hook.__name__}")

    def add_after_commit_hook(self, hook: Callable[[TransactionContext], None]) -> None:
        """
        Add hook to execute after commit.
        
        Args:
            hook: Callable that takes TransactionContext
        """
        self._after_commit_hooks.append(hook)
        self._logger.debug(f"Added after-commit hook: {hook.__name__}")

    def add_on_rollback_hook(
        self,
        hook: Callable[[TransactionContext, Exception], None]
    ) -> None:
        """
        Add hook to execute on rollback.
        
        Args:
            hook: Callable that takes TransactionContext and Exception
        """
        self._on_rollback_hooks.append(hook)
        self._logger.debug(f"Added rollback hook: {hook.__name__}")

    def clear_hooks(self) -> None:
        """Clear all registered hooks."""
        self._before_commit_hooks.clear()
        self._after_commit_hooks.clear()
        self._on_rollback_hooks.clear()
        self._logger.debug("Cleared all transaction hooks")

    # -------------------------------------------------------------------------
    # Transaction Monitoring
    # -------------------------------------------------------------------------

    def get_active_transactions(self) -> List[TransactionContext]:
        """
        Get list of currently active transactions.
        
        Returns:
            List of active TransactionContext instances
        """
        return self._active_transactions.copy()

    def get_transaction_stats(self) -> dict:
        """
        Get transaction statistics.
        
        Returns:
            Dictionary with transaction stats
        """
        return {
            "active_count": len(self._active_transactions),
            "hooks": {
                "before_commit": len(self._before_commit_hooks),
                "after_commit": len(self._after_commit_hooks),
                "on_rollback": len(self._on_rollback_hooks),
            }
        }


class TransactionManagerFactory:
    """Factory for creating transaction managers."""
    
    @staticmethod
    def create(db_session: Session) -> TransactionManager:
        """
        Create a new transaction manager.
        
        Args:
            db_session: Database session
            
        Returns:
            TransactionManager instance
        """
        return TransactionManager(db_session)