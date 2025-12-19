"""
Advanced pagination with multiple strategies and performance optimization.

Provides offset-based, cursor-based, keyset-based, and hybrid
pagination strategies.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import base64
import json

from sqlalchemy import asc, desc, func, or_, and_
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql.expression import ColumnElement

from app.models.base import BaseModel
from app.core.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)


class PaginationStrategy(str, Enum):
    """Pagination strategy types."""
    OFFSET = "offset"
    CURSOR = "cursor"
    KEYSET = "keyset"
    HYBRID = "hybrid"


@dataclass
class PageInfo:
    """Pagination metadata."""
    
    current_page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None
    
    @property
    def start_index(self) -> int:
        """Get starting index for current page."""
        return (self.current_page - 1) * self.per_page
    
    @property
    def end_index(self) -> int:
        """Get ending index for current page."""
        return min(self.start_index + self.per_page, self.total_items)


@dataclass
class PaginatedResult(Generic[ModelType]):
    """Paginated query result."""
    
    items: List[ModelType]
    page_info: PageInfo
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "items": [item.to_dict() if hasattr(item, 'to_dict') else item 
                     for item in self.items],
            "pagination": {
                "current_page": self.page_info.current_page,
                "per_page": self.page_info.per_page,
                "total_items": self.page_info.total_items,
                "total_pages": self.page_info.total_pages,
                "has_next": self.page_info.has_next,
                "has_previous": self.page_info.has_previous,
                "next_cursor": self.page_info.next_cursor,
                "previous_cursor": self.page_info.previous_cursor,
            }
        }


class Cursor:
    """Cursor for cursor-based pagination."""
    
    def __init__(
        self,
        value: Any,
        field: str = "id",
        direction: str = "next"
    ):
        self.value = value
        self.field = field
        self.direction = direction
    
    def encode(self) -> str:
        """
        Encode cursor to base64 string.
        
        Returns:
            Base64 encoded cursor
        """
        data = {
            "value": str(self.value),
            "field": self.field,
            "direction": self.direction,
        }
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode()).decode()
    
    @classmethod
    def decode(cls, encoded: str) -> "Cursor":
        """
        Decode cursor from base64 string.
        
        Args:
            encoded: Base64 encoded cursor
            
        Returns:
            Cursor instance
        """
        try:
            json_str = base64.b64decode(encoded.encode()).decode()
            data = json.loads(json_str)
            return cls(
                value=data["value"],
                field=data["field"],
                direction=data["direction"]
            )
        except Exception as e:
            logger.error(f"Failed to decode cursor: {e}")
            raise ValueError("Invalid cursor")


class PaginationManager(Generic[ModelType]):
    """
    Advanced pagination manager with multiple strategies.
    
    Provides optimized pagination for different use cases
    and dataset sizes.
    """
    
    def __init__(
        self,
        query: Query,
        model: Type[ModelType],
        strategy: PaginationStrategy = PaginationStrategy.OFFSET,
        default_page_size: int = 50,
        max_page_size: int = 1000,
        count_threshold: int = 10000,
        enable_count_estimation: bool = True
    ):
        """
        Initialize pagination manager.
        
        Args:
            query: Base SQLAlchemy query
            model: Model class
            strategy: Pagination strategy to use
            default_page_size: Default items per page
            max_page_size: Maximum items per page
            count_threshold: Threshold for count estimation
            enable_count_estimation: Whether to estimate counts for large datasets
        """
        self.query = query
        self.model = model
        self.strategy = strategy
        self.default_page_size = default_page_size
        self.max_page_size = max_page_size
        self.count_threshold = count_threshold
        self.enable_count_estimation = enable_count_estimation
    
    # ==================== Offset-Based Pagination ====================
    
    def paginate_offset(
        self,
        page: int = 1,
        per_page: Optional[int] = None,
        count_items: bool = True
    ) -> PaginatedResult[ModelType]:
        """
        Traditional offset-based pagination.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            count_items: Whether to count total items
            
        Returns:
            Paginated result
        """
        # Validate and normalize parameters
        page = max(1, page)
        per_page = min(per_page or self.default_page_size, self.max_page_size)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get total count
        if count_items:
            total_items = self._get_total_count()
        else:
            # Estimate based on query
            total_items = offset + per_page + 1
        
        # Execute paginated query
        items = self.query.offset(offset).limit(per_page).all()
        
        # Calculate pagination info
        total_pages = (total_items + per_page - 1) // per_page if count_items else 0
        has_next = len(items) == per_page and (not count_items or page < total_pages)
        has_previous = page > 1
        
        page_info = PageInfo(
            current_page=page,
            per_page=per_page,
            total_items=total_items if count_items else -1,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
        return PaginatedResult(items=items, page_info=page_info)
    
    # ==================== Cursor-Based Pagination ====================
    
    def paginate_cursor(
        self,
        cursor: Optional[str] = None,
        per_page: Optional[int] = None,
        order_by: str = "id",
        order_direction: str = "asc"
    ) -> PaginatedResult[ModelType]:
        """
        Cursor-based pagination for large datasets.
        
        Args:
            cursor: Pagination cursor
            per_page: Items per page
            order_by: Field to order by
            order_direction: Order direction (asc/desc)
            
        Returns:
            Paginated result
        """
        per_page = min(per_page or self.default_page_size, self.max_page_size)
        
        # Decode cursor if provided
        cursor_obj = None
        if cursor:
            cursor_obj = Cursor.decode(cursor)
        
        # Build query with cursor
        query = self.query
        if cursor_obj:
            column = getattr(self.model, cursor_obj.field)
            if cursor_obj.direction == "next":
                if order_direction == "asc":
                    query = query.filter(column > cursor_obj.value)
                else:
                    query = query.filter(column < cursor_obj.value)
            else:  # previous
                if order_direction == "asc":
                    query = query.filter(column < cursor_obj.value)
                else:
                    query = query.filter(column > cursor_obj.value)
        
        # Apply ordering
        order_column = getattr(self.model, order_by)
        if order_direction == "asc":
            query = query.order_by(asc(order_column))
        else:
            query = query.order_by(desc(order_column))
        
        # Fetch one extra to check if there's a next page
        items = query.limit(per_page + 1).all()
        
        has_next = len(items) > per_page
        if has_next:
            items = items[:per_page]
        
        # Create next cursor
        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            next_cursor = Cursor(
                value=getattr(last_item, order_by),
                field=order_by,
                direction="next"
            ).encode()
        
        # Create previous cursor
        previous_cursor = None
        if cursor_obj or (items and cursor):
            first_item = items[0] if items else None
            if first_item:
                previous_cursor = Cursor(
                    value=getattr(first_item, order_by),
                    field=order_by,
                    direction="previous"
                ).encode()
        
        page_info = PageInfo(
            current_page=1,  # Not applicable for cursor pagination
            per_page=per_page,
            total_items=-1,  # Unknown for cursor pagination
            total_pages=-1,
            has_next=has_next,
            has_previous=cursor is not None,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor
        )
        
        return PaginatedResult(items=items, page_info=page_info)
    
    # ==================== Keyset-Based Pagination ====================
    
    def paginate_keyset(
        self,
        last_id: Optional[Any] = None,
        last_value: Optional[Any] = None,
        per_page: Optional[int] = None,
        order_by: str = "created_at",
        order_direction: str = "desc"
    ) -> PaginatedResult[ModelType]:
        """
        Keyset pagination using indexed columns.
        
        More efficient than offset for large datasets.
        
        Args:
            last_id: Last seen ID
            last_value: Last seen value of order_by field
            per_page: Items per page
            order_by: Field to order by
            order_direction: Order direction
            
        Returns:
            Paginated result
        """
        per_page = min(per_page or self.default_page_size, self.max_page_size)
        
        query = self.query
        
        # Apply keyset filter
        if last_id and last_value:
            id_column = self.model.id
            order_column = getattr(self.model, order_by)
            
            if order_direction == "asc":
                query = query.filter(
                    or_(
                        order_column > last_value,
                        and_(order_column == last_value, id_column > last_id)
                    )
                )
            else:
                query = query.filter(
                    or_(
                        order_column < last_value,
                        and_(order_column == last_value, id_column > last_id)
                    )
                )
        
        # Apply ordering
        order_column = getattr(self.model, order_by)
        if order_direction == "asc":
            query = query.order_by(asc(order_column), asc(self.model.id))
        else:
            query = query.order_by(desc(order_column), asc(self.model.id))
        
        # Fetch results
        items = query.limit(per_page + 1).all()
        
        has_next = len(items) > per_page
        if has_next:
            items = items[:per_page]
        
        page_info = PageInfo(
            current_page=1,
            per_page=per_page,
            total_items=-1,
            total_pages=-1,
            has_next=has_next,
            has_previous=last_id is not None
        )
        
        return PaginatedResult(items=items, page_info=page_info)
    
    # ==================== Hybrid Pagination ====================
    
    def paginate_hybrid(
        self,
        page: int = 1,
        per_page: Optional[int] = None,
        cursor: Optional[str] = None,
        order_by: str = "id"
    ) -> PaginatedResult[ModelType]:
        """
        Hybrid pagination combining offset and cursor strategies.
        
        Uses offset for small datasets and cursor for large ones.
        
        Args:
            page: Page number
            per_page: Items per page
            cursor: Cursor for continuation
            order_by: Field to order by
            
        Returns:
            Paginated result
        """
        # Estimate total count
        total_count = self._get_total_count(estimate=True)
        
        # Choose strategy based on dataset size
        if total_count < self.count_threshold:
            return self.paginate_offset(page, per_page, count_items=True)
        else:
            return self.paginate_cursor(cursor, per_page, order_by)
    
    # ==================== Smart Pagination ====================
    
    def paginate(
        self,
        page: int = 1,
        per_page: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs
    ) -> PaginatedResult[ModelType]:
        """
        Smart pagination using configured strategy.
        
        Args:
            page: Page number
            per_page: Items per page
            cursor: Cursor for cursor-based pagination
            **kwargs: Additional strategy-specific arguments
            
        Returns:
            Paginated result
        """
        if self.strategy == PaginationStrategy.OFFSET:
            return self.paginate_offset(page, per_page)
        elif self.strategy == PaginationStrategy.CURSOR:
            return self.paginate_cursor(cursor, per_page, **kwargs)
        elif self.strategy == PaginationStrategy.KEYSET:
            return self.paginate_keyset(per_page=per_page, **kwargs)
        elif self.strategy == PaginationStrategy.HYBRID:
            return self.paginate_hybrid(page, per_page, cursor, **kwargs)
        else:
            return self.paginate_offset(page, per_page)
    
    # ==================== Utility Methods ====================
    
    def _get_total_count(self, estimate: bool = False) -> int:
        """
        Get total count of items.
        
        Args:
            estimate: Whether to use estimation for large datasets
            
        Returns:
            Total count or estimate
        """
        if estimate and self.enable_count_estimation:
            # Try fast count first
            count = self._fast_count()
            if count > self.count_threshold:
                return self._estimate_count()
        
        return self.query.count()
    
    def _fast_count(self) -> int:
        """
        Fast count using COUNT(*) without offset/limit.
        
        Returns:
            Exact count
        """
        count_query = self.query.statement.with_only_columns([func.count()]).order_by(None)
        return self.query.session.execute(count_query).scalar()
    
    def _estimate_count(self) -> int:
        """
        Estimate count for very large datasets.
        
        Uses database statistics for estimation.
        
        Returns:
            Estimated count
        """
        # PostgreSQL: Use reltuples from pg_class
        # MySQL: Use information_schema
        # For now, return a large number
        return 1000000  # Placeholder
    
    def prefetch_adjacent_pages(
        self,
        current_page: int,
        per_page: int,
        prefetch_count: int = 1
    ) -> Dict[int, List[ModelType]]:
        """
        Prefetch adjacent pages for caching.
        
        Args:
            current_page: Current page number
            per_page: Items per page
            prefetch_count: Number of pages to prefetch on each side
            
        Returns:
            Dictionary mapping page numbers to items
        """
        pages = {}
        
        for i in range(-prefetch_count, prefetch_count + 1):
            page_num = current_page + i
            if page_num > 0:
                offset = (page_num - 1) * per_page
                items = self.query.offset(offset).limit(per_page).all()
                pages[page_num] = items
        
        return pages
    
    def get_page_boundaries(
        self,
        total_items: int,
        per_page: int
    ) -> List[Dict[str, int]]:
        """
        Get boundaries for all pages.
        
        Args:
            total_items: Total number of items
            per_page: Items per page
            
        Returns:
            List of page boundaries
        """
        boundaries = []
        total_pages = (total_items + per_page - 1) // per_page
        
        for page in range(1, total_pages + 1):
            start = (page - 1) * per_page
            end = min(start + per_page, total_items)
            boundaries.append({
                "page": page,
                "start": start,
                "end": end,
                "count": end - start
            })
        
        return boundaries


class PageSizeOptimizer:
    """Optimizer for dynamic page size adjustment."""
    
    def __init__(
        self,
        min_size: int = 10,
        max_size: int = 100,
        default_size: int = 50
    ):
        self.min_size = min_size
        self.max_size = max_size
        self.default_size = default_size
    
    def optimize(
        self,
        total_items: int,
        user_preference: Optional[int] = None,
        device_type: Optional[str] = None
    ) -> int:
        """
        Calculate optimal page size.
        
        Args:
            total_items: Total number of items
            user_preference: User's preferred page size
            device_type: Device type (mobile, tablet, desktop)
            
        Returns:
            Optimized page size
        """
        # Start with user preference or default
        size = user_preference or self.default_size
        
        # Adjust for device type
        if device_type == "mobile":
            size = min(size, 20)
        elif device_type == "tablet":
            size = min(size, 50)
        
        # Adjust for total items
        if total_items < size:
            size = max(self.min_size, total_items)
        
        # Clamp to bounds
        return max(self.min_size, min(size, self.max_size))


class PaginationCache:
    """Cache for paginated results."""
    
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[PaginatedResult]:
        """Get cached result."""
        if key in self._cache:
            cached = self._cache[key]
            if datetime.utcnow().timestamp() - cached["timestamp"] < self.ttl:
                return cached["result"]
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, result: PaginatedResult) -> None:
        """Cache result."""
        self._cache[key] = {
            "result": result,
            "timestamp": datetime.utcnow().timestamp()
        }
    
    def invalidate(self, pattern: Optional[str] = None) -> None:
        """Invalidate cache entries."""
        if pattern:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
        else:
            self._cache.clear()
    
    def get_cache_key(
        self,
        query_hash: str,
        page: int,
        per_page: int,
        **kwargs
    ) -> str:
        """Generate cache key."""
        import hashlib
        
        key_data = f"{query_hash}:{page}:{per_page}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()