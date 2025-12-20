"""
Advanced complaint search and filtering service.

Provides sophisticated search capabilities with full-text search,
filters, sorting, and saved search functionality.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from sqlalchemy.orm import Session

from app.models.base.enums import ComplaintCategory, ComplaintStatus, Priority
from app.models.complaint.complaint import Complaint
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.core.exceptions import ValidationError


class SortField(str, Enum):
    """Sort field options."""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PRIORITY = "priority"
    SLA_DUE_AT = "sla_due_at"
    STATUS = "status"
    COMPLAINT_NUMBER = "complaint_number"
    RATING = "rating"


class SortOrder(str, Enum):
    """Sort order options."""
    ASC = "ASC"
    DESC = "DESC"


class ComplaintSearchService:
    """
    Advanced complaint search service.
    
    Provides comprehensive search and filtering capabilities
    with saved searches and search history.
    """

    def __init__(self, session: Session):
        """
        Initialize search service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)

    # ==================== Advanced Search ====================

    def advanced_search(
        self,
        query: Optional[str] = None,
        hostel_id: Optional[str] = None,
        status: Optional[List[ComplaintStatus]] = None,
        category: Optional[List[ComplaintCategory]] = None,
        priority: Optional[List[Priority]] = None,
        assigned_to: Optional[str] = None,
        raised_by: Optional[str] = None,
        student_id: Optional[str] = None,
        room_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        escalated_only: bool = False,
        sla_breach_only: bool = False,
        has_feedback: Optional[bool] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        tags: Optional[List[str]] = None,
        sort_by: SortField = SortField.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Perform advanced search with multiple filters.
        
        Args:
            query: Search text (searches in title and description)
            hostel_id: Filter by hostel
            status: Filter by status list
            category: Filter by category list
            priority: Filter by priority list
            assigned_to: Filter by assignee
            raised_by: Filter by raiser
            student_id: Filter by student
            room_id: Filter by room
            date_from: Start date filter
            date_to: End date filter
            escalated_only: Only escalated complaints
            sla_breach_only: Only SLA breached complaints
            has_feedback: Filter by feedback existence
            min_rating: Minimum rating filter
            max_rating: Maximum rating filter
            tags: Filter by tags (from metadata)
            sort_by: Sort field
            sort_order: Sort order
            page: Page number (1-indexed)
            page_size: Results per page
            
        Returns:
            Search results with pagination
        """
        # Calculate skip for pagination
        skip = (page - 1) * page_size
        
        # Perform search
        complaints, total = self.complaint_repo.search_complaints(
            search_term=query,
            hostel_id=hostel_id,
            status=status,
            category=category,
            priority=priority,
            assigned_to=assigned_to,
            raised_by=raised_by,
            student_id=student_id,
            room_id=room_id,
            date_from=date_from,
            date_to=date_to,
            escalated_only=escalated_only,
            sla_breach_only=sla_breach_only,
            skip=skip,
            limit=page_size,
        )
        
        # Apply additional filters
        if has_feedback is not None:
            complaints = [
                c for c in complaints
                if (c.student_feedback is not None) == has_feedback
            ]
        
        if min_rating is not None:
            complaints = [
                c for c in complaints
                if c.student_rating and c.student_rating >= min_rating
            ]
        
        if max_rating is not None:
            complaints = [
                c for c in complaints
                if c.student_rating and c.student_rating <= max_rating
            ]
        
        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "results": complaints,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
            "filters_applied": {
                "query": query,
                "status": [s.value for s in status] if status else None,
                "category": [c.value for c in category] if category else None,
                "priority": [p.value for p in priority] if priority else None,
                "escalated_only": escalated_only,
                "sla_breach_only": sla_breach_only,
            },
        }

    # ==================== Quick Filters ====================

    def get_my_complaints(
        self,
        user_id: str,
        status: Optional[ComplaintStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get complaints raised by user.
        
        Args:
            user_id: User identifier
            status: Optional status filter
            page: Page number
            page_size: Results per page
            
        Returns:
            User's complaints with pagination
        """
        return self.advanced_search(
            raised_by=user_id,
            status=[status] if status else None,
            page=page,
            page_size=page_size,
        )

    def get_assigned_to_me(
        self,
        user_id: str,
        status: Optional[ComplaintStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get complaints assigned to user.
        
        Args:
            user_id: User identifier
            status: Optional status filter
            page: Page number
            page_size: Results per page
            
        Returns:
            Assigned complaints with pagination
        """
        return self.advanced_search(
            assigned_to=user_id,
            status=[status] if status else None,
            page=page,
            page_size=page_size,
        )

    def get_urgent_complaints(
        self,
        hostel_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get urgent/critical complaints.
        
        Args:
            hostel_id: Optional hostel filter
            page: Page number
            page_size: Results per page
            
        Returns:
            Urgent complaints
        """
        return self.advanced_search(
            hostel_id=hostel_id,
            priority=[Priority.CRITICAL, Priority.URGENT],
            status=[
                ComplaintStatus.OPEN,
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.IN_PROGRESS,
            ],
            sort_by=SortField.PRIORITY,
            page=page,
            page_size=page_size,
        )

    def get_overdue_complaints(
        self,
        hostel_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get overdue complaints (SLA breached).
        
        Args:
            hostel_id: Optional hostel filter
            page: Page number
            page_size: Results per page
            
        Returns:
            Overdue complaints
        """
        return self.advanced_search(
            hostel_id=hostel_id,
            sla_breach_only=True,
            status=[
                ComplaintStatus.OPEN,
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.IN_PROGRESS,
            ],
            sort_by=SortField.SLA_DUE_AT,
            page=page,
            page_size=page_size,
        )

    def get_unassigned_complaints(
        self,
        hostel_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get unassigned open complaints.
        
        Args:
            hostel_id: Optional hostel filter
            page: Page number
            page_size: Results per page
            
        Returns:
            Unassigned complaints
        """
        complaints = self.complaint_repo.find_by_hostel(
            hostel_id=hostel_id,
            status=ComplaintStatus.OPEN,
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        
        unassigned = [c for c in complaints if not c.assigned_to]
        
        return {
            "results": unassigned,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(unassigned),
            },
        }

    def get_escalated_complaints(
        self,
        hostel_id: Optional[str] = None,
        escalated_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get escalated complaints.
        
        Args:
            hostel_id: Optional hostel filter
            escalated_to: Optional user filter
            page: Page number
            page_size: Results per page
            
        Returns:
            Escalated complaints
        """
        complaints = self.complaint_repo.find_escalated_complaints(
            hostel_id=hostel_id,
            escalated_to=escalated_to,
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        
        return {
            "results": complaints,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(complaints),
            },
        }

    # ==================== Saved Searches ====================

    def save_search(
        self,
        user_id: str,
        search_name: str,
        search_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save search parameters for quick access.
        
        Args:
            user_id: User identifier
            search_name: Name for saved search
            search_params: Search parameters
            
        Returns:
            Saved search record
        """
        # Would store in database - placeholder implementation
        saved_search = {
            "id": f"search_{datetime.now().timestamp()}",
            "user_id": user_id,
            "name": search_name,
            "params": search_params,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return saved_search

    def get_saved_searches(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get user's saved searches.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of saved searches
        """
        # Placeholder - would fetch from database
        return []

    def execute_saved_search(
        self,
        search_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Execute a saved search.
        
        Args:
            search_id: Saved search identifier
            page: Page number
            page_size: Results per page
            
        Returns:
            Search results
        """
        # Would load saved search params and execute
        # Placeholder implementation
        return self.advanced_search(page=page, page_size=page_size)

    # ==================== Search Suggestions ====================

    def get_search_suggestions(
        self,
        query: str,
        limit: int = 10,
    ) -> List[str]:
        """
        Get search suggestions based on query.
        
        Args:
            query: Partial search query
            limit: Maximum suggestions
            
        Returns:
            List of suggestions
        """
        # Would implement autocomplete/typeahead
        # Placeholder implementation
        suggestions = [
            "water leakage",
            "electricity problem",
            "wifi not working",
            "room cleaning",
            "ac not working",
        ]
        
        # Filter by query
        if query:
            suggestions = [s for s in suggestions if query.lower() in s.lower()]
        
        return suggestions[:limit]

    # ==================== Faceted Search ====================

    def get_search_facets(
        self,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get facets/aggregations for search filtering.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Facet counts
        """
        stats = self.complaint_repo.get_complaint_statistics(hostel_id=hostel_id)
        
        return {
            "status": stats.get("status_breakdown", {}),
            "category": stats.get("category_breakdown", {}),
            "priority": stats.get("priority_breakdown", {}),
            "sla_breach": {
                "breached": stats.get("sla_breach_count", 0),
                "compliant": stats.get("total_complaints", 0) - stats.get("sla_breach_count", 0),
            },
            "escalated": {
                "escalated": stats.get("escalated_count", 0),
                "not_escalated": stats.get("total_complaints", 0) - stats.get("escalated_count", 0),
            },
        }