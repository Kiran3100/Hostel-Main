"""
Advanced filtering engine with dynamic criteria and search optimization.

Provides sophisticated filtering with full-text search, fuzzy matching,
and geospatial capabilities.
"""

from typing import Any, Dict, List, Optional, Type, Union, Callable, TypedDict
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
import re

from sqlalchemy import and_, or_, not_, func, cast, String, Date
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import ClauseElement

from app.models.base import BaseModel
from app.core.logging import get_logger

logger = get_logger(__name__)


class FilterCriteria(TypedDict, total=False):
    """Type definition for filter criteria dictionary."""
    is_active: bool
    featured_only: bool
    has_availability: bool
    required_beds: int
    city: str
    state: str
    lat: float
    lng: float
    radius: float
    min_price: Decimal
    max_price: Decimal
    hostel_type: str
    amenities: List[str]
    min_rating: float
    sort_by: str
    sort_order: str


class FilterOperator(str, Enum):
    """Filter operation types."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    ILIKE = "ilike"
    NOT_LIKE = "not_like"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    FUZZY = "fuzzy"


class FilterType(str, Enum):
    """Filter value types."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ARRAY = "array"
    OBJECT = "object"


class Filter:
    """Single filter condition."""
    
    def __init__(
        self,
        field: str,
        operator: FilterOperator,
        value: Any,
        filter_type: Optional[FilterType] = None,
        case_sensitive: bool = False
    ):
        self.field = field
        self.operator = operator
        self.value = value
        self.filter_type = filter_type
        self.case_sensitive = case_sensitive
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "type": self.filter_type.value if self.filter_type else None,
            "case_sensitive": self.case_sensitive
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Filter":
        """Create from dictionary."""
        return cls(
            field=data["field"],
            operator=FilterOperator(data["operator"]),
            value=data["value"],
            filter_type=FilterType(data["type"]) if data.get("type") else None,
            case_sensitive=data.get("case_sensitive", False)
        )


class FilterGroup:
    """Group of filters with AND/OR logic."""
    
    def __init__(
        self,
        filters: List[Union[Filter, "FilterGroup"]],
        logic: str = "AND"
    ):
        self.filters = filters
        self.logic = logic.upper()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "logic": self.logic,
            "filters": [f.to_dict() for f in self.filters]
        }


class FilterEngine:
    """
    Advanced filtering engine with dynamic criteria.
    
    Supports complex filtering with multiple operators,
    types, and search strategies.
    """
    
    def __init__(self, model: Type[BaseModel]):
        self.model = model
        self._operator_map = {
            FilterOperator.EQUALS: self._apply_equals,
            FilterOperator.NOT_EQUALS: self._apply_not_equals,
            FilterOperator.GREATER_THAN: self._apply_greater_than,
            FilterOperator.GREATER_THAN_EQUAL: self._apply_greater_than_equal,
            FilterOperator.LESS_THAN: self._apply_less_than,
            FilterOperator.LESS_THAN_EQUAL: self._apply_less_than_equal,
            FilterOperator.IN: self._apply_in,
            FilterOperator.NOT_IN: self._apply_not_in,
            FilterOperator.LIKE: self._apply_like,
            FilterOperator.ILIKE: self._apply_ilike,
            FilterOperator.NOT_LIKE: self._apply_not_like,
            FilterOperator.BETWEEN: self._apply_between,
            FilterOperator.IS_NULL: self._apply_is_null,
            FilterOperator.IS_NOT_NULL: self._apply_is_not_null,
            FilterOperator.CONTAINS: self._apply_contains,
            FilterOperator.STARTS_WITH: self._apply_starts_with,
            FilterOperator.ENDS_WITH: self._apply_ends_with,
            FilterOperator.REGEX: self._apply_regex,
            FilterOperator.FUZZY: self._apply_fuzzy,
        }
    
    # ==================== Main Filter Application ====================
    
    def apply_filters(
        self,
        query: Query,
        filters: List[Union[Filter, FilterGroup]]
    ) -> Query:
        """
        Apply filters to query.
        
        Args:
            query: Base query
            filters: List of filters or filter groups
            
        Returns:
            Filtered query
        """
        for filter_item in filters:
            if isinstance(filter_item, Filter):
                query = self._apply_single_filter(query, filter_item)
            elif isinstance(filter_item, FilterGroup):
                query = self._apply_filter_group(query, filter_item)
        
        return query
    
    def _apply_single_filter(self, query: Query, filter: Filter) -> Query:
        """Apply single filter to query."""
        if not hasattr(self.model, filter.field):
            logger.warning(f"Field {filter.field} not found on {self.model.__name__}")
            return query
        
        operator_func = self._operator_map.get(filter.operator)
        if not operator_func:
            logger.warning(f"Operator {filter.operator} not supported")
            return query
        
        condition = operator_func(filter)
        if condition is not None:
            query = query.filter(condition)
        
        return query
    
    def _apply_filter_group(self, query: Query, group: FilterGroup) -> Query:
        """Apply filter group to query."""
        conditions = []
        
        for filter_item in group.filters:
            if isinstance(filter_item, Filter):
                operator_func = self._operator_map.get(filter_item.operator)
                if operator_func:
                    condition = operator_func(filter_item)
                    if condition is not None:
                        conditions.append(condition)
            elif isinstance(filter_item, FilterGroup):
                # Recursively handle nested groups
                sub_conditions = []
                for sub_filter in filter_item.filters:
                    if isinstance(sub_filter, Filter):
                        operator_func = self._operator_map.get(sub_filter.operator)
                        if operator_func:
                            condition = operator_func(sub_filter)
                            if condition is not None:
                                sub_conditions.append(condition)
                
                if sub_conditions:
                    if filter_item.logic == "AND":
                        conditions.append(and_(*sub_conditions))
                    else:
                        conditions.append(or_(*sub_conditions))
        
        if conditions:
            if group.logic == "AND":
                query = query.filter(and_(*conditions))
            else:
                query = query.filter(or_(*conditions))
        
        return query
    
    # ==================== Operator Implementations ====================
    
    def _apply_equals(self, filter: Filter) -> ClauseElement:
        """Apply equals operator."""
        column = getattr(self.model, filter.field)
        return column == filter.value
    
    def _apply_not_equals(self, filter: Filter) -> ClauseElement:
        """Apply not equals operator."""
        column = getattr(self.model, filter.field)
        return column != filter.value
    
    def _apply_greater_than(self, filter: Filter) -> ClauseElement:
        """Apply greater than operator."""
        column = getattr(self.model, filter.field)
        return column > filter.value
    
    def _apply_greater_than_equal(self, filter: Filter) -> ClauseElement:
        """Apply greater than or equal operator."""
        column = getattr(self.model, filter.field)
        return column >= filter.value
    
    def _apply_less_than(self, filter: Filter) -> ClauseElement:
        """Apply less than operator."""
        column = getattr(self.model, filter.field)
        return column < filter.value
    
    def _apply_less_than_equal(self, filter: Filter) -> ClauseElement:
        """Apply less than or equal operator."""
        column = getattr(self.model, filter.field)
        return column <= filter.value
    
    def _apply_in(self, filter: Filter) -> ClauseElement:
        """Apply IN operator."""
        column = getattr(self.model, filter.field)
        if not isinstance(filter.value, (list, tuple)):
            filter.value = [filter.value]
        return column.in_(filter.value)
    
    def _apply_not_in(self, filter: Filter) -> ClauseElement:
        """Apply NOT IN operator."""
        column = getattr(self.model, filter.field)
        if not isinstance(filter.value, (list, tuple)):
            filter.value = [filter.value]
        return ~column.in_(filter.value)
    
    def _apply_like(self, filter: Filter) -> ClauseElement:
        """Apply LIKE operator."""
        column = getattr(self.model, filter.field)
        return column.like(filter.value)
    
    def _apply_ilike(self, filter: Filter) -> ClauseElement:
        """Apply ILIKE operator (case-insensitive)."""
        column = getattr(self.model, filter.field)
        return column.ilike(filter.value)
    
    def _apply_not_like(self, filter: Filter) -> ClauseElement:
        """Apply NOT LIKE operator."""
        column = getattr(self.model, filter.field)
        return ~column.like(filter.value)
    
    def _apply_between(self, filter: Filter) -> ClauseElement:
        """Apply BETWEEN operator."""
        if not isinstance(filter.value, (list, tuple)) or len(filter.value) != 2:
            logger.error("BETWEEN requires array of 2 values")
            return None
        
        column = getattr(self.model, filter.field)
        return and_(column >= filter.value[0], column <= filter.value[1])
    
    def _apply_is_null(self, filter: Filter) -> ClauseElement:
        """Apply IS NULL operator."""
        column = getattr(self.model, filter.field)
        return column.is_(None)
    
    def _apply_is_not_null(self, filter: Filter) -> ClauseElement:
        """Apply IS NOT NULL operator."""
        column = getattr(self.model, filter.field)
        return column.isnot(None)
    
    def _apply_contains(self, filter: Filter) -> ClauseElement:
        """Apply CONTAINS operator (substring search)."""
        column = getattr(self.model, filter.field)
        pattern = f"%{filter.value}%"
        if filter.case_sensitive:
            return column.like(pattern)
        return column.ilike(pattern)
    
    def _apply_starts_with(self, filter: Filter) -> ClauseElement:
        """Apply STARTS WITH operator."""
        column = getattr(self.model, filter.field)
        pattern = f"{filter.value}%"
        if filter.case_sensitive:
            return column.like(pattern)
        return column.ilike(pattern)
    
    def _apply_ends_with(self, filter: Filter) -> ClauseElement:
        """Apply ENDS WITH operator."""
        column = getattr(self.model, filter.field)
        pattern = f"%{filter.value}"
        if filter.case_sensitive:
            return column.like(pattern)
        return column.ilike(pattern)
    
    def _apply_regex(self, filter: Filter) -> ClauseElement:
        """Apply REGEX operator."""
        column = getattr(self.model, filter.field)
        # PostgreSQL regex operator
        return column.op('~')(filter.value)
    
    def _apply_fuzzy(self, filter: Filter) -> ClauseElement:
        """Apply fuzzy matching using Levenshtein distance."""
        column = getattr(self.model, filter.field)
        # This requires pg_trgm extension in PostgreSQL
        # similarity(column, value) > threshold
        threshold = 0.3  # Default threshold
        return func.similarity(column, filter.value) > threshold
    
    # ==================== Search Methods ====================
    
    def full_text_search(
        self,
        query: Query,
        search_term: str,
        fields: List[str],
        language: str = "english"
    ) -> Query:
        """
        Full-text search across multiple fields.
        
        Args:
            query: Base query
            search_term: Search term
            fields: Fields to search in
            language: Language for text search
            
        Returns:
            Filtered query with relevance ranking
        """
        # PostgreSQL full-text search
        search_vectors = []
        
        for field in fields:
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                vector = func.to_tsvector(language, column)
                search_vectors.append(vector)
        
        if not search_vectors:
            return query
        
        # Combine search vectors
        combined_vector = search_vectors[0]
        for vector in search_vectors[1:]:
            combined_vector = combined_vector.op('||')(vector)
        
        # Create search query
        search_query = func.plainto_tsquery(language, search_term)
        
        # Apply filter and ranking
        query = query.filter(combined_vector.op('@@')(search_query))
        query = query.order_by(
            func.ts_rank(combined_vector, search_query).desc()
        )
        
        return query
    
    def fuzzy_search(
        self,
        query: Query,
        search_term: str,
        field: str,
        threshold: float = 0.3
    ) -> Query:
        """
        Fuzzy search using similarity.
        
        Args:
            query: Base query
            search_term: Search term
            field: Field to search in
            threshold: Similarity threshold (0-1)
            
        Returns:
            Filtered query
        """
        if not hasattr(self.model, field):
            return query
        
        column = getattr(self.model, field)
        query = query.filter(func.similarity(column, search_term) > threshold)
        query = query.order_by(func.similarity(column, search_term).desc())
        
        return query
    
    def range_filter(
        self,
        query: Query,
        field: str,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None,
        inclusive: bool = True
    ) -> Query:
        """
        Apply range filter.
        
        Args:
            query: Base query
            field: Field to filter
            min_value: Minimum value
            max_value: Maximum value
            inclusive: Whether to include boundaries
            
        Returns:
            Filtered query
        """
        if not hasattr(self.model, field):
            return query
        
        column = getattr(self.model, field)
        
        if min_value is not None:
            if inclusive:
                query = query.filter(column >= min_value)
            else:
                query = query.filter(column > min_value)
        
        if max_value is not None:
            if inclusive:
                query = query.filter(column <= max_value)
            else:
                query = query.filter(column < max_value)
        
        return query
    
    def date_range_filter(
        self,
        query: Query,
        field: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Query:
        """
        Apply date range filter.
        
        Args:
            query: Base query
            field: Date field
            start_date: Start date
            end_date: End date
            
        Returns:
            Filtered query
        """
        if not hasattr(self.model, field):
            return query
        
        column = getattr(self.model, field)
        
        if start_date:
            query = query.filter(func.date(column) >= start_date)
        
        if end_date:
            query = query.filter(func.date(column) <= end_date)
        
        return query
    
    def geospatial_filter(
        self,
        query: Query,
        latitude: float,
        longitude: float,
        radius_km: float,
        lat_field: str = "latitude",
        lon_field: str = "longitude"
    ) -> Query:
        """
        Filter by geographic proximity.
        
        Args:
            query: Base query
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Radius in kilometers
            lat_field: Latitude field name
            lon_field: Longitude field name
            
        Returns:
            Filtered query
        """
        if not (hasattr(self.model, lat_field) and hasattr(self.model, lon_field)):
            return query
        
        # Haversine formula
        lat_col = getattr(self.model, lat_field)
        lon_col = getattr(self.model, lon_field)
        
        distance = func.acos(
            func.sin(func.radians(latitude)) * func.sin(func.radians(lat_col)) +
            func.cos(func.radians(latitude)) * func.cos(func.radians(lat_col)) *
            func.cos(func.radians(longitude) - func.radians(lon_col))
        ) * 6371  # Earth radius in km
        
        query = query.filter(distance <= radius_km)
        query = query.order_by(distance)
        
        return query


class SearchQueryBuilder:
    """Builder for complex search queries."""
    
    def __init__(self, model: Type[BaseModel]):
        self.model = model
        self.filter_engine = FilterEngine(model)
        self._filters: List[Union[Filter, FilterGroup]] = []
        self._search_term: Optional[str] = None
        self._search_fields: List[str] = []
        self._fuzzy_fields: Dict[str, float] = {}
        self._geo_filter: Optional[Dict[str, Any]] = None
    
    def add_filter(
        self,
        field: str,
        operator: FilterOperator,
        value: Any
    ) -> "SearchQueryBuilder":
        """Add filter."""
        self._filters.append(Filter(field, operator, value))
        return self
    
    def add_text_search(
        self,
        search_term: str,
        fields: List[str]
    ) -> "SearchQueryBuilder":
        """Add full-text search."""
        self._search_term = search_term
        self._search_fields = fields
        return self
    
    def add_fuzzy_search(
        self,
        field: str,
        threshold: float = 0.3
    ) -> "SearchQueryBuilder":
        """Add fuzzy search for field."""
        self._fuzzy_fields[field] = threshold
        return self
    
    def add_geo_filter(
        self,
        latitude: float,
        longitude: float,
        radius_km: float
    ) -> "SearchQueryBuilder":
        """Add geospatial filter."""
        self._geo_filter = {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km
        }
        return self
    
    def build(self, base_query: Query) -> Query:
        """Build final query."""
        query = base_query
        
        # Apply filters
        if self._filters:
            query = self.filter_engine.apply_filters(query, self._filters)
        
        # Apply text search
        if self._search_term and self._search_fields:
            query = self.filter_engine.full_text_search(
                query,
                self._search_term,
                self._search_fields
            )
        
        # Apply fuzzy search
        for field, threshold in self._fuzzy_fields.items():
            if self._search_term:
                query = self.filter_engine.fuzzy_search(
                    query,
                    self._search_term,
                    field,
                    threshold
                )
        
        # Apply geo filter
        if self._geo_filter:
            query = self.filter_engine.geospatial_filter(
                query,
                **self._geo_filter
            )
        
        return query