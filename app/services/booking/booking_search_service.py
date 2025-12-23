"""
Booking search & filtering service.

Enhanced with:
- Advanced filtering and sorting
- Query optimization
- Caching for repeated searches
- Performance monitoring
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime
import logging
from functools import lru_cache
import hashlib
import json

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingRepository
from app.models.booking.booking import Booking as BookingModel
from app.schemas.booking.booking_filters import (
    BookingFilterParams,
    BookingSearchRequest,
    BookingSortOptions
)
from app.schemas.booking.booking_response import BookingListItem

logger = logging.getLogger(__name__)


class BookingSearchService(BaseService[BookingModel, BookingRepository]):
    """
    Search, list, and export-oriented booking queries.
    
    Features:
    - Advanced filtering with multiple criteria
    - Optimized sorting and pagination
    - Search result caching
    - Export data preparation
    """

    def __init__(self, repository: BookingRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._search_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_search_request(self, request: BookingSearchRequest) -> Optional[ServiceError]:
        """Validate search request parameters."""
        # Validate date ranges
        if hasattr(request, 'check_in_from') and hasattr(request, 'check_in_to'):
            if request.check_in_from and request.check_in_to:
                if request.check_in_from > request.check_in_to:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="check_in_from must be before check_in_to",
                        severity=ErrorSeverity.ERROR,
                        details={"check_in_from": str(request.check_in_from), "check_in_to": str(request.check_in_to)}
                    )

        # Validate pagination
        if hasattr(request, 'page') and request.page is not None:
            if request.page < 1:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Page must be >= 1",
                    severity=ErrorSeverity.ERROR,
                    details={"page": request.page}
                )

        if hasattr(request, 'page_size') and request.page_size is not None:
            if request.page_size < 1 or request.page_size > 1000:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Page size must be between 1 and 1000",
                    severity=ErrorSeverity.ERROR,
                    details={"page_size": request.page_size}
                )

        return None

    def _validate_filter_params(self, filters: BookingFilterParams) -> Optional[ServiceError]:
        """Validate filter parameters."""
        # Validate date ranges in filters
        if hasattr(filters, 'created_after') and hasattr(filters, 'created_before'):
            if filters.created_after and filters.created_before:
                if filters.created_after > filters.created_before:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="created_after must be before created_before",
                        severity=ErrorSeverity.ERROR
                    )

        # Validate price ranges
        if hasattr(filters, 'min_price') and hasattr(filters, 'max_price'):
            if filters.min_price is not None and filters.max_price is not None:
                if filters.min_price < 0 or filters.max_price < 0:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Price values must be non-negative",
                        severity=ErrorSeverity.ERROR
                    )
                if filters.min_price > filters.max_price:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="min_price must be <= max_price",
                        severity=ErrorSeverity.ERROR
                    )

        return None

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def _generate_cache_key(self, request: Any) -> str:
        """Generate a cache key from request parameters."""
        try:
            # Convert request to dict and create hash
            request_dict = request.dict() if hasattr(request, 'dict') else vars(request)
            request_json = json.dumps(request_dict, sort_keys=True, default=str)
            return hashlib.md5(request_json.encode()).hexdigest()
        except Exception:
            # If serialization fails, return unique key to skip cache
            return str(datetime.utcnow().timestamp())

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get result from cache if valid."""
        if cache_key in self._search_cache:
            cached_data, cached_time = self._search_cache[cache_key]
            age = (datetime.utcnow() - cached_time).total_seconds()
            
            if age < self._cache_ttl:
                self._logger.debug(f"Cache hit for key {cache_key[:8]}... (age: {age:.1f}s)")
                return cached_data
            else:
                # Remove expired entry
                del self._search_cache[cache_key]
                self._logger.debug(f"Cache expired for key {cache_key[:8]}...")
        
        return None

    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set cache entry."""
        self._search_cache[cache_key] = (data, datetime.utcnow())
        
        # Limit cache size (keep last 100 entries)
        if len(self._search_cache) > 100:
            oldest_key = min(self._search_cache.keys(), key=lambda k: self._search_cache[k][1])
            del self._search_cache[oldest_key]

    def clear_cache(self) -> None:
        """Clear search cache."""
        self._search_cache.clear()
        self._logger.info("Search cache cleared")

    # -------------------------------------------------------------------------
    # Search Operations
    # -------------------------------------------------------------------------

    def search(
        self,
        request: BookingSearchRequest,
        use_cache: bool = True,
    ) -> ServiceResult[List[BookingListItem]]:
        """
        Search bookings with advanced criteria.
        
        Args:
            request: Search request with filters and options
            use_cache: Whether to use cached results
            
        Returns:
            ServiceResult containing list of BookingListItem or error
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate request
            validation_error = self._validate_search_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            # Check cache
            cache_key = self._generate_cache_key(request) if use_cache else None
            if cache_key and use_cache:
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    return ServiceResult.success(
                        cached_result,
                        metadata={
                            "count": len(cached_result),
                            "cached": True,
                            "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
                        }
                    )

            self._logger.info(
                "Executing booking search",
                extra={
                    "filters": request.dict() if hasattr(request, 'dict') else None
                }
            )

            # Execute search
            items = self.repository.search(request)
            
            # Cache results
            if cache_key and use_cache:
                self._set_cache(cache_key, items)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self._logger.info(
                f"Search completed: {len(items)} results in {duration_ms:.2f}ms",
                extra={
                    "result_count": len(items),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "cached": False,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            self._logger.error(f"Error during booking search: {str(e)}", exc_info=True)
            return self._handle_exception(e, "search bookings")

    def list_with_filters(
        self,
        filters: BookingFilterParams,
        sort: Optional[BookingSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
        use_cache: bool = True,
    ) -> ServiceResult[List[BookingListItem]]:
        """
        List bookings with advanced filtering and sorting.
        
        Args:
            filters: Filter parameters
            sort: Sort options
            page: Page number (1-indexed)
            page_size: Items per page
            use_cache: Whether to use cached results
            
        Returns:
            ServiceResult containing list of BookingListItem or error
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate filters
            validation_error = self._validate_filter_params(filters)
            if validation_error:
                return ServiceResult.failure(validation_error)

            # Validate pagination
            if page < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page must be >= 1",
                        severity=ErrorSeverity.ERROR,
                        details={"page": page}
                    )
                )

            if page_size < 1 or page_size > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page size must be between 1 and 1000",
                        severity=ErrorSeverity.ERROR,
                        details={"page_size": page_size}
                    )
                )

            # Generate cache key
            cache_data = {
                "filters": filters.dict() if hasattr(filters, 'dict') else vars(filters),
                "sort": sort.dict() if sort and hasattr(sort, 'dict') else None,
                "page": page,
                "page_size": page_size
            }
            cache_key = hashlib.md5(
                json.dumps(cache_data, sort_keys=True, default=str).encode()
            ).hexdigest() if use_cache else None

            # Check cache
            if cache_key and use_cache:
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    return ServiceResult.success(
                        cached_result,
                        metadata={
                            "count": len(cached_result),
                            "page": page,
                            "page_size": page_size,
                            "has_more": len(cached_result) == page_size,
                            "cached": True
                        }
                    )

            self._logger.info(
                "Listing bookings with filters",
                extra={
                    "page": page,
                    "page_size": page_size,
                    "filter_count": len(cache_data["filters"])
                }
            )

            # Execute query
            items = self.repository.list_with_filters(filters, sort=sort, page=page, page_size=page_size)
            
            # Cache results
            if cache_key and use_cache:
                self._set_cache(cache_key, items)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "page": page,
                    "page_size": page_size,
                    "has_more": len(items) == page_size,
                    "cached": False,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            self._logger.error(f"Error listing bookings with filters: {str(e)}", exc_info=True)
            return self._handle_exception(e, "list bookings with filters")

    # -------------------------------------------------------------------------
    # Advanced Search Operations
    # -------------------------------------------------------------------------

    def search_by_guest(
        self,
        guest_name: str,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[List[BookingListItem]]:
        """
        Search bookings by guest name.
        
        Args:
            guest_name: Guest name to search for
            hostel_id: Optional hostel filter
            
        Returns:
            ServiceResult containing list of BookingListItem or error
        """
        try:
            if not guest_name or len(guest_name.strip()) < 2:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Guest name must be at least 2 characters",
                        severity=ErrorSeverity.ERROR
                    )
                )

            self._logger.debug(f"Searching bookings by guest name: {guest_name}")

            items = self.repository.search_by_guest(guest_name, hostel_id=hostel_id)

            return ServiceResult.success(
                items,
                metadata={"count": len(items), "search_term": guest_name}
            )

        except Exception as e:
            self._logger.error(f"Error searching by guest name: {str(e)}", exc_info=True)
            return self._handle_exception(e, "search by guest name")

    def get_upcoming_bookings(
        self,
        hostel_id: UUID,
        days: int = 7,
    ) -> ServiceResult[List[BookingListItem]]:
        """
        Get upcoming bookings for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            days: Number of days to look ahead
            
        Returns:
            ServiceResult containing list of BookingListItem or error
        """
        try:
            if days < 1 or days > 365:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Days must be between 1 and 365",
                        severity=ErrorSeverity.ERROR,
                        details={"days": days}
                    )
                )

            self._logger.debug(f"Fetching upcoming bookings for hostel {hostel_id} (next {days} days)")

            items = self.repository.get_upcoming_bookings(hostel_id, days=days)

            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "hostel_id": str(hostel_id),
                    "days": days
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching upcoming bookings: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get upcoming bookings", hostel_id)

    def export_bookings(
        self,
        filters: BookingFilterParams,
        format: str = "csv",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Prepare booking data for export.
        
        Args:
            filters: Filter parameters
            format: Export format (csv, excel, json)
            
        Returns:
            ServiceResult containing export data or error
        """
        try:
            if format not in ["csv", "excel", "json"]:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Invalid export format",
                        severity=ErrorSeverity.ERROR,
                        details={"format": format, "allowed": ["csv", "excel", "json"]}
                    )
                )

            self._logger.info(f"Preparing booking export in {format} format")

            export_data = self.repository.prepare_export(filters, format=format)

            return ServiceResult.success(
                export_data,
                message=f"Export data prepared in {format} format"
            )

        except Exception as e:
            self._logger.error(f"Error preparing export: {str(e)}", exc_info=True)
            return self._handle_exception(e, "export bookings")