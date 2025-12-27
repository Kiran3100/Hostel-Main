"""
Base service class providing common functionality for all services.
"""

from typing import TypeVar, Generic, Optional, Dict, Any, Callable, List
from abc import ABC, abstractmethod
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core1.logging import get_logger
from app.repositories.base.base_repository import BaseRepository
from app.services.base.service_result import (
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)


TModel = TypeVar("TModel")
TRepo = TypeVar("TRepo", bound=BaseRepository)


class BaseService(ABC, Generic[TModel, TRepo]):
    """
    Base service with common behaviors:
    - Shared logger and db session
    - Consistent error handling via ServiceResult
    - Transaction management utilities
    - Standardized CRUD operations
    - Validation hooks
    """

    def __init__(self, repository: TRepo, db_session: Session):
        """
        Initialize base service.
        
        Args:
            repository: Repository instance for data access
            db_session: SQLAlchemy database session
        """
        self.repository: TRepo = repository
        self.db: Session = db_session
        self._logger = get_logger(self.__class__.__name__)

    # -------------------------------------------------------------------------
    # Exception & Error Handling
    # -------------------------------------------------------------------------
    
    def _handle_exception(
        self,
        exception: Exception,
        operation: str,
        entity_ref: Optional[Any] = None,
        severity: ErrorSeverity = ErrorSeverity.CRITICAL,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult:
        """
        Convert exception to a ServiceResult failure with comprehensive logging.
        
        Args:
            exception: The caught exception
            operation: Description of the operation that failed
            entity_ref: Reference to the entity involved (ID, name, etc.)
            severity: Error severity level
            additional_context: Extra context for logging/debugging
            
        Returns:
            ServiceResult with failure status and error details
        """
        context = {
            "operation": operation,
            "entity_ref": str(entity_ref) if entity_ref is not None else None,
            "exception_type": type(exception).__name__,
        }
        
        if additional_context:
            context.update(additional_context)
        
        # Log with full context
        self._logger.error(
            f"Error during {operation}: {exception}",
            exc_info=True,
            extra=context,
        )
        
        # Determine error code based on exception type
        error_code = self._map_exception_to_error_code(exception)
        
        return ServiceResult.failure(
            ServiceError(
                code=error_code,
                message=f"Failed to {operation}",
                details={
                    "error": str(exception),
                    "entity_ref": str(entity_ref) if entity_ref is not None else None,
                    "context": additional_context,
                },
                severity=severity,
            )
        )
    
    def _map_exception_to_error_code(self, exception: Exception) -> ErrorCode:
        """
        Map exception types to appropriate error codes.
        
        Args:
            exception: The exception to map
            
        Returns:
            Appropriate ErrorCode for the exception
        """
        exception_mapping = {
            ValueError: ErrorCode.VALIDATION_ERROR,
            KeyError: ErrorCode.NOT_FOUND,
            AttributeError: ErrorCode.INVALID_REFERENCE,
            PermissionError: ErrorCode.INSUFFICIENT_PERMISSIONS,
            SQLAlchemyError: ErrorCode.INTERNAL_ERROR,
        }
        
        for exc_type, error_code in exception_mapping.items():
            if isinstance(exception, exc_type):
                return error_code
        
        return ErrorCode.INTERNAL_ERROR

    # -------------------------------------------------------------------------
    # Transaction Management
    # -------------------------------------------------------------------------
    
    @contextmanager
    def transaction(self, auto_commit: bool = True):
        """
        Context manager for database transactions with automatic rollback.
        
        Args:
            auto_commit: Whether to commit automatically on success
            
        Yields:
            The database session
            
        Example:
            with self.transaction():
                self.repository.create(data)
                # automatic commit on success, rollback on exception
        """
        try:
            yield self.db
            if auto_commit:
                self._commit()
        except Exception as e:
            self._rollback()
            self._logger.error(f"Transaction failed: {e}", exc_info=True)
            raise
    
    def _commit(self) -> None:
        """Commit the current transaction with error handling."""
        try:
            self.db.commit()
            self._logger.debug("Transaction committed successfully")
        except Exception as e:
            self._logger.error(f"Commit failed: {e}", exc_info=True)
            self._rollback()
            raise

    def _rollback(self) -> None:
        """Rollback the current transaction, suppressing rollback errors."""
        try:
            self.db.rollback()
            self._logger.debug("Transaction rolled back")
        except Exception as e:
            # Log but don't raise - rollback errors should not mask original error
            self._logger.warning(f"Rollback failed: {e}")

    # -------------------------------------------------------------------------
    # Common CRUD Operations
    # -------------------------------------------------------------------------
    
    def get_by_id(self, entity_id: UUID) -> ServiceResult[TModel]:
        """
        Retrieve entity by ID.
        
        Args:
            entity_id: UUID of the entity
            
        Returns:
            ServiceResult containing the entity or error
        """
        try:
            entity = self.repository.get_by_id(entity_id)
            if not entity:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Entity with ID {entity_id} not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            return ServiceResult.success(entity)
        except Exception as e:
            return self._handle_exception(e, "get entity by ID", entity_id)
    
    def create(self, data: Dict[str, Any]) -> ServiceResult[TModel]:
        """
        Create a new entity.
        
        Args:
            data: Entity data dictionary
            
        Returns:
            ServiceResult containing the created entity or error
        """
        try:
            # Pre-create validation hook
            validation_result = self._validate_create(data)
            if validation_result and not validation_result.is_success:
                return validation_result
            
            with self.transaction():
                entity = self.repository.create(data)
                
                # Post-create hook
                self._after_create(entity)
                
            return ServiceResult.success(entity, message="Entity created successfully")
        except Exception as e:
            return self._handle_exception(e, "create entity")
    
    def update(self, entity_id: UUID, data: Dict[str, Any]) -> ServiceResult[TModel]:
        """
        Update an existing entity.
        
        Args:
            entity_id: UUID of the entity to update
            data: Update data dictionary
            
        Returns:
            ServiceResult containing the updated entity or error
        """
        try:
            # Pre-update validation hook
            validation_result = self._validate_update(entity_id, data)
            if validation_result and not validation_result.is_success:
                return validation_result
            
            with self.transaction():
                entity = self.repository.update(entity_id, data)
                if not entity:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.NOT_FOUND,
                            message=f"Entity with ID {entity_id} not found",
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                
                # Post-update hook
                self._after_update(entity, data)
                
            return ServiceResult.success(entity, message="Entity updated successfully")
        except Exception as e:
            return self._handle_exception(e, "update entity", entity_id)
    
    def delete(self, entity_id: UUID, soft: bool = True) -> ServiceResult[bool]:
        """
        Delete an entity.
        
        Args:
            entity_id: UUID of the entity to delete
            soft: Whether to perform soft delete (if supported)
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            # Pre-delete validation hook
            validation_result = self._validate_delete(entity_id)
            if validation_result and not validation_result.is_success:
                return validation_result
            
            with self.transaction():
                success = self.repository.delete(entity_id, soft=soft)
                if not success:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.NOT_FOUND,
                            message=f"Entity with ID {entity_id} not found",
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                
                # Post-delete hook
                self._after_delete(entity_id)
                
            return ServiceResult.success(
                True,
                message="Entity deleted successfully"
            )
        except Exception as e:
            return self._handle_exception(e, "delete entity", entity_id)

    # -------------------------------------------------------------------------
    # Validation Hooks (Override in subclasses)
    # -------------------------------------------------------------------------
    
    def _validate_create(self, data: Dict[str, Any]) -> Optional[ServiceResult]:
        """
        Hook for validating data before create operation.
        Override in subclasses to add custom validation.
        
        Args:
            data: Data to validate
            
        Returns:
            ServiceResult with failure if validation fails, None if valid
        """
        return None
    
    def _validate_update(self, entity_id: UUID, data: Dict[str, Any]) -> Optional[ServiceResult]:
        """
        Hook for validating data before update operation.
        Override in subclasses to add custom validation.
        
        Args:
            entity_id: ID of entity being updated
            data: Update data to validate
            
        Returns:
            ServiceResult with failure if validation fails, None if valid
        """
        return None
    
    def _validate_delete(self, entity_id: UUID) -> Optional[ServiceResult]:
        """
        Hook for validating before delete operation.
        Override in subclasses to add custom validation.
        
        Args:
            entity_id: ID of entity being deleted
            
        Returns:
            ServiceResult with failure if validation fails, None if valid
        """
        return None

    # -------------------------------------------------------------------------
    # Lifecycle Hooks (Override in subclasses)
    # -------------------------------------------------------------------------
    
    def _after_create(self, entity: TModel) -> None:
        """
        Hook called after successful entity creation.
        Override to add post-create logic (events, audit, etc.)
        
        Args:
            entity: The created entity
        """
        pass
    
    def _after_update(self, entity: TModel, changes: Dict[str, Any]) -> None:
        """
        Hook called after successful entity update.
        Override to add post-update logic (events, audit, etc.)
        
        Args:
            entity: The updated entity
            changes: Dictionary of changed fields
        """
        pass
    
    def _after_delete(self, entity_id: UUID) -> None:
        """
        Hook called after successful entity deletion.
        Override to add post-delete logic (events, audit, etc.)
        
        Args:
            entity_id: ID of the deleted entity
        """
        pass

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def _log_operation(
        self,
        operation: str,
        entity_ref: Optional[Any] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log service operation with standardized format.
        
        Args:
            operation: Description of the operation
            entity_ref: Reference to the entity involved
            extra: Additional context to log
        """
        context = {"entity_ref": str(entity_ref) if entity_ref else None}
        if extra:
            context.update(extra)
        
        self._logger.info(f"Operation: {operation}", extra=context)