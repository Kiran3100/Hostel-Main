"""
Base repository with standardized CRUD operations, transaction management, and error handling.

Provides foundation for all domain repositories with type safety,
audit integration, and multi-tenant support.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import and_, or_, func, select, update, delete
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.inspection import inspect

from app.models.base import BaseModel, SoftDeleteModel, TenantModel
from app.core.logging import get_logger
from app.core.exceptions import (
    RepositoryError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    OptimisticLockError,
    ValidationError
)

logger = get_logger(__name__)

# Type variable for model classes
ModelType = TypeVar("ModelType", bound=BaseModel)


class AuditContext:
    """Context for audit trail information."""
    
    def __init__(
        self,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.ip_address = ip_address
        self.action = action
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()


class BaseRepository(Generic[ModelType]):
    """
    Abstract base repository with standardized operations.
    
    Provides CRUD operations, transaction management, and error handling
    for all domain repositories.
    """
    
    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize repository.
        
        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db
        self._cache = None  # Will be injected by CachingRepository
        self._is_soft_delete = issubclass(model, SoftDeleteModel)
        self._is_tenant_model = issubclass(model, TenantModel)
    
    # ==================== Transaction Management ====================
    
    @contextmanager
    def transaction(self):
        """
        Transaction context manager with automatic rollback.
        
        Usage:
            with repository.transaction():
                repository.create(entity)
                repository.update(id, data)
        """
        try:
            yield self.db
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Transaction rollback: {str(e)}", exc_info=True)
            raise RepositoryError(f"Transaction failed: {str(e)}") from e
    
    def begin_transaction(self):
        """Begin new transaction."""
        self.db.begin()
    
    def commit(self):
        """Commit current transaction."""
        try:
            self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Commit failed: {str(e)}") from e
    
    def rollback(self):
        """Rollback current transaction."""
        self.db.rollback()
    
    # ==================== Create Operations ====================
    
    def create(
        self,
        entity: ModelType,
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Create new entity with audit logging.
        
        Args:
            entity: Entity to create
            audit_context: Audit information
            commit: Whether to commit immediately
            
        Returns:
            Created entity
            
        Raises:
            EntityAlreadyExistsError: If entity already exists
            ValidationError: If validation fails
        """
        try:
            # Apply audit context
            if audit_context and hasattr(entity, 'created_by'):
                entity.created_by = audit_context.user_id
            
            # Add to session
            self.db.add(entity)
            
            if commit:
                self.db.commit()
                self.db.refresh(entity)
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate_entity(self.model.__tablename__, entity.id)
            else:
                self.db.flush()
            
            logger.info(f"Created {self.model.__name__} with id: {entity.id}")
            return entity
            
        except IntegrityError as e:
            self.db.rollback()
            raise EntityAlreadyExistsError(
                f"{self.model.__name__} already exists"
            ) from e
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Create failed: {str(e)}") from e
    
    def create_many(
        self,
        entities: List[ModelType],
        audit_context: Optional[AuditContext] = None,
        batch_size: int = 1000
    ) -> List[ModelType]:
        """
        Bulk create with batch processing.
        
        Args:
            entities: List of entities to create
            audit_context: Audit information
            batch_size: Number of entities per batch
            
        Returns:
            List of created entities
        """
        created_entities = []
        
        try:
            # Process in batches
            for i in range(0, len(entities), batch_size):
                batch = entities[i:i + batch_size]
                
                # Apply audit context to batch
                if audit_context:
                    for entity in batch:
                        if hasattr(entity, 'created_by'):
                            entity.created_by = audit_context.user_id
                
                # Bulk insert
                self.db.bulk_save_objects(batch, return_defaults=True)
                self.db.flush()
                
                created_entities.extend(batch)
            
            self.db.commit()
            
            # Invalidate cache
            if self._cache:
                self._cache.invalidate_pattern(f"{self.model.__tablename__}:*")
            
            logger.info(f"Bulk created {len(created_entities)} {self.model.__name__} entities")
            return created_entities
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Bulk create failed: {str(e)}") from e
    
    # ==================== Read Operations ====================
    
    def find_by_id(
        self,
        id: Union[UUID, int],
        include_deleted: bool = False
    ) -> Optional[ModelType]:
        """
        Find entity by ID.
        
        Args:
            id: Entity ID
            include_deleted: Include soft-deleted entities
            
        Returns:
            Entity or None
        """
        try:
            query = self.db.query(self.model).filter(self.model.id == id)
            
            # Apply soft delete filter
            if self._is_soft_delete and not include_deleted:
                query = query.filter(self.model.is_deleted == False)
            
            return query.first()
            
        except SQLAlchemyError as e:
            raise RepositoryError(f"Find by ID failed: {str(e)}") from e
    
    def get_by_id(
        self,
        id: Union[UUID, int],
        include_deleted: bool = False
    ) -> ModelType:
        """
        Get entity by ID or raise exception.
        
        Args:
            id: Entity ID
            include_deleted: Include soft-deleted entities
            
        Returns:
            Entity
            
        Raises:
            EntityNotFoundError: If entity not found
        """
        entity = self.find_by_id(id, include_deleted)
        if not entity:
            raise EntityNotFoundError(
                f"{self.model.__name__} with id {id} not found"
            )
        return entity
    
    def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[ModelType]:
        """
        Find all entities with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records
            include_deleted: Include soft-deleted entities
            
        Returns:
            List of entities
        """
        try:
            query = self.db.query(self.model)
            
            # Apply soft delete filter
            if self._is_soft_delete and not include_deleted:
                query = query.filter(self.model.is_deleted == False)
            
            return query.offset(skip).limit(limit).all()
            
        except SQLAlchemyError as e:
            raise RepositoryError(f"Find all failed: {str(e)}") from e
    
    def find_by_criteria(
        self,
        criteria: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[List[str]] = None,
        include_deleted: bool = False
    ) -> List[ModelType]:
        """
        Find entities matching criteria.
        
        Args:
            criteria: Filter criteria as key-value pairs
            skip: Number of records to skip
            limit: Maximum number of records
            order_by: List of fields to order by (prefix with - for desc)
            include_deleted: Include soft-deleted entities
            
        Returns:
            List of matching entities
        """
        try:
            query = self.db.query(self.model)
            
            # Apply criteria filters
            for key, value in criteria.items():
                if hasattr(self.model, key):
                    column = getattr(self.model, key)
                    if isinstance(value, (list, tuple)):
                        query = query.filter(column.in_(value))
                    else:
                        query = query.filter(column == value)
            
            # Apply soft delete filter
            if self._is_soft_delete and not include_deleted:
                query = query.filter(self.model.is_deleted == False)
            
            # Apply ordering
            if order_by:
                for field in order_by:
                    if field.startswith('-'):
                        query = query.order_by(getattr(self.model, field[1:]).desc())
                    else:
                        query = query.order_by(getattr(self.model, field))
            
            return query.offset(skip).limit(limit).all()
            
        except SQLAlchemyError as e:
            raise RepositoryError(f"Find by criteria failed: {str(e)}") from e
    
    def find_one_by_criteria(
        self,
        criteria: Dict[str, Any],
        include_deleted: bool = False
    ) -> Optional[ModelType]:
        """
        Find single entity matching criteria.
        
        Args:
            criteria: Filter criteria
            include_deleted: Include soft-deleted entities
            
        Returns:
            Entity or None
        """
        results = self.find_by_criteria(criteria, limit=1, include_deleted=include_deleted)
        return results[0] if results else None
    
    # ==================== Update Operations ====================
    
    def update(
        self,
        id: Union[UUID, int],
        data: Dict[str, Any],
        audit_context: Optional[AuditContext] = None,
        version: Optional[int] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Update entity with version control.
        
        Args:
            id: Entity ID
            data: Update data
            audit_context: Audit information
            version: Expected version for optimistic locking
            commit: Whether to commit immediately
            
        Returns:
            Updated entity
            
        Raises:
            EntityNotFoundError: If entity not found
            OptimisticLockError: If version mismatch
        """
        try:
            entity = self.get_by_id(id)
            
            # Check version for optimistic locking
            if version is not None and hasattr(entity, 'version'):
                if entity.version != version:
                    raise OptimisticLockError(
                        f"Version mismatch: expected {version}, got {entity.version}"
                    )
            
            # Apply updates
            for key, value in data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            # Apply audit context
            if audit_context and hasattr(entity, 'updated_by'):
                entity.updated_by = audit_context.user_id
            
            # Increment version
            if hasattr(entity, 'version'):
                entity.version += 1
            
            if commit:
                self.db.commit()
                self.db.refresh(entity)
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate_entity(self.model.__tablename__, id)
            else:
                self.db.flush()
            
            logger.info(f"Updated {self.model.__name__} with id: {id}")
            return entity
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Update failed: {str(e)}") from e
    
    def update_many(
        self,
        criteria: Dict[str, Any],
        data: Dict[str, Any],
        audit_context: Optional[AuditContext] = None
    ) -> int:
        """
        Bulk update entities matching criteria.
        
        Args:
            criteria: Filter criteria
            data: Update data
            audit_context: Audit information
            
        Returns:
            Number of updated entities
        """
        try:
            query = self.db.query(self.model)
            
            # Apply criteria
            for key, value in criteria.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
            
            # Apply soft delete filter
            if self._is_soft_delete:
                query = query.filter(self.model.is_deleted == False)
            
            # Add audit info to update data
            update_data = data.copy()
            if audit_context and hasattr(self.model, 'updated_by'):
                update_data['updated_by'] = audit_context.user_id
            if hasattr(self.model, 'updated_at'):
                update_data['updated_at'] = datetime.utcnow()
            
            # Execute bulk update
            count = query.update(update_data, synchronize_session='fetch')
            self.db.commit()
            
            # Invalidate cache
            if self._cache:
                self._cache.invalidate_pattern(f"{self.model.__tablename__}:*")
            
            logger.info(f"Bulk updated {count} {self.model.__name__} entities")
            return count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Bulk update failed: {str(e)}") from e
    
    # ==================== Delete Operations ====================
    
    def delete(
        self,
        id: Union[UUID, int],
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> bool:
        """
        Hard delete entity.
        
        Args:
            id: Entity ID
            audit_context: Audit information
            commit: Whether to commit immediately
            
        Returns:
            True if deleted, False if not found
        """
        try:
            entity = self.find_by_id(id, include_deleted=True)
            if not entity:
                return False
            
            self.db.delete(entity)
            
            if commit:
                self.db.commit()
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate_entity(self.model.__tablename__, id)
            else:
                self.db.flush()
            
            logger.info(f"Deleted {self.model.__name__} with id: {id}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Delete failed: {str(e)}") from e
    
    def soft_delete(
        self,
        id: Union[UUID, int],
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Soft delete entity with audit trail.
        
        Args:
            id: Entity ID
            audit_context: Audit information
            commit: Whether to commit immediately
            
        Returns:
            Soft-deleted entity
            
        Raises:
            EntityNotFoundError: If entity not found
            ValidationError: If model doesn't support soft delete
        """
        if not self._is_soft_delete:
            raise ValidationError(
                f"{self.model.__name__} doesn't support soft delete"
            )
        
        try:
            entity = self.get_by_id(id)
            
            entity.is_deleted = True
            entity.deleted_at = datetime.utcnow()
            if audit_context and hasattr(entity, 'deleted_by'):
                entity.deleted_by = audit_context.user_id
            
            if commit:
                self.db.commit()
                self.db.refresh(entity)
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate_entity(self.model.__tablename__, id)
            else:
                self.db.flush()
            
            logger.info(f"Soft deleted {self.model.__name__} with id: {id}")
            return entity
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Soft delete failed: {str(e)}") from e
    
    def restore(
        self,
        id: Union[UUID, int],
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Restore soft-deleted entity.
        
        Args:
            id: Entity ID
            audit_context: Audit information
            commit: Whether to commit immediately
            
        Returns:
            Restored entity
        """
        if not self._is_soft_delete:
            raise ValidationError(
                f"{self.model.__name__} doesn't support soft delete"
            )
        
        try:
            entity = self.get_by_id(id, include_deleted=True)
            
            entity.is_deleted = False
            entity.deleted_at = None
            if hasattr(entity, 'deleted_by'):
                entity.deleted_by = None
            
            if commit:
                self.db.commit()
                self.db.refresh(entity)
                
                # Invalidate cache
                if self._cache:
                    self._cache.invalidate_entity(self.model.__tablename__, id)
            else:
                self.db.flush()
            
            logger.info(f"Restored {self.model.__name__} with id: {id}")
            return entity
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RepositoryError(f"Restore failed: {str(e)}") from e
    
    # ==================== Count Operations ====================
    
    def count(
        self,
        criteria: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False
    ) -> int:
        """
        Count entities matching criteria.
        
        Args:
            criteria: Filter criteria
            include_deleted: Include soft-deleted entities
            
        Returns:
            Count of matching entities
        """
        try:
            query = self.db.query(func.count(self.model.id))
            
            # Apply criteria
            if criteria:
                for key, value in criteria.items():
                    if hasattr(self.model, key):
                        column = getattr(self.model, key)
                        if isinstance(value, (list, tuple)):
                            query = query.filter(column.in_(value))
                        else:
                            query = query.filter(column == value)
            
            # Apply soft delete filter
            if self._is_soft_delete and not include_deleted:
                query = query.filter(self.model.is_deleted == False)
            
            return query.scalar()
            
        except SQLAlchemyError as e:
            raise RepositoryError(f"Count failed: {str(e)}") from e
    
    def exists(
        self,
        criteria: Dict[str, Any],
        include_deleted: bool = False
    ) -> bool:
        """
        Check if entity exists matching criteria.
        
        Args:
            criteria: Filter criteria
            include_deleted: Include soft-deleted entities
            
        Returns:
            True if exists, False otherwise
        """
        return self.count(criteria, include_deleted) > 0
    
    # ==================== Multi-Tenant Operations ====================
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[ModelType]:
        """
        Find entities by hostel (tenant).
        
        Args:
            hostel_id: Hostel ID
            skip: Number of records to skip
            limit: Maximum number of records
            include_deleted: Include soft-deleted entities
            
        Returns:
            List of entities for hostel
        """
        if not self._is_tenant_model:
            raise ValidationError(
                f"{self.model.__name__} is not a tenant model"
            )
        
        return self.find_by_criteria(
            {"hostel_id": hostel_id},
            skip=skip,
            limit=limit,
            include_deleted=include_deleted
        )
    
    def count_by_hostel(
        self,
        hostel_id: UUID,
        include_deleted: bool = False
    ) -> int:
        """
        Count entities for hostel.
        
        Args:
            hostel_id: Hostel ID
            include_deleted: Include soft-deleted entities
            
        Returns:
            Count of entities
        """
        if not self._is_tenant_model:
            raise ValidationError(
                f"{self.model.__name__} is not a tenant model"
            )
        
        return self.count({"hostel_id": hostel_id}, include_deleted)
    
        # ==================== Pagination Methods ====================
    
    def paginate_query(
        self,
        query: Query,
        pagination: 'PaginationParams'
    ) -> 'PaginatedResult[ModelType]':
        """
        Paginate a query using pagination parameters.
        
        Args:
            query: SQLAlchemy query to paginate
            pagination: Pagination parameters
            
        Returns:
            Paginated result
        """
        try:
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            if pagination.skip:
                query = query.offset(pagination.skip)
            if pagination.limit:
                query = query.limit(pagination.limit)
            
            # Apply ordering if specified
            if pagination.order_by and hasattr(self.model, pagination.order_by):
                order_column = getattr(self.model, pagination.order_by)
                if pagination.order_direction.lower() == 'desc':
                    query = query.order_by(order_column.desc())
                else:
                    query = query.order_by(order_column.asc())
            
            # Execute query
            items = query.all()
            
            # Create pagination result
            from app.repositories.base.pagination import PaginatedResult
            return PaginatedResult(
                items=items,
                total_count=total_count,
                page=pagination.page,
                page_size=pagination.per_page
            )
            
        except SQLAlchemyError as e:
            raise RepositoryError(f"Pagination failed: {str(e)}") from e
    
    def find_by_specification(self, specification: 'Specification') -> List[ModelType]:
        """
        Find entities matching a specification.
        
        Args:
            specification: Specification to apply
            
        Returns:
            List of matching entities
        """
        try:
            query = self.db.query(self.model)
            
            # Apply the specification
            if hasattr(specification, 'is_satisfied_by'):
                query = specification.is_satisfied_by(query)
            else:
                # Fallback to expression-based specification
                expression = specification.to_expression(self.model)
                query = query.filter(expression)
            
            return query.all()
            
        except SQLAlchemyError as e:
            raise RepositoryError(f"Specification query failed: {str(e)}") from e
    
    # ==================== Utility Methods ====================
    
    def refresh(self, entity: ModelType) -> ModelType:
        """
        Refresh entity from database.
        
        Args:
            entity: Entity to refresh
            
        Returns:
            Refreshed entity
        """
        self.db.refresh(entity)
        return entity
    
    def expunge(self, entity: ModelType) -> None:
        """
        Remove entity from session.
        
        Args:
            entity: Entity to expunge
        """
        self.db.expunge(entity)
    
    def merge(self, entity: ModelType) -> ModelType:
        """
        Merge detached entity into session.
        
        Args:
            entity: Entity to merge
            
        Returns:
            Merged entity
        """
        return self.db.merge(entity)