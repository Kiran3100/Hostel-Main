"""
Inquiry Repository for comprehensive inquiry management.

This repository handles all inquiry-related database operations including
CRUD operations, advanced querying, analytics, and conversion tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func, case, cast, Integer
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.models.inquiry.inquiry import Inquiry
from app.models.inquiry.inquiry_follow_up import InquiryFollowUp
from app.models.hostel.hostel import Hostel
from app.models.user.user import User
from app.schemas.common.enums import InquirySource, InquiryStatus, RoomType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.core.exceptions import NotFoundError, ValidationException


class InquiryRepository(BaseRepository[Inquiry]):
    """
    Repository for Inquiry entity with comprehensive inquiry management capabilities.
    
    Provides specialized methods for inquiry lifecycle management, lead scoring,
    conversion tracking, and analytics.
    """
    
    def __init__(self, session: Session):
        """Initialize inquiry repository."""
        super().__init__(Inquiry, session)
    
    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================
    
    async def create_inquiry(
        self,
        hostel_id: UUID,
        visitor_name: str,
        visitor_email: str,
        visitor_phone: str,
        inquiry_data: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Inquiry:
        """
        Create new inquiry with validation and deduplication.
        
        Args:
            hostel_id: Target hostel ID
            visitor_name: Visitor's name
            visitor_email: Visitor's email
            visitor_phone: Visitor's phone
            inquiry_data: Additional inquiry data
            audit_context: Audit information
            
        Returns:
            Created inquiry entity
            
        Raises:
            ValidationException: If validation fails
        """
        # Check for duplicate inquiry (same email, hostel, within 24 hours)
        existing = await self.find_recent_duplicate(
            hostel_id=hostel_id,
            visitor_email=visitor_email,
            hours=24
        )
        
        if existing:
            raise ValidationException(
                f"Duplicate inquiry found. Visitor {visitor_email} "
                f"already submitted inquiry within last 24 hours."
            )
        
        # Create inquiry entity
        inquiry = Inquiry(
            hostel_id=hostel_id,
            visitor_name=visitor_name,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
            **inquiry_data
        )
        
        # Calculate initial priority score
        inquiry.priority_score = inquiry.calculate_priority_score()
        
        # Create with audit trail
        created_inquiry = await self.create(inquiry, audit_context)
        
        return created_inquiry
    
    async def update_inquiry_status(
        self,
        inquiry_id: UUID,
        new_status: InquiryStatus,
        updated_by: UUID,
        notes: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Inquiry:
        """
        Update inquiry status with validation and tracking.
        
        Args:
            inquiry_id: Inquiry ID
            new_status: New status
            updated_by: User making the update
            notes: Optional status change notes
            audit_context: Audit information
            
        Returns:
            Updated inquiry
            
        Raises:
            NotFoundError: If inquiry not found
            ValidationException: If status transition invalid
        """
        inquiry = await self.find_by_id(inquiry_id)
        if not inquiry:
            raise NotFoundError(f"Inquiry {inquiry_id} not found")
        
        # Validate status transition
        self._validate_status_transition(inquiry.status, new_status)
        
        # Update status
        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }
        
        # Add status-specific updates
        if new_status == InquiryStatus.CONTACTED and not inquiry.contacted_at:
            update_data["contacted_at"] = datetime.utcnow()
            update_data["contacted_by"] = updated_by
        
        if new_status == InquiryStatus.CONVERTED:
            update_data["converted_to_booking"] = True
            update_data["converted_at"] = datetime.utcnow()
            update_data["converted_by"] = updated_by
        
        if notes:
            current_notes = inquiry.notes or ""
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            update_data["notes"] = f"{current_notes}\n[{timestamp}] Status changed to {new_status.value}: {notes}"
        
        # Recalculate priority score
        inquiry.status = new_status
        update_data["priority_score"] = inquiry.calculate_priority_score()
        
        updated_inquiry = await self.update(inquiry_id, update_data, audit_context=audit_context)
        
        return updated_inquiry
    
    async def assign_inquiry(
        self,
        inquiry_id: UUID,
        assigned_to: UUID,
        assigned_by: UUID,
        notes: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Inquiry:
        """
        Assign inquiry to a user.
        
        Args:
            inquiry_id: Inquiry ID
            assigned_to: User to assign to
            assigned_by: User making assignment
            notes: Optional assignment notes
            audit_context: Audit information
            
        Returns:
            Updated inquiry
        """
        inquiry = await self.find_by_id(inquiry_id)
        if not inquiry:
            raise NotFoundError(f"Inquiry {inquiry_id} not found")
        
        update_data = {
            "assigned_to": assigned_to,
            "assigned_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        if notes:
            current_notes = inquiry.notes or ""
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            update_data["notes"] = f"{current_notes}\n[{timestamp}] Assigned by {assigned_by}: {notes}"
        
        # Auto-update status if still new
        if inquiry.status == InquiryStatus.NEW:
            update_data["status"] = InquiryStatus.ASSIGNED
        
        updated_inquiry = await self.update(inquiry_id, update_data, audit_context=audit_context)
        
        return updated_inquiry
    
    # ============================================================================
    # SPECIALIZED QUERIES
    # ============================================================================
    
    async def find_recent_duplicate(
        self,
        hostel_id: UUID,
        visitor_email: str,
        hours: int = 24
    ) -> Optional[Inquiry]:
        """
        Find recent duplicate inquiry from same visitor.
        
        Args:
            hostel_id: Hostel ID
            visitor_email: Visitor email
            hours: Time window in hours
            
        Returns:
            Duplicate inquiry if found
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.visitor_email == visitor_email)
            .where(self.model.created_at >= cutoff_time)
            .where(self.model.is_deleted == False)
            .order_by(self.model.created_at.desc())
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().first()
    
    async def find_by_status(
        self,
        hostel_id: UUID,
        status: InquiryStatus,
        include_assigned: bool = True,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find inquiries by status.
        
        Args:
            hostel_id: Hostel ID
            status: Inquiry status
            include_assigned: Whether to include assigned inquiries
            limit: Maximum results
            
        Returns:
            List of inquiries
        """
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.status == status)
            .where(self.model.is_deleted == False)
        )
        
        if not include_assigned:
            query = query.where(self.model.assigned_to.is_(None))
        
        query = (
            query
            .order_by(self.model.priority_score.desc())
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_new_inquiries(
        self,
        hostel_id: UUID,
        hours: int = 24,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find new inquiries within time window.
        
        Args:
            hostel_id: Hostel ID
            hours: Time window in hours
            limit: Maximum results
            
        Returns:
            List of new inquiries
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.status == InquiryStatus.NEW)
            .where(self.model.created_at >= cutoff_time)
            .where(self.model.is_deleted == False)
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_urgent_inquiries(
        self,
        hostel_id: UUID,
        limit: int = 50
    ) -> List[Inquiry]:
        """
        Find urgent inquiries requiring immediate attention.
        
        Args:
            hostel_id: Hostel ID
            limit: Maximum results
            
        Returns:
            List of urgent inquiries
        """
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(
                or_(
                    self.model.is_urgent == True,
                    and_(
                        self.model.status == InquiryStatus.NEW,
                        self.model.created_at >= datetime.utcnow() - timedelta(hours=24)
                    )
                )
            )
            .where(self.model.status.notin_([InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED]))
            .where(self.model.is_deleted == False)
            .order_by(self.model.priority_score.desc())
            .order_by(self.model.created_at.asc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_stale_inquiries(
        self,
        hostel_id: UUID,
        days: int = 7,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find stale inquiries without recent contact.
        
        Args:
            hostel_id: Hostel ID
            days: Days threshold for staleness
            limit: Maximum results
            
        Returns:
            List of stale inquiries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.created_at <= cutoff_date)
            .where(
                or_(
                    self.model.contacted_at.is_(None),
                    self.model.contacted_at <= cutoff_date
                )
            )
            .where(self.model.status.in_([InquiryStatus.NEW, InquiryStatus.ASSIGNED, InquiryStatus.CONTACTED]))
            .where(self.model.is_deleted == False)
            .order_by(self.model.created_at.asc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_by_assigned_user(
        self,
        assigned_to: UUID,
        status_filter: Optional[List[InquiryStatus]] = None,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find inquiries assigned to specific user.
        
        Args:
            assigned_to: User ID
            status_filter: Optional status filter
            limit: Maximum results
            
        Returns:
            List of assigned inquiries
        """
        query = (
            QueryBuilder(self.model)
            .where(self.model.assigned_to == assigned_to)
            .where(self.model.is_deleted == False)
        )
        
        if status_filter:
            query = query.where(self.model.status.in_(status_filter))
        
        query = (
            query
            .order_by(self.model.priority_score.desc())
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_needing_follow_up(
        self,
        hostel_id: UUID,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find inquiries needing follow-up.
        
        Args:
            hostel_id: Hostel ID
            limit: Maximum results
            
        Returns:
            List of inquiries needing follow-up
        """
        now = datetime.utcnow()
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.next_follow_up_due.isnot(None))
            .where(self.model.next_follow_up_due <= now)
            .where(self.model.status.notin_([InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED]))
            .where(self.model.is_deleted == False)
            .order_by(self.model.next_follow_up_due.asc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_by_source(
        self,
        hostel_id: UUID,
        source: InquirySource,
        days: int = 30,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find inquiries by source within time period.
        
        Args:
            hostel_id: Hostel ID
            source: Inquiry source
            days: Time period in days
            limit: Maximum results
            
        Returns:
            List of inquiries from source
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.inquiry_source == source)
            .where(self.model.created_at >= cutoff_date)
            .where(self.model.is_deleted == False)
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_high_priority_inquiries(
        self,
        hostel_id: UUID,
        min_priority_score: int = 70,
        limit: int = 50
    ) -> List[Inquiry]:
        """
        Find high-priority inquiries based on priority score.
        
        Args:
            hostel_id: Hostel ID
            min_priority_score: Minimum priority score
            limit: Maximum results
            
        Returns:
            List of high-priority inquiries
        """
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.priority_score >= min_priority_score)
            .where(self.model.status.notin_([InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED]))
            .where(self.model.is_deleted == False)
            .order_by(self.model.priority_score.desc())
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_unconverted_with_preferences(
        self,
        hostel_id: UUID,
        room_type: Optional[RoomType] = None,
        check_in_from: Optional[datetime] = None,
        check_in_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Find unconverted inquiries matching preferences.
        
        Args:
            hostel_id: Hostel ID
            room_type: Room type preference
            check_in_from: Check-in date range start
            check_in_to: Check-in date range end
            limit: Maximum results
            
        Returns:
            List of matching inquiries
        """
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.converted_to_booking == False)
            .where(self.model.status.notin_([InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED]))
            .where(self.model.is_deleted == False)
        )
        
        if room_type:
            query = query.where(self.model.room_type_preference == room_type)
        
        if check_in_from:
            query = query.where(self.model.preferred_check_in_date >= check_in_from)
        
        if check_in_to:
            query = query.where(self.model.preferred_check_in_date <= check_in_to)
        
        query = (
            query
            .order_by(self.model.priority_score.desc())
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def search_inquiries(
        self,
        hostel_id: UUID,
        search_term: str,
        limit: int = 50
    ) -> List[Inquiry]:
        """
        Search inquiries by visitor name, email, or phone.
        
        Args:
            hostel_id: Hostel ID
            search_term: Search term
            limit: Maximum results
            
        Returns:
            List of matching inquiries
        """
        search_pattern = f"%{search_term}%"
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(
                or_(
                    self.model.visitor_name.ilike(search_pattern),
                    self.model.visitor_email.ilike(search_pattern),
                    self.model.visitor_phone.ilike(search_pattern)
                )
            )
            .where(self.model.is_deleted == False)
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    async def get_inquiry_statistics(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive inquiry statistics.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Dictionary of statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total inquiries
        total_query = (
            QueryBuilder(self.model)
            .where(self.model.hostel_id == hostel_id)
            .where(self.model.created_at >= cutoff_date)
            .where(self.model.is_deleted == False)
            .build()
        )
        
        total_result = await self._execute_query(
            self.session.query(func.count(self.model.id)).select_from(total_query.subquery())
        )
        total_inquiries = total_result.scalar()
        
        # Status breakdown
        status_query = (
            self.session.query(
                self.model.status,
                func.count(self.model.id).label('count')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.is_deleted == False)
            .group_by(self.model.status)
        )
        
        status_result = await self._execute_query(status_query)
        status_breakdown = {row.status.value: row.count for row in status_result}
        
        # Source breakdown
        source_query = (
            self.session.query(
                self.model.inquiry_source,
                func.count(self.model.id).label('count')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.is_deleted == False)
            .group_by(self.model.inquiry_source)
        )
        
        source_result = await self._execute_query(source_query)
        source_breakdown = {row.inquiry_source.value: row.count for row in source_result}
        
        # Conversion metrics
        conversion_query = (
            self.session.query(
                func.count(self.model.id).label('total'),
                func.sum(case((self.model.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.is_deleted == False)
        )
        
        conversion_result = await self._execute_query(conversion_query)
        conversion_data = conversion_result.first()
        
        conversion_rate = 0
        if conversion_data.total > 0:
            conversion_rate = (conversion_data.converted / conversion_data.total) * 100
        
        # Average response time
        response_time_query = (
            self.session.query(
                func.avg(self.model.response_time_minutes).label('avg_response_time')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.response_time_minutes.isnot(None))
            .filter(self.model.is_deleted == False)
        )
        
        response_time_result = await self._execute_query(response_time_query)
        avg_response_time = response_time_result.scalar() or 0
        
        return {
            "period_days": days,
            "total_inquiries": total_inquiries,
            "status_breakdown": status_breakdown,
            "source_breakdown": source_breakdown,
            "conversion_rate": round(conversion_rate, 2),
            "total_converted": conversion_data.converted,
            "avg_response_time_minutes": round(avg_response_time, 2),
            "generated_at": datetime.utcnow()
        }
    
    async def get_conversion_funnel(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get conversion funnel analysis.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Conversion funnel data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        funnel_query = (
            self.session.query(
                func.count(self.model.id).label('total_inquiries'),
                func.sum(case((self.model.contacted_at.isnot(None), 1), else_=0)).label('contacted'),
                func.sum(case((self.model.status == InquiryStatus.INTERESTED, 1), else_=0)).label('interested'),
                func.sum(case((self.model.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.is_deleted == False)
        )
        
        result = await self._execute_query(funnel_query)
        data = result.first()
        
        total = data.total_inquiries or 1  # Avoid division by zero
        
        return {
            "total_inquiries": data.total_inquiries,
            "contacted": {
                "count": data.contacted,
                "rate": round((data.contacted / total) * 100, 2)
            },
            "interested": {
                "count": data.interested,
                "rate": round((data.interested / total) * 100, 2)
            },
            "converted": {
                "count": data.converted,
                "rate": round((data.converted / total) * 100, 2)
            },
            "period_days": days
        }
    
    async def get_source_performance(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics by inquiry source.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            List of source performance data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        performance_query = (
            self.session.query(
                self.model.inquiry_source,
                func.count(self.model.id).label('total'),
                func.sum(case((self.model.converted_to_booking == True, 1), else_=0)).label('converted'),
                func.avg(self.model.priority_score).label('avg_priority'),
                func.avg(self.model.response_time_minutes).label('avg_response_time')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.is_deleted == False)
            .group_by(self.model.inquiry_source)
        )
        
        result = await self._execute_query(performance_query)
        
        performance_data = []
        for row in result:
            conversion_rate = 0
            if row.total > 0:
                conversion_rate = (row.converted / row.total) * 100
            
            performance_data.append({
                "source": row.inquiry_source.value,
                "total_inquiries": row.total,
                "converted": row.converted,
                "conversion_rate": round(conversion_rate, 2),
                "avg_priority_score": round(row.avg_priority or 0, 2),
                "avg_response_time_minutes": round(row.avg_response_time or 0, 2)
            })
        
        return sorted(performance_data, key=lambda x: x['conversion_rate'], reverse=True)
    
    async def get_daily_inquiry_trend(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily inquiry trend data.
        
        Args:
            hostel_id: Hostel ID
            days: Number of days
            
        Returns:
            Daily trend data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        trend_query = (
            self.session.query(
                func.date(self.model.created_at).label('date'),
                func.count(self.model.id).label('count')
            )
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.created_at >= cutoff_date)
            .filter(self.model.is_deleted == False)
            .group_by(func.date(self.model.created_at))
            .order_by(func.date(self.model.created_at))
        )
        
        result = await self._execute_query(trend_query)
        
        return [
            {
                "date": row.date.isoformat(),
                "inquiry_count": row.count
            }
            for row in result
        ]
    
    async def get_team_performance(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get team member performance metrics.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Team performance data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        performance_query = (
            self.session.query(
                self.model.assigned_to,
                User.full_name,
                func.count(self.model.id).label('total_assigned'),
                func.sum(case((self.model.contacted_at.isnot(None), 1), else_=0)).label('contacted'),
                func.sum(case((self.model.converted_to_booking == True, 1), else_=0)).label('converted'),
                func.avg(self.model.response_time_minutes).label('avg_response_time')
            )
            .join(User, self.model.assigned_to == User.id)
            .filter(self.model.hostel_id == hostel_id)
            .filter(self.model.assigned_at >= cutoff_date)
            .filter(self.model.assigned_to.isnot(None))
            .filter(self.model.is_deleted == False)
            .group_by(self.model.assigned_to, User.full_name)
        )
        
        result = await self._execute_query(performance_query)
        
        performance_data = []
        for row in result:
            contact_rate = (row.contacted / row.total_assigned * 100) if row.total_assigned > 0 else 0
            conversion_rate = (row.converted / row.total_assigned * 100) if row.total_assigned > 0 else 0
            
            performance_data.append({
                "user_id": str(row.assigned_to),
                "user_name": row.full_name,
                "total_assigned": row.total_assigned,
                "contacted": row.contacted,
                "converted": row.converted,
                "contact_rate": round(contact_rate, 2),
                "conversion_rate": round(conversion_rate, 2),
                "avg_response_time_minutes": round(row.avg_response_time or 0, 2)
            })
        
        return sorted(performance_data, key=lambda x: x['conversion_rate'], reverse=True)
    
    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================
    
    async def bulk_update_priority_scores(
        self,
        hostel_id: UUID
    ) -> int:
        """
        Recalculate priority scores for all active inquiries.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Number of inquiries updated
        """
        inquiries = await self.find_by_criteria({
            "hostel_id": hostel_id,
            "status": [InquiryStatus.NEW, InquiryStatus.ASSIGNED, InquiryStatus.CONTACTED, InquiryStatus.INTERESTED],
            "is_deleted": False
        })
        
        count = 0
        for inquiry in inquiries:
            new_score = inquiry.calculate_priority_score()
            if new_score != inquiry.priority_score:
                await self.update(inquiry.id, {"priority_score": new_score})
                count += 1
        
        return count
    
    async def bulk_assign_inquiries(
        self,
        inquiry_ids: List[UUID],
        assigned_to: UUID,
        assigned_by: UUID,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Bulk assign multiple inquiries.
        
        Args:
            inquiry_ids: List of inquiry IDs
            assigned_to: User to assign to
            assigned_by: User making assignment
            audit_context: Audit information
            
        Returns:
            Number of inquiries assigned
        """
        count = 0
        for inquiry_id in inquiry_ids:
            try:
                await self.assign_inquiry(
                    inquiry_id=inquiry_id,
                    assigned_to=assigned_to,
                    assigned_by=assigned_by,
                    audit_context=audit_context
                )
                count += 1
            except Exception:
                continue
        
        return count
    
    async def archive_old_inquiries(
        self,
        hostel_id: UUID,
        days: int = 90
    ) -> int:
        """
        Archive old completed inquiries.
        
        Args:
            hostel_id: Hostel ID
            days: Age threshold in days
            
        Returns:
            Number of inquiries archived
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_inquiries = await self.find_by_criteria({
            "hostel_id": hostel_id,
            "status": [InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED],
            "created_at__lte": cutoff_date,
            "is_deleted": False
        })
        
        count = 0
        for inquiry in old_inquiries:
            await self.soft_delete(inquiry.id)
            count += 1
        
        return count
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _validate_status_transition(
        self,
        current_status: InquiryStatus,
        new_status: InquiryStatus
    ) -> None:
        """
        Validate status transition.
        
        Args:
            current_status: Current inquiry status
            new_status: New inquiry status
            
        Raises:
            ValidationException: If transition invalid
        """
        # Define valid transitions
        valid_transitions = {
            InquiryStatus.NEW: [
                InquiryStatus.ASSIGNED,
                InquiryStatus.CONTACTED,
                InquiryStatus.NOT_INTERESTED
            ],
            InquiryStatus.ASSIGNED: [
                InquiryStatus.CONTACTED,
                InquiryStatus.NOT_INTERESTED
            ],
            InquiryStatus.CONTACTED: [
                InquiryStatus.INTERESTED,
                InquiryStatus.NOT_INTERESTED
            ],
            InquiryStatus.INTERESTED: [
                InquiryStatus.CONVERTED,
                InquiryStatus.NOT_INTERESTED
            ],
            InquiryStatus.CONVERTED: [],
            InquiryStatus.NOT_INTERESTED: []
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            raise ValidationException(
                f"Invalid status transition from {current_status.value} to {new_status.value}"
            )
    
    async def _execute_query(self, query):
        """Execute query with error handling."""
        try:
            return self.session.execute(query)
        except Exception as e:
            self.session.rollback()
            raise