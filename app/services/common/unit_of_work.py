# app/services/common/unit_of_work.py
"""
Unit of Work pattern implementation.

Provides transaction management and repository coordination
for the service layer with SQLAlchemy.
"""
from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from typing import Any, Callable, Generic, Optional, Type, TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository

from .errors import ServiceError

logger = logging.getLogger(__name__)

TRepository = TypeVar("TRepository", bound=BaseRepository)


class TransactionError(ServiceError):
    """Raised when a database transaction fails."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message, details={"error_type": type(original_error).__name__})
        self.original_error = original_error


class UnitOfWork(AbstractContextManager["UnitOfWork"]):
    """
    Unit of Work pattern for managing database transactions.

    Coordinates repositories and ensures atomic commits/rollbacks.

    Usage:
        >>> with UnitOfWork(session_factory) as uow:
        ...     user_repo = uow.get_repo(UserRepository)
        ...     user = user_repo.get(user_id)
        ...     user.name = "New Name"
        ...     uow.commit()  # Explicit commit

    Auto-commit on success:
        >>> with UnitOfWork(session_factory) as uow:
        ...     user_repo = uow.get_repo(UserRepository)
        ...     user_repo.create(...)
        ...     # Auto-commits on __exit__ if no exception

    Nested transactions:
        >>> with UnitOfWork(session_factory) as uow:
        ...     outer_repo = uow.get_repo(UserRepository)
        ...     try:
        ...         with uow.nested() as nested_uow:
        ...             inner_repo = nested_uow.get_repo(ComplaintRepository)
        ...             # Work in nested transaction
        ...     except Exception:
        ...         # Nested transaction rolled back
        ...         pass
        ...     # Outer transaction continues
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        auto_commit: bool = True,
        auto_flush: bool = True,
    ) -> None:
        """
        Initialize Unit of Work.

        Args:
            session_factory: Factory function that returns a new Session
            auto_commit: Whether to auto-commit on successful context exit
            auto_flush: Whether to auto-flush changes before queries
        """
        self._session_factory = session_factory
        self._auto_commit = auto_commit
        self._auto_flush = auto_flush
        
        self.session: Optional[Session] = None
        self._committed: bool = False
        self._rolled_back: bool = False
        self._repo_cache: dict[Type[BaseRepository], BaseRepository] = {}

    # ------------------------------------------------------------------ #
    # Context manager protocol
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "UnitOfWork":
        """Enter the context and initialize session."""
        if self.session is not None:
            raise RuntimeError("UnitOfWork context already entered")
        
        self.session = self._session_factory()
        self.session.autoflush = self._auto_flush
        self._committed = False
        self._rolled_back = False
        self._repo_cache.clear()
        
        logger.debug("UnitOfWork session started")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit the context and handle transaction completion."""
        if self.session is None:
            return False

        try:
            if exc_type is None:
                # Success path: commit if auto-commit enabled and not already committed
                if self._auto_commit and not self._committed and not self._rolled_back:
                    try:
                        self.session.commit()
                        self._committed = True
                        logger.debug("UnitOfWork auto-committed")
                    except SQLAlchemyError as exc:
                        logger.error(f"Auto-commit failed: {exc}")
                        self.session.rollback()
                        raise TransactionError("Failed to commit transaction", exc) from exc
            else:
                # Error path: rollback if not already rolled back
                if not self._rolled_back:
                    self.session.rollback()
                    self._rolled_back = True
                    logger.warning(f"UnitOfWork rolled back due to {exc_type.__name__}")
        
        finally:
            # Always close the session
            self.session.close()
            self.session = None
            self._repo_cache.clear()
            logger.debug("UnitOfWork session closed")

        # Propagate any exception
        return False

    # ------------------------------------------------------------------ #
    # Transaction control
    # ------------------------------------------------------------------ #

    def commit(self) -> None:
        """
        Explicitly commit the current transaction.

        Raises:
            RuntimeError: If called outside of context
            TransactionError: If commit fails
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork.commit() called outside of context")
        
        if self._committed:
            logger.warning("commit() called on already-committed transaction")
            return
        
        if self._rolled_back:
            raise RuntimeError("Cannot commit a rolled-back transaction")

        try:
            self.session.commit()
            self._committed = True
            logger.debug("UnitOfWork explicitly committed")
        except SQLAlchemyError as exc:
            logger.error(f"Commit failed: {exc}")
            self.session.rollback()
            self._rolled_back = True
            raise TransactionError("Failed to commit transaction", exc) from exc

    def rollback(self) -> None:
        """
        Explicitly roll back the current transaction.

        Raises:
            RuntimeError: If called outside of context
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork.rollback() called outside of context")
        
        if self._rolled_back:
            logger.warning("rollback() called on already-rolled-back transaction")
            return

        try:
            self.session.rollback()
            self._rolled_back = True
            self._committed = False
            logger.debug("UnitOfWork explicitly rolled back")
        except SQLAlchemyError as exc:
            logger.error(f"Rollback failed: {exc}")
            raise TransactionError("Failed to rollback transaction", exc) from exc

    def flush(self) -> None:
        """
        Flush pending changes to the database without committing.

        Useful for getting database-generated values (e.g., auto-increment IDs).

        Raises:
            RuntimeError: If called outside of context
            TransactionError: If flush fails
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork.flush() called outside of context")

        try:
            self.session.flush()
            logger.debug("UnitOfWork flushed")
        except SQLAlchemyError as exc:
            logger.error(f"Flush failed: {exc}")
            raise TransactionError("Failed to flush changes", exc) from exc

    def refresh(self, instance: Any) -> None:
        """
        Refresh an instance from the database.

        Args:
            instance: ORM model instance to refresh

        Raises:
            RuntimeError: If called outside of context
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork.refresh() called outside of context")

        self.session.refresh(instance)
        logger.debug(f"Refreshed instance: {instance}")

    # ------------------------------------------------------------------ #
    # Repository factory
    # ------------------------------------------------------------------ #

    def get_repo(self, repo_cls: Type[TRepository]) -> TRepository:
        """
        Get or create a repository instance bound to this UnitOfWork's session.

        Repositories are cached per UnitOfWork instance for consistency.

        Args:
            repo_cls: Repository class to instantiate

        Returns:
            Repository instance bound to current session

        Raises:
            RuntimeError: If called outside of context

        Example:
            >>> with UnitOfWork(session_factory) as uow:
            ...     user_repo = uow.get_repo(UserRepository)
            ...     complaint_repo = uow.get_repo(ComplaintRepository)
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork.get_repo() called outside of context")

        # Return cached instance if available
        if repo_cls in self._repo_cache:
            return self._repo_cache[repo_cls]  # type: ignore

        # Create new repository instance
        repo_instance = repo_cls(self.session)
        self._repo_cache[repo_cls] = repo_instance
        
        logger.debug(f"Created repository: {repo_cls.__name__}")
        return repo_instance  # type: ignore

    # ------------------------------------------------------------------ #
    # Nested transactions (savepoints)
    # ------------------------------------------------------------------ #

    def nested(self) -> "NestedUnitOfWork":
        """
        Create a nested Unit of Work using a savepoint.

        Useful for partial rollbacks within a larger transaction.

        Returns:
            NestedUnitOfWork context manager

        Raises:
            RuntimeError: If called outside of context

        Example:
            >>> with UnitOfWork(session_factory) as uow:
            ...     user = uow.get_repo(UserRepository).create(...)
            ...     try:
            ...         with uow.nested() as nested:
            ...             # Risky operation
            ...             nested.get_repo(ComplaintRepository).create(...)
            ...     except Exception:
            ...         # Nested transaction rolled back
            ...         pass
            ...     # User creation still committed
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork.nested() called outside of context")

        return NestedUnitOfWork(self.session)

    # ------------------------------------------------------------------ #
    # Utility properties
    # ------------------------------------------------------------------ #

    @property
    def is_active(self) -> bool:
        """Check if the UnitOfWork is active (has an open session)."""
        return self.session is not None

    @property
    def is_committed(self) -> bool:
        """Check if the transaction has been committed."""
        return self._committed

    @property
    def is_rolled_back(self) -> bool:
        """Check if the transaction has been rolled back."""
        return self._rolled_back


class NestedUnitOfWork(AbstractContextManager["NestedUnitOfWork"]):
    """
    Nested Unit of Work using SQLAlchemy savepoints.

    Allows partial transaction rollbacks within a parent UnitOfWork.
    """

    def __init__(self, session: Session) -> None:
        """
        Initialize nested UnitOfWork.

        Args:
            session: Parent session to create savepoint on
        """
        self.session = session
        self._savepoint: Any = None
        self._repo_cache: dict[Type[BaseRepository], BaseRepository] = {}

    def __enter__(self) -> "NestedUnitOfWork":
        """Enter nested context and create savepoint."""
        self._savepoint = self.session.begin_nested()
        self._repo_cache.clear()
        logger.debug("Nested UnitOfWork savepoint created")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit nested context and handle savepoint."""
        try:
            if exc_type is None:
                # Commit savepoint on success
                self._savepoint.commit()
                logger.debug("Nested UnitOfWork savepoint committed")
            else:
                # Rollback savepoint on error
                self._savepoint.rollback()
                logger.warning(f"Nested UnitOfWork savepoint rolled back due to {exc_type.__name__}")
        finally:
            self._repo_cache.clear()

        # Propagate exception
        return False

    def get_repo(self, repo_cls: Type[TRepository]) -> TRepository:
        """Get repository bound to the nested session."""
        if repo_cls in self._repo_cache:
            return self._repo_cache[repo_cls]  # type: ignore

        repo_instance = repo_cls(self.session)
        self._repo_cache[repo_cls] = repo_instance
        return repo_instance  # type: ignore

    def commit(self) -> None:
        """Commit the nested transaction (savepoint)."""
        if self._savepoint:
            self._savepoint.commit()
            logger.debug("Nested UnitOfWork explicitly committed")

    def rollback(self) -> None:
        """Rollback the nested transaction (savepoint)."""
        if self._savepoint:
            self._savepoint.rollback()
            logger.debug("Nested UnitOfWork explicitly rolled back")