# app/repositories/booking/booking_aggregate_repository.py
"""
Booking aggregate repository for complex cross-model queries.

Provides aggregated views, complex analytics, dashboard data,
and business intelligence queries across booking-related models.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select, case
from sqlalchemy.orm import Session, joinedload

from app.models.booking.booking import Booking
from app.models.booking.booking_approval import BookingApproval
from app.models.booking.booking_assignment import BookingAssignment
from app.models.booking.booking_cancellation import BookingCancellation
from app.models.booking.booking_conversion import BookingConversion
from app.models.booking.booking_modification import BookingModification
from app.models.booking.booking_waitlist import BookingWaitlist
from app.models.base.enums import BookingStatus, WaitlistStatus
from app.repositories.base.base_repository import BaseRepository


class BookingAggregateRepository:
    """
    Aggregate repository for complex booking queries.
    
    Provides:
    - Dashboard metrics and KPIs
    - Cross-model analytics
    - Business intelligence queries
    - Funnel analysis
    - Performance metrics
    """
    
    def __init__(self, session: Session):
        """Initialize aggregate repository."""
        self.session = session
    
    # ==================== DASHBOARD METRICS ====================
    
    def get_booking_funnel_metrics(
        self,
        hostel_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get booking funnel conversion metrics.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Funnel metrics dictionary
        """
        query = select(Booking).where(
            and_(
                Booking.hostel_id == hostel_id,
                Booking.deleted_at.is_(None),
            )
        )
        
        if date_from:
            query = query.where(Booking.booking_date >= date_from)
        
        if date_to:
            query = query.where(Booking.booking_date <= date_to)
        
        bookings = self.session.execute(query).scalars().all()
        
        total_requests = len(bookings)
        pending = sum(1 for b in bookings if b.booking_status == BookingStatus.PENDING)
        approved = sum(1 for b in bookings if b.booking_status == BookingStatus.APPROVED)
        confirmed = sum(1 for b in bookings if b.booking_status == BookingStatus.CONFIRMED)
        checked_in = sum(1 for b in bookings if b.booking_status == BookingStatus.CHECKED_IN)
        completed = sum(1 for b in bookings if b.booking_status == BookingStatus.COMPLETED)
        
        rejected = sum(1 for b in bookings if b.booking_status == BookingStatus.REJECTED)
        cancelled = sum(1 for b in bookings if b.booking_status == BookingStatus.CANCELLED)
        
        return {
            "total_requests": total_requests,
            "pending": pending,
            "approved": approved,
            "confirmed": confirmed,
            "checked_in": checked_in,
            "completed": completed,
            "rejected": rejected,
            "cancelled": cancelled,
            # Conversion rates
            "approval_rate": (approved / total_requests * 100) if total_requests > 0 else 0,
            "confirmation_rate": (confirmed / approved * 100) if approved > 0 else 0,
            "checkin_rate": (checked_in / confirmed * 100) if confirmed > 0 else 0,
            "completion_rate": (completed / checked_in * 100) if checked_in > 0 else 0,
            # Drop-off rates
            "rejection_rate": (rejected / total_requests * 100) if total_requests > 0 else 0,
            "cancellation_rate": (cancelled / total_requests * 100) if total_requests > 0 else 0,
        }
    
    def get_hostel_performance_dashboard(
        self,
        hostel_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get comprehensive hostel performance dashboard data.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Dashboard data dictionary
        """
        # Booking metrics
        funnel_metrics = self.get_booking_funnel_metrics(hostel_id, date_from, date_to)
        
        # Revenue metrics
        revenue_query = select(
            func.sum(Booking.total_amount).label('total_revenue'),
            func.sum(
                case(
                    (Booking.advance_paid == True, Booking.advance_amount),
                    else_=0
                )
            ).label('advance_collected'),
            func.avg(Booking.total_amount).label('avg_booking_value'),
        ).where(
            and_(
                Booking.hostel_id == hostel_id,
                Booking.booking_status.in_([
                    BookingStatus.CONFIRMED,
                    BookingStatus.CHECKED_IN,
                    BookingStatus.COMPLETED,
                ]),
                Booking.deleted_at.is_(None),
            )
        )
        
        if date_from:
            revenue_query = revenue_query.where(Booking.booking_date >= date_from)
        
        if date_to:
            revenue_query = revenue_query.where(Booking.booking_date <= date_to)
        
        revenue_result = self.session.execute(revenue_query).first()
        
        # Conversion metrics
        conversion_count = self.session.execute(
            select(func.count(BookingConversion.id)).join(
                Booking,
                BookingConversion.booking_id == Booking.id
            ).where(
                and_(
                    Booking.hostel_id == hostel_id,
                    BookingConversion.is_successful == True,
                    BookingConversion.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        # Cancellation metrics
        cancellation_query = select(
            func.count(BookingCancellation.id).label('total_cancellations'),
            func.sum(BookingCancellation.refundable_amount).label('total_refunds'),
            func.avg(BookingCancellation.cancellation_charge_percentage).label('avg_charge_pct'),
        ).join(
            Booking,
            BookingCancellation.booking_id == Booking.id
        ).where(
            and_(
                Booking.hostel_id == hostel_id,
                BookingCancellation.deleted_at.is_(None),
            )
        )
        
        cancellation_result = self.session.execute(cancellation_query).first()
        
        # Waitlist metrics
        waitlist_query = select(
            func.count(BookingWaitlist.id).label('total_waitlist'),
            func.count(
                case(
                    (BookingWaitlist.status == WaitlistStatus.WAITING, 1),
                )
            ).label('active_waitlist'),
            func.count(
                case(
                    (BookingWaitlist.converted_to_booking == True, 1),
                )
            ).label('converted_from_waitlist'),
        ).where(
            and_(
                BookingWaitlist.hostel_id == hostel_id,
                BookingWaitlist.deleted_at.is_(None),
            )
        )
        
        waitlist_result = self.session.execute(waitlist_query).first()
        
        return {
            "funnel_metrics": funnel_metrics,
            "revenue_metrics": {
                "total_revenue": revenue_result.total_revenue or Decimal("0.00"),
                "advance_collected": revenue_result.advance_collected or Decimal("0.00"),
                "average_booking_value": revenue_result.avg_booking_value or Decimal("0.00"),
            },
            "conversion_metrics": {
                "total_conversions": conversion_count,
                "conversion_rate": (
                    conversion_count / funnel_metrics["confirmed"] * 100
                    if funnel_metrics["confirmed"] > 0 else 0
                ),
            },
            "cancellation_metrics": {
                "total_cancellations": cancellation_result.total_cancellations or 0,
                "total_refunds": cancellation_result.total_refunds or Decimal("0.00"),
                "average_charge_percentage": cancellation_result.avg_charge_pct or Decimal("0.00"),
            },
            "waitlist_metrics": {
                "total_entries": waitlist_result.total_waitlist or 0,
                "active_entries": waitlist_result.active_waitlist or 0,
                "converted_entries": waitlist_result.converted_from_waitlist or 0,
                "conversion_rate": (
                    waitlist_result.converted_from_waitlist / waitlist_result.total_waitlist * 100
                    if waitlist_result.total_waitlist > 0 else 0
                ),
            },
        }
    
    def get_time_series_bookings(
        self,
        hostel_id: UUID,
        date_from: datetime,
        date_to: datetime,
        granularity: str = 'day',
    ) -> List[Dict]:
        """
        Get time series booking data.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Start date
            date_to: End date
            granularity: 'day', 'week', or 'month'
            
        Returns:
            List of time series data points
        """
        # This would typically use date_trunc function for PostgreSQL
        # Simplified implementation
        query = select(
            func.date(Booking.booking_date).label('date'),
            func.count(Booking.id).label('count'),
            func.sum(Booking.total_amount).label('revenue'),
        ).where(
            and_(
                Booking.hostel_id == hostel_id,
                Booking.booking_date >= date_from,
                Booking.booking_date <= date_to,
                Booking.deleted_at.is_(None),
            )
        ).group_by(
            func.date(Booking.booking_date)
        ).order_by(
            func.date(Booking.booking_date)
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "date": str(row.date),
                "bookings": row.count,
                "revenue": row.revenue or Decimal("0.00"),
            }
            for row in results
        ]
    
    def get_pending_actions_summary(
        self,
        hostel_id: UUID,
    ) -> Dict[str, any]:
        """
        Get summary of pending actions requiring attention.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Pending actions summary
        """
        # Pending approvals
        pending_approvals = self.session.execute(
            select(func.count(Booking.id)).where(
                and_(
                    Booking.hostel_id == hostel_id,
                    Booking.booking_status == BookingStatus.PENDING,
                    Booking.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        # Expiring bookings
        expiring_bookings = self.session.execute(
            select(func.count(Booking.id)).where(
                and_(
                    Booking.hostel_id == hostel_id,
                    Booking.booking_status == BookingStatus.PENDING,
                    Booking.expires_at.isnot(None),
                    Booking.expires_at <= datetime.utcnow() + timedelta(hours=24),
                    Booking.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        # Pending payments
        pending_payments = self.session.execute(
            select(func.count(BookingApproval.id)).join(
                Booking,
                BookingApproval.booking_id == Booking.id
            ).where(
                and_(
                    Booking.hostel_id == hostel_id,
                    BookingApproval.advance_payment_required == True,
                    Booking.advance_paid == False,
                    Booking.booking_status == BookingStatus.APPROVED,
                    BookingApproval.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        # Pending modifications
        pending_modifications = self.session.execute(
            select(func.count(BookingModification.id)).join(
                Booking,
                BookingModification.booking_id == Booking.id
            ).where(
                and_(
                    Booking.hostel_id == hostel_id,
                    BookingModification.modification_status == 'pending',
                    BookingModification.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        # Pending conversions
        pending_conversions = self.session.execute(
            select(func.count(BookingConversion.id)).join(
                Booking,
                BookingConversion.booking_id == Booking.id
            ).where(
                and_(
                    Booking.hostel_id == hostel_id,
                    BookingConversion.is_successful == True,
                    BookingConversion.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        # Active waitlist
        active_waitlist = self.session.execute(
            select(func.count(BookingWaitlist.id)).where(
                and_(
                    BookingWaitlist.hostel_id == hostel_id,
                    BookingWaitlist.status == WaitlistStatus.WAITING,
                    BookingWaitlist.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        return {
            "pending_approvals": pending_approvals,
            "expiring_bookings": expiring_bookings,
            "pending_payments": pending_payments,
            "pending_modifications": pending_modifications,
            "pending_conversions": pending_conversions,
            "active_waitlist": active_waitlist,
            "total_pending_actions": (
                pending_approvals +
                expiring_bookings +
                pending_payments +
                pending_modifications
            ),
        }


