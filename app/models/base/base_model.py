# --- File: C:\Hostel-Main\app\models\base\base_model.py ---
"""
Base model configuration for SQLAlchemy ORM.

Provides abstract base classes with common functionality
for all database models including declarative base setup,
session management, and utility methods.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import uuid4

from sqlalchemy import Column, DateTime, Boolean, String, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import Session, Query, Mapped, mapped_column
from sqlalchemy.sql import func

# Create declarative base
Base = declarative_base()

# Type variable for model classes
ModelType = TypeVar("ModelType", bound="BaseModel")


class BaseModel(Base):
    """
    Abstract base model with common fields and methods.
    
    Provides foundation for all database models with
    standard functionality and utilities.
    """
    
    __abstract__ = True
    
    # Primary key column - present in all models
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
        comment="Primary key (UUID)"
    )
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower() + 's'
    
    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            exclude: List of field names to exclude
            
        Returns:
            Dictionary representation of the model
        """
        exclude = exclude or []
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                
                # Handle special types
                if isinstance(value, datetime):
                    result[column.name] = value.isoformat()
                elif isinstance(value, (uuid4, PG_UUID)):
                    result[column.name] = str(value)
                else:
                    result[column.name] = value
        
        return result
    
    @classmethod
    def get_by_id(cls: Type[ModelType], db: Session, id: Any) -> Optional[ModelType]:
        """
        Get model instance by ID.
        
        Args:
            db: Database session
            id: Primary key value
            
        Returns:
            Model instance or None
        """
        return db.query(cls).filter(cls.id == id).first()
    
    @classmethod
    def get_all(
        cls: Type[ModelType],
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get all model instances with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances
        """
        return db.query(cls).offset(skip).limit(limit).all()
    
    @classmethod
    def count(cls: Type[ModelType], db: Session) -> int:
        """
        Get total count of records.
        
        Args:
            db: Database session
            
        Returns:
            Total count
        """
        return db.query(cls).count()
    
    def save(self, db: Session, commit: bool = True) -> "BaseModel":
        """
        Save model instance to database.
        
        Args:
            db: Database session
            commit: Whether to commit immediately
            
        Returns:
            Saved model instance
        """
        db.add(self)
        if commit:
            db.commit()
            db.refresh(self)
        return self
    
    def delete(self, db: Session, commit: bool = True) -> None:
        """
        Delete model instance from database.
        
        Args:
            db: Database session
            commit: Whether to commit immediately
        """
        db.delete(self)
        if commit:
            db.commit()
    
    def update(self, db: Session, **kwargs) -> "BaseModel":
        """
        Update model instance with provided values.
        
        Args:
            db: Database session
            **kwargs: Field values to update
            
        Returns:
            Updated model instance
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        return self.save(db)
    
    def __repr__(self) -> str:
        """String representation of model instance."""
        return f"<{self.__class__.__name__}(id={getattr(self, 'id', None)})>"


class TimestampModel(BaseModel):
    """
    Base model with automatic timestamp tracking.
    
    Includes created_at and updated_at fields with
    automatic management.
    """
    
    __abstract__ = True
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Record last update timestamp"
    )


class SoftDeleteModel(TimestampModel):
    """
    Base model with soft delete capability.
    
    Includes is_deleted flag and deleted_at timestamp
    for logical deletion.
    """
    
    __abstract__ = True
    
    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Soft delete flag"
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Deletion timestamp"
    )
    
    def soft_delete(self, db: Session, commit: bool = True) -> "SoftDeleteModel":
        """
        Perform soft delete on model instance.
        
        Args:
            db: Database session
            commit: Whether to commit immediately
            
        Returns:
            Soft-deleted model instance
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        return self.save(db, commit=commit)
    
    def restore(self, db: Session, commit: bool = True) -> "SoftDeleteModel":
        """
        Restore soft-deleted model instance.
        
        Args:
            db: Database session
            commit: Whether to commit immediately
            
        Returns:
            Restored model instance
        """
        self.is_deleted = False
        self.deleted_at = None
        return self.save(db, commit=commit)
    
    @classmethod
    def get_active(
        cls: Type[ModelType],
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get all non-deleted model instances.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of active model instances
        """
        return db.query(cls).filter(
            cls.is_deleted == False
        ).offset(skip).limit(limit).all()


class TenantModel(SoftDeleteModel):
    """
    Base model for multi-tenancy support.
    
    Includes hostel_id for tenant isolation and
    provides tenant-aware query methods.
    """
    
    __abstract__ = True
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Hostel/tenant identifier"
    )
    
    @classmethod
    def get_by_hostel(
        cls: Type[ModelType],
        db: Session,
        hostel_id: Any,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get model instances for specific hostel.
        
        Args:
            db: Database session
            hostel_id: Hostel identifier
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances for hostel
        """
        return db.query(cls).filter(
            cls.hostel_id == hostel_id,
            cls.is_deleted == False
        ).offset(skip).limit(limit).all()
    
    @classmethod
    def count_by_hostel(cls: Type[ModelType], db: Session, hostel_id: Any) -> int:
        """
        Get count of records for specific hostel.
        
        Args:
            db: Database session
            hostel_id: Hostel identifier
            
        Returns:
            Count of records
        """
        return db.query(cls).filter(
            cls.hostel_id == hostel_id,
            cls.is_deleted == False
        ).count()


# Event listeners for automatic timestamp management
@event.listens_for(TimestampModel, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    """Update timestamp before update."""
    target.updated_at = datetime.utcnow()


@event.listens_for(SoftDeleteModel, 'before_update', propagate=True)
def receive_before_soft_delete(mapper, connection, target):
    """Set deleted_at timestamp on soft delete."""
    if target.is_deleted and not target.deleted_at:
        target.deleted_at = datetime.utcnow()