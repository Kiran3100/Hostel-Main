"""
Pagination utilities for hostel management system
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime
import base64
import json
from urllib.parse import urlencode

T = TypeVar('T')

@dataclass
class PaginationParams:
    """Pagination parameters"""
    page: int = 1
    page_size: int = 20
    max_page_size: int = 100
    
    def __post_init__(self):
        # Validate and sanitize parameters
        self.page = max(1, self.page)
        self.page_size = min(max(1, self.page_size), self.max_page_size)

@dataclass
class PaginationInfo:
    """Pagination information"""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
    next_page: Optional[int]
    previous_page: Optional[int]
    start_index: int
    end_index: int
    
    @classmethod
    def create(cls, page: int, page_size: int, total_items: int) -> 'PaginationInfo':
        """Create pagination info from basic parameters"""
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
        has_next = page < total_pages
        has_previous = page > 1
        next_page = page + 1 if has_next else None
        previous_page = page - 1 if has_previous else None
        start_index = (page - 1) * page_size + 1 if total_items > 0 else 0
        end_index = min(page * page_size, total_items)
        
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            next_page=next_page,
            previous_page=previous_page,
            start_index=start_index,
            end_index=end_index
        )

@dataclass
class PaginatedResponse(Generic[T]):
    """Paginated response wrapper"""
    items: List[T]
    pagination: PaginationInfo
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'items': self.items,
            'pagination': {
                'page': self.pagination.page,
                'page_size': self.pagination.page_size,
                'total_items': self.pagination.total_items,
                'total_pages': self.pagination.total_pages,
                'has_next': self.pagination.has_next,
                'has_previous': self.pagination.has_previous,
                'next_page': self.pagination.next_page,
                'previous_page': self.pagination.previous_page,
                'start_index': self.pagination.start_index,
                'end_index': self.pagination.end_index
            }
        }

class PaginationHelper:
    """Main pagination utilities"""
    
    @staticmethod
    def paginate_list(items: List[T], page: int = 1, 
                     page_size: int = 20) -> PaginatedResponse[T]:
        """Paginate a list of items"""
        total_items = len(items)
        pagination_info = PaginationInfo.create(page, page_size, total_items)
        
        # Calculate slice indices
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        paginated_items = items[start_idx:end_idx]
        
        return PaginatedResponse(
            items=paginated_items,
            pagination=pagination_info
        )
    
    @staticmethod
    def get_page_range(current_page: int, total_pages: int, 
                      max_pages: int = 10) -> List[int]:
        """Get range of page numbers for pagination UI"""
        if total_pages <= max_pages:
            return list(range(1, total_pages + 1))
        
        # Calculate start and end pages
        half_range = max_pages // 2
        start_page = max(1, current_page - half_range)
        end_page = min(total_pages, start_page + max_pages - 1)
        
        # Adjust start_page if we're near the end
        if end_page - start_page + 1 < max_pages:
            start_page = max(1, end_page - max_pages + 1)
        
        return list(range(start_page, end_page + 1))
    
    @staticmethod
    def get_pagination_summary(pagination: PaginationInfo) -> str:
        """Get human-readable pagination summary"""
        if pagination.total_items == 0:
            return "No items found"
        
        if pagination.total_items == 1:
            return "Showing 1 item"
        
        return (f"Showing {pagination.start_index} to {pagination.end_index} "
                f"of {pagination.total_items} items")
    
    @staticmethod
    def calculate_offset_limit(page: int, page_size: int) -> Tuple[int, int]:
        """Calculate offset and limit for database queries"""
        offset = (page - 1) * page_size
        limit = page_size
        return offset, limit
    
    @staticmethod
    def build_pagination_urls(base_url: str, current_page: int, 
                            total_pages: int, query_params: Dict[str, Any] = None,
                            page_param: str = 'page') -> Dict[str, Optional[str]]:
        """Build pagination URLs"""
        query_params = query_params or {}
        
        def build_url(page: int) -> str:
            params = query_params.copy()
            params[page_param] = page
            return f"{base_url}?{urlencode(params)}"
        
        return {
            'first': build_url(1) if total_pages > 0 else None,
            'previous': build_url(current_page - 1) if current_page > 1 else None,
            'current': build_url(current_page),
            'next': build_url(current_page + 1) if current_page < total_pages else None,
            'last': build_url(total_pages) if total_pages > 0 else None
        }

class CursorPaginator:
    """Cursor-based pagination for large datasets"""
    
    def __init__(self, cursor_field: str = 'id', cursor_direction: str = 'asc'):
        self.cursor_field = cursor_field
        self.cursor_direction = cursor_direction.lower()
    
    def encode_cursor(self, cursor_value: Any) -> str:
        """Encode cursor value to string"""
        cursor_data = {
            'value': cursor_value,
            'field': self.cursor_field,
            'direction': self.cursor_direction,
            'timestamp': datetime.now().isoformat()
        }
        
        json_str = json.dumps(cursor_data, default=str)
        return base64.urlsafe_b64encode(json_str.encode()).decode()
    
    def decode_cursor(self, cursor_string: str) -> Dict[str, Any]:
        """Decode cursor string to value"""
        try:
            json_str = base64.urlsafe_b64decode(cursor_string.encode()).decode()
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            raise ValueError("Invalid cursor format")
    
    def get_cursor_filter(self, cursor: Optional[str]) -> Dict[str, Any]:
        """Get filter conditions for cursor-based query"""
        if not cursor:
            return {}
        
        cursor_data = self.decode_cursor(cursor)
        cursor_value = cursor_data['value']
        
        if self.cursor_direction == 'asc':
            return {f"{self.cursor_field}__gt": cursor_value}
        else:
            return {f"{self.cursor_field}__lt": cursor_value}
    
    def paginate_queryset(self, queryset, cursor: Optional[str] = None, 
                         page_size: int = 20) -> Dict[str, Any]:
        """Paginate queryset using cursor"""
        # Apply cursor filter
        cursor_filter = self.get_cursor_filter(cursor)
        if cursor_filter:
            queryset = queryset.filter(**cursor_filter)
        
        # Order by cursor field
        order_field = self.cursor_field
        if self.cursor_direction == 'desc':
            order_field = f"-{order_field}"
        
        queryset = queryset.order_by(order_field)
        
        # Get one extra item to check if there's a next page
        items = list(queryset[:page_size + 1])
        
        has_next = len(items) > page_size
        if has_next:
            items = items[:page_size]
        
        # Generate next cursor
        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            cursor_value = getattr(last_item, self.cursor_field)
            next_cursor = self.encode_cursor(cursor_value)
        
        return {
            'items': items,
            'has_next': has_next,
            'next_cursor': next_cursor,
            'page_size': page_size
        }

class OffsetPaginator:
    """Traditional offset-based pagination"""
    
    def __init__(self, default_page_size: int = 20, max_page_size: int = 100):
        self.default_page_size = default_page_size
        self.max_page_size = max_page_size
    
    def paginate(self, queryset, page: int = 1, 
                page_size: Optional[int] = None) -> PaginatedResponse:
        """Paginate queryset with offset/limit"""
        page_size = page_size or self.default_page_size
        page_size = min(page_size, self.max_page_size)
        page = max(1, page)
        
        # Get total count
        total_items = queryset.count() if hasattr(queryset, 'count') else len(queryset)
        
        # Create pagination info
        pagination_info = PaginationInfo.create(page, page_size, total_items)
        
        # Calculate offset and get items
        offset = (page - 1) * page_size
        
        if hasattr(queryset, 'limit') and hasattr(queryset, 'offset'):
            # Database queryset
            items = list(queryset.offset(offset).limit(page_size))
        else:
            # List or other iterable
            items = list(queryset)[offset:offset + page_size]
        
        return PaginatedResponse(
            items=items,
            pagination=pagination_info
        )

class PageCalculator:
    """Page calculation utilities"""
    
    @staticmethod
    def get_total_pages(total_items: int, page_size: int) -> int:
        """Calculate total number of pages"""
        if page_size <= 0:
            return 0
        return math.ceil(total_items / page_size)
    
    @staticmethod
    def get_page_items_range(page: int, page_size: int) -> Tuple[int, int]:
        """Get start and end indices for page"""
        start = (page - 1) * page_size
        end = start + page_size
        return start, end
    
    @staticmethod
    def validate_page_params(page: int, page_size: int, total_items: int) -> Tuple[int, int]:
        """Validate and adjust page parameters"""
        # Ensure page_size is positive
        page_size = max(1, page_size)
        
        # Calculate max valid page
        total_pages = PageCalculator.get_total_pages(total_items, page_size)
        max_page = max(1, total_pages)
        
        # Ensure page is within valid range
        page = min(max(1, page), max_page)
        
        return page, page_size
    
    @staticmethod
    def get_neighboring_pages(current_page: int, total_pages: int, 
                            neighbors: int = 2) -> Dict[str, List[int]]:
        """Get neighboring page numbers"""
        result = {
            'previous': [],
            'next': []
        }
        
        # Previous pages
        for i in range(max(1, current_page - neighbors), current_page):
            result['previous'].append(i)
        
        # Next pages
        for i in range(current_page + 1, min(total_pages + 1, current_page + neighbors + 1)):
            result['next'].append(i)
        
        return result

class PaginationAnalytics:
    """Analytics for pagination usage"""
    
    def __init__(self):
        self.page_views = {}
        self.jump_patterns = []
    
    def record_page_view(self, page: int, page_size: int, 
                        user_id: Optional[str] = None,
                        timestamp: Optional[datetime] = None):
        """Record page view for analytics"""
        timestamp = timestamp or datetime.now()
        
        view_data = {
            'page': page,
            'page_size': page_size,
            'user_id': user_id,
            'timestamp': timestamp
        }
        
        if page not in self.page_views:
            self.page_views[page] = []
        
        self.page_views[page].append(view_data)
    
    def record_page_jump(self, from_page: int, to_page: int,
                        user_id: Optional[str] = None):
        """Record page navigation patterns"""
        self.jump_patterns.append({
            'from_page': from_page,
            'to_page': to_page,
            'user_id': user_id,
            'timestamp': datetime.now(),
            'jump_distance': abs(to_page - from_page)
        })
    
    def get_popular_pages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequently viewed pages"""
        page_counts = {}
        
        for page, views in self.page_views.items():
            page_counts[page] = len(views)
        
        sorted_pages = sorted(page_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'page': page, 'view_count': count}
            for page, count in sorted_pages[:limit]
        ]
    
    def get_bounce_rate(self) -> float:
        """Calculate bounce rate (single page views)"""
        total_sessions = len(set(
            view['user_id'] for views in self.page_views.values() 
            for view in views if view['user_id']
        ))
        
        if total_sessions == 0:
            return 0.0
        
        single_page_sessions = 0
        user_page_counts = {}
        
        for views in self.page_views.values():
            for view in views:
                user_id = view['user_id']
                if user_id:
                    user_page_counts[user_id] = user_page_counts.get(user_id, 0) + 1
        
        for user_id, page_count in user_page_counts.items():
            if page_count == 1:
                single_page_sessions += 1
        
        return single_page_sessions / total_sessions
    
    def get_average_pages_per_session(self) -> float:
        """Calculate average pages viewed per session"""
        user_page_counts = {}
        
        for views in self.page_views.values():
            for view in views:
                user_id = view['user_id']
                if user_id:
                    user_page_counts[user_id] = user_page_counts.get(user_id, 0) + 1
        
        if not user_page_counts:
            return 0.0
        
        return sum(user_page_counts.values()) / len(user_page_counts)

class PaginationOptimizer:
    """Optimization utilities for pagination performance"""
    
    @staticmethod
    def suggest_page_size(dataset_size: int, user_behavior: Dict[str, Any] = None) -> int:
        """Suggest optimal page size based on dataset and user behavior"""
        # Base suggestions by dataset size
        if dataset_size < 50:
            base_size = dataset_size
        elif dataset_size < 500:
            base_size = 20
        elif dataset_size < 5000:
            base_size = 50
        else:
            base_size = 100
        
        # Adjust based on user behavior if provided
        if user_behavior:
            avg_session_pages = user_behavior.get('avg_session_pages', 3)
            
            # If users typically view many pages, suggest smaller page size
            if avg_session_pages > 5:
                base_size = max(10, base_size // 2)
            # If users typically view few pages, suggest larger page size
            elif avg_session_pages < 2:
                base_size = min(100, base_size * 2)
        
        return base_size
    
    @staticmethod
    def detect_pagination_issues(pagination_analytics: PaginationAnalytics) -> List[str]:
        """Detect potential pagination issues"""
        issues = []
        
        # High bounce rate
        bounce_rate = pagination_analytics.get_bounce_rate()
        if bounce_rate > 0.7:
            issues.append(f"High bounce rate ({bounce_rate:.1%}) - users may not be finding relevant content")
        
        # Low average pages per session
        avg_pages = pagination_analytics.get_average_pages_per_session()
        if avg_pages < 1.5:
            issues.append(f"Low engagement ({avg_pages:.1f} pages per session) - consider improving content discovery")
        
        # Large page jumps
        large_jumps = [
            jump for jump in pagination_analytics.jump_patterns 
            if jump['jump_distance'] > 10
        ]
        
        if len(large_jumps) > len(pagination_analytics.jump_patterns) * 0.2:
            issues.append("Many large page jumps detected - users may be struggling to find content")
        
        # Unpopular later pages
        popular_pages = pagination_analytics.get_popular_pages(20)
        if popular_pages and len(popular_pages) > 5:
            last_five_views = sum(page['view_count'] for page in popular_pages[-5:])
            first_five_views = sum(page['view_count'] for page in popular_pages[:5])
            
            if last_five_views < first_five_views * 0.1:
                issues.append("Later pages receive very few views - consider better sorting or search")
        
        return issues
    
    @staticmethod
    def generate_optimization_recommendations(issues: List[str]) -> List[str]:
        """Generate recommendations based on detected issues"""
        recommendations = []
        
        for issue in issues:
            if "bounce rate" in issue:
                recommendations.append("Improve first page content relevance")
                recommendations.append("Add better filtering/search options")
                recommendations.append("Consider showing previews or summaries")
            
            elif "engagement" in issue:
                recommendations.append("Reduce page size to encourage exploration")
                recommendations.append("Add related content suggestions")
                recommendations.append("Implement infinite scroll for better UX")
            
            elif "page jumps" in issue:
                recommendations.append("Add pagination shortcuts (first, last)")
                recommendations.append("Implement search within results")
                recommendations.append("Add page number input for direct navigation")
            
            elif "later pages" in issue:
                recommendations.append("Improve content sorting algorithm")
                recommendations.append("Add 'most relevant' or 'recommended' sections")
                recommendations.append("Implement faceted search")
        
        return list(set(recommendations))  # Remove duplicates