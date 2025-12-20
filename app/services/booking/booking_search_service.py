# app/services/booking/booking_search_service.py
"""
Booking search service for advanced search and filtering.

Provides powerful search capabilities, saved searches, search analytics,
and intelligent search suggestions.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.base.enums import BookingSource, BookingStatus, RoomType
from app.repositories.booking.booking_repository import (
    BookingRepository,
    BookingSearchCriteria,
)
from app.repositories.base.base_repository import QueryOptions


class BookingSearchService:
    """
    Service for advanced booking search operations.
    
    Responsibilities:
    - Execute complex multi-criteria searches
    - Provide search suggestions
    - Track search patterns
    - Optimize search performance
    - Generate search analytics
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
    ):
        """Initialize search service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
    
    # ==================== SEARCH OPERATIONS ====================
    
    def search_bookings(
        self,
        filters: Optional[Dict] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        include_deleted: bool = False,
    ) -> Dict:
        """
        Execute advanced booking search with multiple filters.
        
        Args:
            filters: Search filter dictionary
            page: Page number (1-indexed)
            page_size: Results per page
            sort_by: Field to sort by
            sort_order: "asc" or "desc"
            include_deleted: Include soft-deleted records
            
        Returns:
            Search results with pagination and metadata
        """
        filters = filters or {}
        
        # Build search criteria
        criteria = self._build_search_criteria(filters)
        
        # Determine order_by
        order_by = self._build_order_by(sort_by, sort_order)
        
        # Build query options
        options = QueryOptions(
            include_deleted=include_deleted,
            prefetch_relationships=["visitor", "hostel", "guest_info"],
        )
        
        # Execute search
        bookings, total = self.booking_repo.search_bookings(
            criteria, page, page_size, order_by, options
        )
        
        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "results": bookings,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "filters_applied": self._get_applied_filters_summary(filters),
            "sort": {"field": sort_by, "order": sort_order} if sort_by else None,
        }
    
    def _build_search_criteria(self, filters: Dict) -> BookingSearchCriteria:
        """Build search criteria from filter dictionary."""
        return BookingSearchCriteria(
            booking_reference=filters.get("booking_reference"),
            visitor_id=UUID(filters["visitor_id"]) if filters.get("visitor_id") else None,
            hostel_id=UUID(filters["hostel_id"]) if filters.get("hostel_id") else None,
            hostel_ids=[UUID(hid) for hid in filters.get("hostel_ids", [])],
            status=BookingStatus(filters["status"]) if filters.get("status") else None,
            statuses=[BookingStatus(s) for s in filters.get("statuses", [])],
            source=BookingSource(filters["source"]) if filters.get("source") else None,
            room_type=RoomType(filters["room_type"]) if filters.get("room_type") else None,
            check_in_date_from=self._parse_date(filters.get("check_in_date_from")),
            check_in_date_to=self._parse_date(filters.get("check_in_date_to")),
            booking_date_from=self._parse_datetime(filters.get("booking_date_from")),
            booking_date_to=self._parse_datetime(filters.get("booking_date_to")),
            advance_paid=filters.get("advance_paid"),
            converted_to_student=filters.get("converted_to_student"),
            min_amount=float(filters["min_amount"]) if filters.get("min_amount") else None,
            max_amount=float(filters["max_amount"]) if filters.get("max_amount") else None,
            expiring_within_hours=filters.get("expiring_within_hours"),
            is_expired=filters.get("is_expired"),
            referral_code=filters.get("referral_code"),
            guest_email=filters.get("guest_email"),
            guest_phone=filters.get("guest_phone"),
        )
    
    def _build_order_by(self, sort_by: Optional[str], sort_order: str) -> Optional[List[str]]:
        """Build order_by list for query."""
        if not sort_by:
            return None
        
        # Map frontend field names to model field names
        field_mapping = {
            "booking_reference": "booking_reference",
            "created_at": "created_at",
            "check_in_date": "preferred_check_in_date",
            "total_amount": "total_amount",
            "status": "booking_status",
        }
        
        field = field_mapping.get(sort_by, sort_by)
        
        if sort_order.lower() == "desc":
            return [f"-{field}"]
        else:
            return [field]
    
    def _parse_date(self, date_str: Optional[str]):
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            return None
    
    def _parse_datetime(self, datetime_str: Optional[str]):
        """Parse datetime string to datetime object."""
        if not datetime_str:
            return None
        try:
            return datetime.fromisoformat(datetime_str)
        except:
            return None
    
    def _get_applied_filters_summary(self, filters: Dict) -> Dict:
        """Generate summary of applied filters."""
        applied = {}
        
        for key, value in filters.items():
            if value is not None and value != "" and value != []:
                applied[key] = value
        
        return applied
    
    # ==================== QUICK SEARCHES ====================
    
    def search_by_reference(self, booking_reference: str) -> Optional[Dict]:
        """
        Quick search by booking reference.
        
        Args:
            booking_reference: Booking reference number
            
        Returns:
            Booking dictionary or None
        """
        result = self.search_bookings(
            filters={"booking_reference": booking_reference},
            page=1,
            page_size=1,
        )
        
        if result["results"]:
            return result["results"][0]
        return None
    
    def search_by_guest_email(self, email: str, limit: int = 10) -> List[Dict]:
        """
        Search bookings by guest email.
        
        Args:
            email: Guest email address
            limit: Result limit
            
        Returns:
            List of booking dictionaries
        """
        result = self.search_bookings(
            filters={"guest_email": email},
            page=1,
            page_size=limit,
        )
        
        return result["results"]
    
    def search_by_guest_phone(self, phone: str, limit: int = 10) -> List[Dict]:
        """
        Search bookings by guest phone.
        
        Args:
            phone: Guest phone number
            limit: Result limit
            
        Returns:
            List of booking dictionaries
        """
        result = self.search_bookings(
            filters={"guest_phone": phone},
            page=1,
            page_size=limit,
        )
        
        return result["results"]
    
    def search_pending_approvals(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search pending approval bookings.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Result limit
            
        Returns:
            List of pending booking dictionaries
        """
        filters = {"status": "PENDING"}
        if hostel_id:
            filters["hostel_id"] = str(hostel_id)
        
        result = self.search_bookings(
            filters=filters,
            page=1,
            page_size=limit,
            sort_by="created_at",
            sort_order="asc",
        )
        
        return result["results"]
    
    def search_upcoming_checkins(
        self,
        hostel_id: Optional[UUID] = None,
        days_ahead: int = 7,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search upcoming check-ins.
        
        Args:
            hostel_id: Optional hostel filter
            days_ahead: Days to look ahead
            limit: Result limit
            
        Returns:
            List of booking dictionaries with upcoming check-ins
        """
        from datetime import date, timedelta
        
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        
        filters = {
            "statuses": ["CONFIRMED", "APPROVED"],
            "check_in_date_from": today.isoformat(),
            "check_in_date_to": end_date.isoformat(),
        }
        
        if hostel_id:
            filters["hostel_id"] = str(hostel_id)
        
        result = self.search_bookings(
            filters=filters,
            page=1,
            page_size=limit,
            sort_by="check_in_date",
            sort_order="asc",
        )
        
        return result["results"]
    
    def search_expiring_bookings(
        self,
        hostel_id: Optional[UUID] = None,
        within_hours: int = 24,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search bookings expiring soon.
        
        Args:
            hostel_id: Optional hostel filter
            within_hours: Hours threshold
            limit: Result limit
            
        Returns:
            List of expiring booking dictionaries
        """
        filters = {"expiring_within_hours": within_hours}
        
        if hostel_id:
            filters["hostel_id"] = str(hostel_id)
        
        result = self.search_bookings(
            filters=filters,
            page=1,
            page_size=limit,
            sort_by="created_at",
            sort_order="asc",
        )
        
        return result["results"]
    
    # ==================== SEARCH SUGGESTIONS ====================
    
    def get_search_suggestions(
        self,
        query: str,
        suggestion_type: str = "all",
        limit: int = 10,
    ) -> Dict:
        """
        Get search suggestions based on query.
        
        Args:
            query: Search query string
            suggestion_type: Type of suggestions ("bookings", "guests", "all")
            limit: Number of suggestions
            
        Returns:
            Suggestions dictionary
        """
        suggestions = {"bookings": [], "guests": [], "references": []}
        
        if suggestion_type in ["all", "bookings"]:
            # Search booking references
            if query.upper().startswith("BK"):
                bookings = self.search_bookings(
                    filters={"booking_reference": query.upper()},
                    page=1,
                    page_size=limit,
                )
                suggestions["references"] = [
                    {
                        "type": "booking_reference",
                        "value": b["booking_reference"],
                        "label": f"{b['booking_reference']} - {b.get('guest_info', {}).get('guest_name', 'Unknown')}",
                    }
                    for b in bookings["results"]
                ]
        
        if suggestion_type in ["all", "guests"]:
            # Search by email
            if "@" in query:
                bookings = self.search_by_guest_email(query, limit)
                suggestions["guests"] = [
                    {
                        "type": "guest_email",
                        "value": b.get("guest_info", {}).get("guest_email"),
                        "label": f"{b.get('guest_info', {}).get('guest_name')} - {b['booking_reference']}",
                    }
                    for b in bookings
                    if b.get("guest_info")
                ]
        
        return suggestions
    
    # ==================== SAVED SEARCHES ====================
    
    def save_search(
        self,
        user_id: UUID,
        search_name: str,
        search_filters: Dict,
    ) -> Dict:
        """
        Save a search query for later use.
        
        Args:
            user_id: User UUID
            search_name: Name for the saved search
            search_filters: Search filter configuration
            
        Returns:
            Saved search dictionary
        """
        # In production, save to database
        saved_search = {
            "id": str(UUID()),
            "user_id": str(user_id),
            "name": search_name,
            "filters": search_filters,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        return saved_search
    
    def get_saved_searches(self, user_id: UUID) -> List[Dict]:
        """
        Get all saved searches for a user.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of saved search dictionaries
        """
        # In production, fetch from database
        return []
    
    def execute_saved_search(
        self,
        saved_search_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        """
        Execute a saved search.
        
        Args:
            saved_search_id: Saved search UUID
            page: Page number
            page_size: Results per page
            
        Returns:
            Search results
        """
        # In production, load saved search and execute
        return self.search_bookings({}, page, page_size)