"""
Inquiry Follow-up Repository for tracking communication and interactions.

This repository manages all follow-up related operations including
communication tracking, outcome analysis, and engagement metrics.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session

from app.models.inquiry.inquiry_follow_up import (
    InquiryFollowUp,
    ContactMethod,
    ContactOutcome
)
from app.models.inquiry.inquiry import Inquiry
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.core.exceptions import NotFoundException, ValidationException


class InquiryFollowUpRepository(BaseRepository[InquiryFollowUp]):
    """
    Repository for InquiryFollowUp entity with comprehensive follow-up tracking.
    
    Provides methods for communication tracking, outcome analysis,
    and engagement optimization.
    """
    
    def __init__(self, session: Session):
        """Initialize follow-up repository."""
        super().__init__(InquiryFollowUp, session)
    
    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================
    
    async def create_follow_up(
        self,
        inquiry_id: UUID,
        followed_up_by: UUID,
        contact_method: ContactMethod,
        contact_outcome: ContactOutcome,
        notes: str,
        follow_up_data: Optional[Dict[str, Any]] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> InquiryFollowUp:
        """
        Create new follow-up record.
        
        Args:
            inquiry_id: Inquiry ID
            followed_up_by: User ID
            contact_method: Contact method used
            contact_outcome: Outcome of contact
            notes: Follow-up notes
            follow_up_data: Additional follow-up data
            audit_context: Audit information
            
        Returns:
            Created follow-up entity
        """
        # Get inquiry to determine attempt number
        inquiry = await self._get_inquiry(inquiry_id)
        
        # Calculate attempt number
        attempt_number = inquiry.follow_up_count + 1
        
        # Determine if successful
        is_successful = contact_outcome in [
            ContactOutcome.CONNECTED,
            ContactOutcome.INTERESTED,
            ContactOutcome.CALLBACK_REQUESTED
        ]
        
        # Create follow-up
        follow_up_dict = {
            "inquiry_id": inquiry_id,
            "followed_up_by": followed_up_by,
            "contact_method": contact_method,
            "contact_outcome": contact_outcome,
            "notes": notes,
            "attempt_number": attempt_number,
            "is_successful": is_successful,
            "attempted_at": datetime.utcnow()
        }
        
        if follow_up_data:
            follow_up_dict.update(follow_up_data)
        
        follow_up = InquiryFollowUp(**follow_up_dict)
        
        created_follow_up = await self.create(follow_up, audit_context)
        
        # Update inquiry follow-up tracking
        await self._update_inquiry_follow_up_tracking(inquiry_id, created_follow_up)
        
        return created_follow_up
    
    async def record_email_engagement(
        self,
        follow_up_id: UUID,
        opened: bool = False,
        clicked: bool = False,
        response_received: bool = False
    ) -> InquiryFollowUp:
        """
        Record email engagement metrics.
        
        Args:
            follow_up_id: Follow-up ID
            opened: Whether email was opened
            clicked: Whether links were clicked
            response_received: Whether response was received
            
        Returns:
            Updated follow-up
        """
        update_data = {}
        
        if opened:
            update_data["email_opened"] = True
        
        if clicked:
            update_data["email_clicked"] = True
        
        if response_received:
            update_data["response_received"] = True
            
            # Calculate response time if not already set
            follow_up = await self.find_by_id(follow_up_id)
            if follow_up and not follow_up.response_time_hours:
                response_time = (datetime.utcnow() - follow_up.attempted_at).total_seconds() / 3600
                update_data["response_time_hours"] = int(response_time)
        
        return await self.update(follow_up_id, update_data)
    
    # ============================================================================
    # SPECIALIZED QUERIES
    # ============================================================================
    
    async def find_by_inquiry(
        self,
        inquiry_id: UUID,
        limit: int = 100
    ) -> List[InquiryFollowUp]:
        """
        Find all follow-ups for an inquiry.
        
        Args:
            inquiry_id: Inquiry ID
            limit: Maximum results
            
        Returns:
            List of follow-ups
        """
        query = (
            QueryBuilder(self.model)
            .where(self.model.inquiry_id == inquiry_id)
            .order_by(self.model.attempted_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_by_user(
        self,
        user_id: UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[InquiryFollowUp]:
        """
        Find follow-ups by user within time period.
        
        Args:
            user_id: User ID
            days: Time period in days
            limit: Maximum results
            
        Returns:
            List of follow-ups
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            QueryBuilder(self.model)
            .where(self.model.followed_up_by == user_id)
            .where(self.model.attempted_at >= cutoff_date)
            .order_by(self.model.attempted_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_recent_follow_ups(
        self,
        hostel_id: UUID,
        hours: int = 24,
        limit: int = 100
    ) -> List[InquiryFollowUp]:
        """
        Find recent follow-ups for a hostel.
        
        Args:
            hostel_id: Hostel ID
            hours: Time window in hours
            limit: Maximum results
            
        Returns:
            List of recent follow-ups
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = (
            QueryBuilder(self.model)
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .where(Inquiry.hostel_id == hostel_id)
            .where(self.model.attempted_at >= cutoff_time)
            .order_by(self.model.attempted_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_by_outcome(
        self,
        hostel_id: UUID,
        outcome: ContactOutcome,
        days: int = 30,
        limit: int = 100
    ) -> List[InquiryFollowUp]:
        """
        Find follow-ups by outcome.
        
        Args:
            hostel_id: Hostel ID
            outcome: Contact outcome
            days: Time period in days
            limit: Maximum results
            
        Returns:
            List of follow-ups
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            QueryBuilder(self.model)
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .where(Inquiry.hostel_id == hostel_id)
            .where(self.model.contact_outcome == outcome)
            .where(self.model.attempted_at >= cutoff_date)
            .order_by(self.model.attempted_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_successful_follow_ups(
        self,
        hostel_id: UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[InquiryFollowUp]:
        """
        Find successful follow-ups.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            limit: Maximum results
            
        Returns:
            List of successful follow-ups
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            QueryBuilder(self.model)
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .where(Inquiry.hostel_id == hostel_id)
            .where(self.model.is_successful == True)
            .where(self.model.attempted_at >= cutoff_date)
            .order_by(self.model.attempted_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    async def find_automated_follow_ups(
        self,
        hostel_id: UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[InquiryFollowUp]:
        """
        Find automated follow-ups.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            limit: Maximum results
            
        Returns:
            List of automated follow-ups
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            QueryBuilder(self.model)
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .where(Inquiry.hostel_id == hostel_id)
            .where(self.model.is_automated == True)
            .where(self.model.attempted_at >= cutoff_date)
            .order_by(self.model.attempted_at.desc())
            .limit(limit)
            .build()
        )
        
        result = await self._execute_query(query)
        return result.scalars().all()
    
    # ============================================================================
    # ANALYTICS
    # ============================================================================
    
    async def get_follow_up_statistics(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive follow-up statistics.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Dictionary of statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total follow-ups
        total_query = (
            self.session.query(func.count(self.model.id))
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
        )
        
        total_result = await self._execute_query(total_query)
        total_follow_ups = total_result.scalar()
        
        # Success rate
        success_query = (
            self.session.query(
                func.count(self.model.id).label('total'),
                func.sum(case((self.model.is_successful == True, 1), else_=0)).label('successful')
            )
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
        )
        
        success_result = await self._execute_query(success_query)
        success_data = success_result.first()
        
        success_rate = 0
        if success_data.total > 0:
            success_rate = (success_data.successful / success_data.total) * 100
        
        # Method breakdown
        method_query = (
            self.session.query(
                self.model.contact_method,
                func.count(self.model.id).label('count')
            )
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
            .group_by(self.model.contact_method)
        )
        
        method_result = await self._execute_query(method_query)
        method_breakdown = {row.contact_method.value: row.count for row in method_result}
        
        # Outcome breakdown
        outcome_query = (
            self.session.query(
                self.model.contact_outcome,
                func.count(self.model.id).label('count')
            )
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
            .group_by(self.model.contact_outcome)
        )
        
        outcome_result = await self._execute_query(outcome_query)
        outcome_breakdown = {row.contact_outcome.value: row.count for row in outcome_result}
        
        # Average response time
        response_query = (
            self.session.query(
                func.avg(self.model.response_time_hours).label('avg_response_time')
            )
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
            .filter(self.model.response_time_hours.isnot(None))
        )
        
        response_result = await self._execute_query(response_query)
        avg_response_time = response_result.scalar() or 0
        
        return {
            "period_days": days,
            "total_follow_ups": total_follow_ups,
            "success_rate": round(success_rate, 2),
            "total_successful": success_data.successful,
            "method_breakdown": method_breakdown,
            "outcome_breakdown": outcome_breakdown,
            "avg_response_time_hours": round(avg_response_time, 2),
            "generated_at": datetime.utcnow()
        }
    
    async def get_method_performance(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics by contact method.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            List of method performance data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        performance_query = (
            self.session.query(
                self.model.contact_method,
                func.count(self.model.id).label('total'),
                func.sum(case((self.model.is_successful == True, 1), else_=0)).label('successful'),
                func.avg(self.model.response_time_hours).label('avg_response_time'),
                func.avg(self.model.duration_minutes).label('avg_duration')
            )
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
            .group_by(self.model.contact_method)
        )
        
        result = await self._execute_query(performance_query)
        
        performance_data = []
        for row in result:
            success_rate = 0
            if row.total > 0:
                success_rate = (row.successful / row.total) * 100
            
            performance_data.append({
                "method": row.contact_method.value,
                "total_attempts": row.total,
                "successful": row.successful,
                "success_rate": round(success_rate, 2),
                "avg_response_time_hours": round(row.avg_response_time or 0, 2),
                "avg_duration_minutes": round(row.avg_duration or 0, 2)
            })
        
        return sorted(performance_data, key=lambda x: x['success_rate'], reverse=True)
    
    async def get_user_performance(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get team member follow-up performance.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            List of user performance data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        from app.models.user.user import User
        
        performance_query = (
            self.session.query(
                self.model.followed_up_by,
                User.full_name,
                func.count(self.model.id).label('total'),
                func.sum(case((self.model.is_successful == True, 1), else_=0)).label('successful'),
                func.avg(self.model.response_time_hours).label('avg_response_time')
            )
            .join(User, self.model.followed_up_by == User.id)
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.attempted_at >= cutoff_date)
            .group_by(self.model.followed_up_by, User.full_name)
        )
        
        result = await self._execute_query(performance_query)
        
        performance_data = []
        for row in result:
            success_rate = (row.successful / row.total * 100) if row.total > 0 else 0
            
            performance_data.append({
                "user_id": str(row.followed_up_by),
                "user_name": row.full_name,
                "total_follow_ups": row.total,
                "successful": row.successful,
                "success_rate": round(success_rate, 2),
                "avg_response_time_hours": round(row.avg_response_time or 0, 2)
            })
        
        return sorted(performance_data, key=lambda x: x['success_rate'], reverse=True)
    
    async def get_email_engagement_metrics(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get email engagement metrics.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Email engagement data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        email_query = (
            self.session.query(
                func.count(self.model.id).label('total_emails'),
                func.sum(case((self.model.email_opened == True, 1), else_=0)).label('opened'),
                func.sum(case((self.model.email_clicked == True, 1), else_=0)).label('clicked'),
                func.sum(case((self.model.response_received == True, 1), else_=0)).label('responded')
            )
            .join(Inquiry, self.model.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(self.model.contact_method == ContactMethod.EMAIL)
            .filter(self.model.attempted_at >= cutoff_date)
        )
        
        result = await self._execute_query(email_query)
        data = result.first()
        
        total = data.total_emails or 1
        
        return {
            "total_emails": data.total_emails,
            "open_rate": round((data.opened / total) * 100, 2),
            "click_rate": round((data.clicked / total) * 100, 2),
            "response_rate": round((data.responded / total) * 100, 2),
            "period_days": days
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    async def _get_inquiry(self, inquiry_id: UUID) -> Inquiry:
        """Get inquiry by ID."""
        inquiry = self.session.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
        if not inquiry:
            raise NotFoundException(f"Inquiry {inquiry_id} not found")
        return inquiry
    
    async def _update_inquiry_follow_up_tracking(
        self,
        inquiry_id: UUID,
        follow_up: InquiryFollowUp
    ) -> None:
        """Update inquiry follow-up tracking fields."""
        inquiry = await self._get_inquiry(inquiry_id)
        
        # Update follow-up count
        inquiry.follow_up_count += 1
        inquiry.last_follow_up_at = follow_up.attempted_at
        
        # Update response time if first contact
        if inquiry.response_time_minutes is None and follow_up.is_successful:
            response_time = (follow_up.attempted_at - inquiry.created_at).total_seconds() / 60
            inquiry.response_time_minutes = int(response_time)
        
        self.session.commit()
    
    async def _execute_query(self, query):
        """Execute query with error handling."""
        try:
            return self.session.execute(query)
        except Exception as e:
            self.session.rollback()
            raise