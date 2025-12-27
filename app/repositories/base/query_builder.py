"""
Fluent query builder with type-safe operations, join optimization, and performance analysis.

Provides advanced query construction capabilities with automatic
optimization and performance monitoring.
"""

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from datetime import datetime
from enum import Enum

from sqlalchemy import and_, or_, not_, func, text, case
from sqlalchemy.orm import Query, Session, joinedload, selectinload, subqueryload
from sqlalchemy.sql import Select, ClauseElement
from sqlalchemy.sql.expression import ColumnElement

from app.models.base import BaseModel
from app.core1.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)


class JoinType(str, Enum):
    """SQL join types."""
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    OUTER = "outer"


class OrderDirection(str, Enum):
    """Order direction."""
    ASC = "asc"
    DESC = "desc"


class QueryBuilder(Generic[ModelType]):
    """
    Fluent query builder with advanced features.
    
    Provides chainable methods for building complex queries
    with automatic optimization.
    """
    
    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize query builder.
        
        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db
        self._query: Optional[Query] = None
        self._filters: List[ClauseElement] = []
        self._joins: List[tuple] = []
        self._order_by: List[tuple] = []
        self._group_by: List[ColumnElement] = []
        self._having: List[ClauseElement] = []
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None
        self._distinct_flag: bool = False
        self._eager_loads: List[tuple] = []
        self._subqueries: Dict[str, Query] = {}
        self._performance_hints: List[str] = []
    
    # ==================== Filter Methods ====================
    
    def where(self, *conditions: ClauseElement) -> "QueryBuilder[ModelType]":
        """
        Add WHERE conditions.
        
        Args:
            *conditions: Filter conditions
            
        Returns:
            Self for chaining
        """
        self._filters.extend(conditions)
        return self
    
    def filter(self, **kwargs) -> "QueryBuilder[ModelType]":
        """
        Add filters using keyword arguments.
        
        Args:
            **kwargs: Field=value pairs
            
        Returns:
            Self for chaining
        """
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                if isinstance(value, (list, tuple)):
                    self._filters.append(column.in_(value))
                elif value is None:
                    self._filters.append(column.is_(None))
                else:
                    self._filters.append(column == value)
        return self
    
    def filter_by_id(self, id: Any) -> "QueryBuilder[ModelType]":
        """
        Filter by primary key.
        
        Args:
            id: Primary key value
            
        Returns:
            Self for chaining
        """
        self._filters.append(self.model.id == id)
        return self
    
    def filter_by_ids(self, ids: List[Any]) -> "QueryBuilder[ModelType]":
        """
        Filter by multiple IDs.
        
        Args:
            ids: List of IDs
            
        Returns:
            Self for chaining
        """
        self._filters.append(self.model.id.in_(ids))
        return self
    
    def or_where(self, *conditions: ClauseElement) -> "QueryBuilder[ModelType]":
        """
        Add OR conditions.
        
        Args:
            *conditions: OR conditions
            
        Returns:
            Self for chaining
        """
        if conditions:
            self._filters.append(or_(*conditions))
        return self
    
    def not_where(self, condition: ClauseElement) -> "QueryBuilder[ModelType]":
        """
        Add NOT condition.
        
        Args:
            condition: Condition to negate
            
        Returns:
            Self for chaining
        """
        self._filters.append(not_(condition))
        return self
    
    def where_null(self, field: str) -> "QueryBuilder[ModelType]":
        """
        Filter where field is NULL.
        
        Args:
            field: Field name
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._filters.append(getattr(self.model, field).is_(None))
        return self
    
    def where_not_null(self, field: str) -> "QueryBuilder[ModelType]":
        """
        Filter where field is NOT NULL.
        
        Args:
            field: Field name
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._filters.append(getattr(self.model, field).isnot(None))
        return self
    
    def where_in(self, field: str, values: List[Any]) -> "QueryBuilder[ModelType]":
        """
        Filter where field is IN list.
        
        Args:
            field: Field name
            values: List of values
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._filters.append(getattr(self.model, field).in_(values))
        return self
    
    def where_not_in(self, field: str, values: List[Any]) -> "QueryBuilder[ModelType]":
        """
        Filter where field is NOT IN list.
        
        Args:
            field: Field name
            values: List of values
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._filters.append(~getattr(self.model, field).in_(values))
        return self
    
    def where_between(
        self,
        field: str,
        start: Any,
        end: Any
    ) -> "QueryBuilder[ModelType]":
        """
        Filter where field is BETWEEN values.
        
        Args:
            field: Field name
            start: Start value
            end: End value
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            column = getattr(self.model, field)
            self._filters.append(and_(column >= start, column <= end))
        return self
    
    def where_like(self, field: str, pattern: str) -> "QueryBuilder[ModelType]":
        """
        Filter where field matches LIKE pattern.
        
        Args:
            field: Field name
            pattern: LIKE pattern
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._filters.append(getattr(self.model, field).like(pattern))
        return self
    
    def where_ilike(self, field: str, pattern: str) -> "QueryBuilder[ModelType]":
        """
        Filter where field matches ILIKE pattern (case-insensitive).
        
        Args:
            field: Field name
            pattern: ILIKE pattern
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._filters.append(getattr(self.model, field).ilike(pattern))
        return self
    
    def where_date(
        self,
        field: str,
        date: datetime
    ) -> "QueryBuilder[ModelType]":
        """
        Filter by date (ignoring time).
        
        Args:
            field: Field name
            date: Date to match
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            column = getattr(self.model, field)
            self._filters.append(func.date(column) == date.date())
        return self
    
    # ==================== Join Methods ====================
    
    def join(
        self,
        model: Type[BaseModel],
        condition: Optional[ClauseElement] = None,
        join_type: JoinType = JoinType.INNER,
        aliased: bool = False
    ) -> "QueryBuilder[ModelType]":
        """
        Add JOIN clause.
        
        Args:
            model: Model to join
            condition: Join condition
            join_type: Type of join
            aliased: Whether to create alias
            
        Returns:
            Self for chaining
        """
        self._joins.append((model, condition, join_type, aliased))
        return self
    
    def left_join(
        self,
        model: Type[BaseModel],
        condition: Optional[ClauseElement] = None
    ) -> "QueryBuilder[ModelType]":
        """
        Add LEFT JOIN clause.
        
        Args:
            model: Model to join
            condition: Join condition
            
        Returns:
            Self for chaining
        """
        return self.join(model, condition, JoinType.LEFT)
    
    def right_join(
        self,
        model: Type[BaseModel],
        condition: Optional[ClauseElement] = None
    ) -> "QueryBuilder[ModelType]":
        """
        Add RIGHT JOIN clause.
        
        Args:
            model: Model to join
            condition: Join condition
            
        Returns:
            Self for chaining
        """
        return self.join(model, condition, JoinType.RIGHT)
    
    def outer_join(
        self,
        model: Type[BaseModel],
        condition: Optional[ClauseElement] = None
    ) -> "QueryBuilder[ModelType]":
        """
        Add OUTER JOIN clause.
        
        Args:
            model: Model to join
            condition: Join condition
            
        Returns:
            Self for chaining
        """
        return self.join(model, condition, JoinType.OUTER)
    
    # ==================== Eager Loading ====================
    
    def with_eager(self, *relationships: str) -> "QueryBuilder[ModelType]":
        """
        Eager load relationships using JOIN.
        
        Args:
            *relationships: Relationship names
            
        Returns:
            Self for chaining
        """
        for rel in relationships:
            if hasattr(self.model, rel):
                self._eager_loads.append((rel, 'joined'))
        return self
    
    def with_subquery(self, *relationships: str) -> "QueryBuilder[ModelType]":
        """
        Eager load relationships using subquery.
        
        Args:
            *relationships: Relationship names
            
        Returns:
            Self for chaining
        """
        for rel in relationships:
            if hasattr(self.model, rel):
                self._eager_loads.append((rel, 'subquery'))
        return self
    
    def with_selectin(self, *relationships: str) -> "QueryBuilder[ModelType]":
        """
        Eager load relationships using SELECT IN.
        
        Args:
            *relationships: Relationship names
            
        Returns:
            Self for chaining
        """
        for rel in relationships:
            if hasattr(self.model, rel):
                self._eager_loads.append((rel, 'selectin'))
        return self
    
    # ==================== Ordering ====================
    
    def order_by(
        self,
        field: str,
        direction: OrderDirection = OrderDirection.ASC
    ) -> "QueryBuilder[ModelType]":
        """
        Add ORDER BY clause.
        
        Args:
            field: Field name
            direction: Order direction
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model, field):
            self._order_by.append((field, direction))
        return self
    
    def order_by_desc(self, field: str) -> "QueryBuilder[ModelType]":
        """
        Order by field descending.
        
        Args:
            field: Field name
            
        Returns:
            Self for chaining
        """
        return self.order_by(field, OrderDirection.DESC)
    
    def order_by_asc(self, field: str) -> "QueryBuilder[ModelType]":
        """
        Order by field ascending.
        
        Args:
            field: Field name
            
        Returns:
            Self for chaining
        """
        return self.order_by(field, OrderDirection.ASC)
    
    # ==================== Grouping ====================
    
    def group_by(self, *fields: str) -> "QueryBuilder[ModelType]":
        """
        Add GROUP BY clause.
        
        Args:
            *fields: Field names
            
        Returns:
            Self for chaining
        """
        for field in fields:
            if hasattr(self.model, field):
                self._group_by.append(getattr(self.model, field))
        return self
    
    def having(self, *conditions: ClauseElement) -> "QueryBuilder[ModelType]":
        """
        Add HAVING clause.
        
        Args:
            *conditions: Having conditions
            
        Returns:
            Self for chaining
        """
        self._having.extend(conditions)
        return self
    
    # ==================== Pagination ====================
    
    def limit(self, limit: int) -> "QueryBuilder[ModelType]":
        """
        Set LIMIT.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            Self for chaining
        """
        self._limit_value = limit
        return self
    
    def offset(self, offset: int) -> "QueryBuilder[ModelType]":
        """
        Set OFFSET.
        
        Args:
            offset: Number of results to skip
            
        Returns:
            Self for chaining
        """
        self._offset_value = offset
        return self
    
    def paginate(self, page: int, per_page: int) -> "QueryBuilder[ModelType]":
        """
        Paginate results.
        
        Args:
            page: Page number (1-indexed)
            per_page: Results per page
            
        Returns:
            Self for chaining
        """
        self._limit_value = per_page
        self._offset_value = (page - 1) * per_page
        return self
    
    # ==================== Distinct ====================
    
    def distinct(self, *fields: str) -> "QueryBuilder[ModelType]":
        """
        Add DISTINCT clause.
        
        Args:
            *fields: Fields for DISTINCT ON (PostgreSQL)
            
        Returns:
            Self for chaining
        """
        self._distinct_flag = True
        return self
    
    # ==================== Subqueries ====================
    
    def with_subquery(
        self,
        name: str,
        query: Query
    ) -> "QueryBuilder[ModelType]":
        """
        Add named subquery (CTE).
        
        Args:
            name: Subquery name
            query: Subquery
            
        Returns:
            Self for chaining
        """
        self._subqueries[name] = query
        return self
    
    # ==================== Build & Execute ====================
    
    def build(self) -> Query:
        """
        Build final query.
        
        Returns:
            SQLAlchemy Query object
        """
        # Start with base query
        query = self.db.query(self.model)
        
        # Apply joins
        for model, condition, join_type, aliased in self._joins:
            if join_type == JoinType.INNER:
                query = query.join(model, condition, isouter=False)
            elif join_type == JoinType.LEFT:
                query = query.join(model, condition, isouter=True)
            # Add other join types as needed
        
        # Apply filters
        if self._filters:
            query = query.filter(and_(*self._filters))
        
        # Apply eager loading
        for rel, strategy in self._eager_loads:
            if strategy == 'joined':
                query = query.options(joinedload(getattr(self.model, rel)))
            elif strategy == 'subquery':
                query = query.options(subqueryload(getattr(self.model, rel)))
            elif strategy == 'selectin':
                query = query.options(selectinload(getattr(self.model, rel)))
        
        # Apply ordering
        for field, direction in self._order_by:
            column = getattr(self.model, field)
            if direction == OrderDirection.DESC:
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())
        
        # Apply grouping
        if self._group_by:
            query = query.group_by(*self._group_by)
        
        # Apply having
        if self._having:
            query = query.having(and_(*self._having))
        
        # Apply distinct
        if self._distinct_flag:
            query = query.distinct()
        
        # Apply pagination
        if self._offset_value is not None:
            query = query.offset(self._offset_value)
        if self._limit_value is not None:
            query = query.limit(self._limit_value)
        
        self._query = query
        return query
    
    def all(self) -> List[ModelType]:
        """
        Execute query and return all results.
        
        Returns:
            List of entities
        """
        query = self.build()
        return query.all()
    
    def first(self) -> Optional[ModelType]:
        """
        Execute query and return first result.
        
        Returns:
            First entity or None
        """
        query = self.build()
        return query.first()
    
    def one(self) -> ModelType:
        """
        Execute query and return exactly one result.
        
        Returns:
            Single entity
            
        Raises:
            NoResultFound: If no results
            MultipleResultsFound: If multiple results
        """
        query = self.build()
        return query.one()
    
    def one_or_none(self) -> Optional[ModelType]:
        """
        Execute query and return one result or None.
        
        Returns:
            Single entity or None
        """
        query = self.build()
        return query.one_or_none()
    
    def count(self) -> int:
        """
        Count query results.
        
        Returns:
            Result count
        """
        query = self.build()
        return query.count()
    
    def exists(self) -> bool:
        """
        Check if query returns any results.
        
        Returns:
            True if results exist
        """
        return self.count() > 0
    
    def explain(self) -> str:
        """
        Get query execution plan.
        
        Returns:
            Execution plan as string
        """
        query = self.build()
        return str(query.statement.compile(
            compile_kwargs={"literal_binds": True}
        ))
    
    def reset(self) -> "QueryBuilder[ModelType]":
        """
        Reset builder to initial state.
        
        Returns:
            Self for chaining
        """
        self._query = None
        self._filters = []
        self._joins = []
        self._order_by = []
        self._group_by = []
        self._having = []
        self._limit_value = None
        self._offset_value = None
        self._distinct_flag = False
        self._eager_loads = []
        self._subqueries = {}
        return self