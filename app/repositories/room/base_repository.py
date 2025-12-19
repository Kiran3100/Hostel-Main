# app/repositories/room/base_repository.py
"""
Base repository with common CRUD operations and utilities.
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, update, delete
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.models.base.base_model import BaseModel

T = TypeVar('T', bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Base repository providing common database operations.
    
    Features:
    - CRUD operations with soft delete support
    - Bulk operations
    - Transaction management
    - Query building and filtering
    - Pagination support
    - Relationship loading
    """

    def __init__(self, model: Type[T], session: Session):
        """
        Initialize repository.
        
        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================

    def create(
        self,
        data: Dict[str, Any],
        commit: bool = True,
        flush: bool = False
    ) -> T:
        """
        Create a new entity.
        
        Args:
            data: Entity data
            commit: Whether to commit transaction
            flush: Whether to flush session
            
        Returns:
            Created entity
            
        Raises:
            IntegrityError: If unique constraint violated
            SQLAlchemyError: If database error occurs
        """
        try:
            entity = self.model(**data)
            self.session.add(entity)
            
            if flush:
                self.session.flush()
            if commit:
                self.session.commit()
                self.session.refresh(entity)
                
            return entity
            
        except IntegrityError as e:
            self.session.rollback()
            raise ValueError(f"Integrity constraint violated: {str(e)}")
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Database error: {str(e)}")

    def bulk_create(
        self,
        data_list: List[Dict[str, Any]],
        batch_size: int = 1000,
        commit: bool = True
    ) -> List[T]:
        """
        Create multiple entities in bulk.
        
        Args:
            data_list: List of entity data
            batch_size: Batch size for bulk insert
            commit: Whether to commit transaction
            
        Returns:
            List of created entities
        """
        try:
            entities = []
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]
                batch_entities = [self.model(**data) for data in batch]
                self.session.bulk_save_objects(batch_entities, return_defaults=True)
                entities.extend(batch_entities)
                
            if commit:
                self.session.commit()
                
            return entities
            
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Bulk create error: {str(e)}")

    # ============================================================================
    # READ OPERATIONS
    # ============================================================================

    def find_by_id(
        self,
        id: str,
        include_deleted: bool = False,
        load_relationships: Optional[List[str]] = None
    ) -> Optional[T]:
        """
        Find entity by ID.
        
        Args:
            id: Entity ID
            include_deleted: Whether to include soft-deleted records
            load_relationships: List of relationships to eager load
            
        Returns:
            Entity or None if not found
        """
        query = select(self.model).where(self.model.id == id)
        
        # Handle soft delete
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        # Eager load relationships
        if load_relationships:
            for rel in load_relationships:
                query = query.options(joinedload(getattr(self.model, rel)))
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_all(
        self,
        include_deleted: bool = False,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """
        Find all entities.
        
        Args:
            include_deleted: Whether to include soft-deleted records
            order_by: Column to order by
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of entities
        """
        query = select(self.model)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        if order_by:
            order_column = getattr(self.model, order_by, None)
            if order_column is not None:
                query = query.order_by(order_column)
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_criteria(
        self,
        filters: Dict[str, Any],
        include_deleted: bool = False,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """
        Find entities matching criteria.
        
        Args:
            filters: Filter criteria (field: value pairs)
            include_deleted: Whether to include soft-deleted records
            order_by: Column to order by
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of matching entities
        """
        query = select(self.model)
        
        # Apply filters
        conditions = []
        for field, value in filters.items():
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                if isinstance(value, (list, tuple)):
                    conditions.append(column.in_(value))
                elif value is None:
                    conditions.append(column.is_(None))
                else:
                    conditions.append(column == value)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        if order_by:
            order_column = getattr(self.model, order_by, None)
            if order_column is not None:
                query = query.order_by(order_column)
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def exists(self, filters: Dict[str, Any]) -> bool:
        """
        Check if entity exists matching criteria.
        
        Args:
            filters: Filter criteria
            
        Returns:
            True if exists, False otherwise
        """
        query = select(func.count(self.model.id))
        
        conditions = []
        for field, value in filters.items():
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                conditions.append(column == value)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        if hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        result = self.session.execute(query)
        count = result.scalar()
        return count > 0

    def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False
    ) -> int:
        """
        Count entities matching criteria.
        
        Args:
            filters: Filter criteria
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Count of matching entities
        """
        query = select(func.count(self.model.id))
        
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    conditions.append(column == value)
            if conditions:
                query = query.where(and_(*conditions))
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        result = self.session.execute(query)
        return result.scalar()

    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================

    def update(
        self,
        id: str,
        data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[T]:
        """
        Update entity by ID.
        
        Args:
            id: Entity ID
            data: Update data
            commit: Whether to commit transaction
            
        Returns:
            Updated entity or None if not found
        """
        try:
            entity = self.find_by_id(id)
            if not entity:
                return None
            
            for key, value in data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            if hasattr(entity, 'updated_at'):
                entity.updated_at = datetime.utcnow()
            
            if commit:
                self.session.commit()
                self.session.refresh(entity)
            
            return entity
            
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Update error: {str(e)}")

    def bulk_update(
        self,
        filters: Dict[str, Any],
        data: Dict[str, Any],
        commit: bool = True
    ) -> int:
        """
        Update multiple entities matching criteria.
        
        Args:
            filters: Filter criteria
            data: Update data
            commit: Whether to commit transaction
            
        Returns:
            Number of updated entities
        """
        try:
            stmt = update(self.model)
            
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    conditions.append(column == value)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            if hasattr(self.model, 'updated_at'):
                data['updated_at'] = datetime.utcnow()
            
            stmt = stmt.values(**data)
            result = self.session.execute(stmt)
            
            if commit:
                self.session.commit()
            
            return result.rowcount
            
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Bulk update error: {str(e)}")

    # ============================================================================
    # DELETE OPERATIONS
    # ============================================================================

    def delete(self, id: str, commit: bool = True) -> bool:
        """
        Hard delete entity by ID.
        
        Args:
            id: Entity ID
            commit: Whether to commit transaction
            
        Returns:
            True if deleted, False if not found
        """
        try:
            entity = self.find_by_id(id, include_deleted=True)
            if not entity:
                return False
            
            self.session.delete(entity)
            
            if commit:
                self.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Delete error: {str(e)}")

    def soft_delete(self, id: str, commit: bool = True) -> bool:
        """
        Soft delete entity by ID.
        
        Args:
            id: Entity ID
            commit: Whether to commit transaction
            
        Returns:
            True if deleted, False if not found
        """
        if not hasattr(self.model, 'is_deleted'):
            raise NotImplementedError("Model does not support soft delete")
        
        try:
            entity = self.find_by_id(id)
            if not entity:
                return False
            
            entity.is_deleted = True
            if hasattr(entity, 'deleted_at'):
                entity.deleted_at = datetime.utcnow()
            
            if commit:
                self.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Soft delete error: {str(e)}")

    def restore(self, id: str, commit: bool = True) -> bool:
        """
        Restore soft-deleted entity.
        
        Args:
            id: Entity ID
            commit: Whether to commit transaction
            
        Returns:
            True if restored, False if not found
        """
        if not hasattr(self.model, 'is_deleted'):
            raise NotImplementedError("Model does not support soft delete")
        
        try:
            entity = self.find_by_id(id, include_deleted=True)
            if not entity or not entity.is_deleted:
                return False
            
            entity.is_deleted = False
            if hasattr(entity, 'deleted_at'):
                entity.deleted_at = None
            
            if commit:
                self.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            raise RuntimeError(f"Restore error: {str(e)}")

    # ============================================================================
    # PAGINATION
    # ============================================================================

    def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Paginate query results.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            filters: Filter criteria
            order_by: Column to order by
            
        Returns:
            Dictionary with items, total, page, per_page, pages
        """
        offset = (page - 1) * per_page
        
        items = self.find_by_criteria(
            filters=filters or {},
            order_by=order_by,
            limit=per_page,
            offset=offset
        )
        
        total = self.count(filters=filters)
        pages = (total + per_page - 1) // per_page
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': pages,
            'has_prev': page > 1,
            'has_next': page < pages
        }

    # ============================================================================
    # TRANSACTION MANAGEMENT
    # ============================================================================

    def begin_transaction(self):
        """Begin a new transaction."""
        self.session.begin()

    def commit(self):
        """Commit current transaction."""
        self.session.commit()

    def rollback(self):
        """Rollback current transaction."""
        self.session.rollback()

    def flush(self):
        """Flush session."""
        self.session.flush()

    def refresh(self, entity: T):
        """Refresh entity from database."""
        self.session.refresh(entity)