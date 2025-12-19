"""
Specification pattern for encapsulating business rules and query logic.

Provides reusable, composable, and testable query conditions
for complex business rules.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, Type, TypeVar
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy import and_, or_, not_, func
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import ClauseElement

from app.models.base import BaseModel
from app.models.base.enums import (
    BookingStatus,
    PaymentStatus,
    ComplaintStatus,
    ComplaintPriority,
    MaintenanceStatus,
    RoomStatus,
    BedStatus,
    LeaveStatus,
    AttendanceStatus,
)

ModelType = TypeVar("ModelType", bound=BaseModel)


class Specification(ABC, Generic[ModelType]):
    """
    Abstract specification for query conditions.
    
    Implements the Specification pattern for building
    reusable and composable query logic.
    """
    
    @abstractmethod
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        """
        Convert specification to SQLAlchemy expression.
        
        Args:
            model: Model class
            
        Returns:
            SQLAlchemy clause element
        """
        pass
    
    def apply(self, query: Query) -> Query:
        """
        Apply specification to query.
        
        Args:
            query: SQLAlchemy query
            
        Returns:
            Modified query
        """
        return query.filter(self.to_expression(query.column_descriptions[0]['type']))
    
    def __and__(self, other: "Specification[ModelType]") -> "AndSpecification[ModelType]":
        """Combine specifications with AND."""
        return AndSpecification(self, other)
    
    def __or__(self, other: "Specification[ModelType]") -> "OrSpecification[ModelType]":
        """Combine specifications with OR."""
        return OrSpecification(self, other)
    
    def __invert__(self) -> "NotSpecification[ModelType]":
        """Negate specification."""
        return NotSpecification(self)


class AndSpecification(Specification[ModelType]):
    """AND combination of specifications."""
    
    def __init__(self, *specs: Specification[ModelType]):
        self.specs = specs
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(*[spec.to_expression(model) for spec in self.specs])


class OrSpecification(Specification[ModelType]):
    """OR combination of specifications."""
    
    def __init__(self, *specs: Specification[ModelType]):
        self.specs = specs
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return or_(*[spec.to_expression(model) for spec in self.specs])


class NotSpecification(Specification[ModelType]):
    """NOT negation of specification."""
    
    def __init__(self, spec: Specification[ModelType]):
        self.spec = spec
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return not_(self.spec.to_expression(model))


# ==================== Generic Specifications ====================


class FieldEqualsSpecification(Specification[ModelType]):
    """Specification for field equality."""
    
    def __init__(self, field_name: str, value: Any):
        self.field_name = field_name
        self.value = value
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return getattr(model, self.field_name) == self.value


class FieldInSpecification(Specification[ModelType]):
    """Specification for field IN list."""
    
    def __init__(self, field_name: str, values: List[Any]):
        self.field_name = field_name
        self.values = values
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return getattr(model, self.field_name).in_(self.values)


class FieldBetweenSpecification(Specification[ModelType]):
    """Specification for field BETWEEN values."""
    
    def __init__(self, field_name: str, start: Any, end: Any):
        self.field_name = field_name
        self.start = start
        self.end = end
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        field = getattr(model, self.field_name)
        return and_(field >= self.start, field <= self.end)


class FieldLikeSpecification(Specification[ModelType]):
    """Specification for field LIKE pattern."""
    
    def __init__(self, field_name: str, pattern: str, case_sensitive: bool = False):
        self.field_name = field_name
        self.pattern = pattern
        self.case_sensitive = case_sensitive
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        field = getattr(model, self.field_name)
        if self.case_sensitive:
            return field.like(self.pattern)
        return field.ilike(self.pattern)


class DateRangeSpecification(Specification[ModelType]):
    """Specification for date range filtering."""
    
    def __init__(
        self,
        field_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ):
        self.field_name = field_name
        self.start_date = start_date
        self.end_date = end_date
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        field = getattr(model, self.field_name)
        conditions = []
        
        if self.start_date:
            conditions.append(func.date(field) >= self.start_date)
        if self.end_date:
            conditions.append(func.date(field) <= self.end_date)
        
        return and_(*conditions) if conditions else True


# ==================== Student Specifications ====================


class ActiveStudentsSpecification(Specification):
    """Students with active status and valid enrollment."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        from app.models.student import Student
        
        return and_(
            model.status == "active",
            model.is_deleted == False,
            model.enrollment_date <= datetime.utcnow(),
            or_(
                model.expected_checkout_date.is_(None),
                model.expected_checkout_date > datetime.utcnow()
            )
        )


class StudentsEnrolledInPeriodSpecification(Specification):
    """Students enrolled within a specific period."""
    
    def __init__(self, start_date: date, end_date: date):
        self.start_date = start_date
        self.end_date = end_date
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            func.date(model.enrollment_date) >= self.start_date,
            func.date(model.enrollment_date) <= self.end_date
        )


class StudentsWithOverdueDocumentsSpecification(Specification):
    """Students with documents approaching expiration."""
    
    def __init__(self, days_before: int = 30):
        self.threshold_date = datetime.utcnow() + timedelta(days=days_before)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        # This would typically join with documents table
        return model.id.in_(
            # Subquery for students with expiring documents
            # Implementation depends on document model structure
        )


# ==================== Booking Specifications ====================


class PendingBookingsSpecification(Specification):
    """Bookings pending confirmation."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == BookingStatus.PENDING,
            model.is_deleted == False
        )


class ConfirmedBookingsSpecification(Specification):
    """Confirmed bookings."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == BookingStatus.CONFIRMED,
            model.is_deleted == False
        )


class BookingsForDateRangeSpecification(Specification):
    """Bookings within a date range."""
    
    def __init__(self, start_date: date, end_date: date):
        self.start_date = start_date
        self.end_date = end_date
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            or_(
                and_(
                    model.check_in_date >= self.start_date,
                    model.check_in_date <= self.end_date
                ),
                and_(
                    model.check_out_date >= self.start_date,
                    model.check_out_date <= self.end_date
                ),
                and_(
                    model.check_in_date <= self.start_date,
                    model.check_out_date >= self.end_date
                )
            ),
            model.is_deleted == False
        )


class ExpiredBookingsSpecification(Specification):
    """Bookings that have expired without confirmation."""
    
    def __init__(self, expiry_hours: int = 24):
        self.expiry_threshold = datetime.utcnow() - timedelta(hours=expiry_hours)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == BookingStatus.PENDING,
            model.created_at < self.expiry_threshold,
            model.is_deleted == False
        )


# ==================== Room & Bed Specifications ====================


class AvailableRoomsSpecification(Specification):
    """Rooms available for booking in date range."""
    
    def __init__(
        self,
        start_date: date,
        end_date: date,
        hostel_id: Optional[Any] = None,
        room_type: Optional[str] = None
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.hostel_id = hostel_id
        self.room_type = room_type
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        conditions = [
            model.status == RoomStatus.AVAILABLE,
            model.is_deleted == False,
            model.available_beds > 0
        ]
        
        if self.hostel_id:
            conditions.append(model.hostel_id == self.hostel_id)
        
        if self.room_type:
            conditions.append(model.room_type == self.room_type)
        
        # Check for no conflicting bookings
        # This would typically involve a subquery
        
        return and_(*conditions)


class AvailableBedsSpecification(Specification):
    """Beds available for assignment."""
    
    def __init__(self, room_id: Optional[Any] = None):
        self.room_id = room_id
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        conditions = [
            model.status == BedStatus.AVAILABLE,
            model.is_deleted == False
        ]
        
        if self.room_id:
            conditions.append(model.room_id == self.room_id)
        
        return and_(*conditions)


class RoomsRequiringMaintenanceSpecification(Specification):
    """Rooms requiring maintenance based on last maintenance date."""
    
    def __init__(self, days_since_maintenance: int = 90):
        self.threshold_date = datetime.utcnow() - timedelta(days=days_since_maintenance)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return or_(
            model.last_maintenance_date.is_(None),
            model.last_maintenance_date < self.threshold_date
        )


# ==================== Payment Specifications ====================


class OverduePaymentsSpecification(Specification):
    """Payments past due date with grace period."""
    
    def __init__(self, grace_period_days: int = 0):
        self.due_date_threshold = datetime.utcnow().date() - timedelta(days=grace_period_days)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status.in_([PaymentStatus.PENDING, PaymentStatus.FAILED]),
            func.date(model.due_date) < self.due_date_threshold,
            model.is_deleted == False
        )


class PendingPaymentsSpecification(Specification):
    """Payments pending processing."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == PaymentStatus.PENDING,
            model.is_deleted == False
        )


class PaymentsInDateRangeSpecification(Specification):
    """Payments within date range."""
    
    def __init__(self, start_date: date, end_date: date):
        self.start_date = start_date
        self.end_date = end_date
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            func.date(model.payment_date) >= self.start_date,
            func.date(model.payment_date) <= self.end_date,
            model.is_deleted == False
        )


class FailedPaymentsSpecification(Specification):
    """Failed payments requiring retry."""
    
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == PaymentStatus.FAILED,
            model.retry_count < self.max_attempts,
            model.is_deleted == False
        )


# ==================== Complaint Specifications ====================


class OpenComplaintsSpecification(Specification):
    """Open complaints requiring attention."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status.in_([ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS]),
            model.is_deleted == False
        )


class HighPriorityComplaintsSpecification(Specification):
    """High priority and urgent complaints."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.priority.in_([ComplaintPriority.HIGH, ComplaintPriority.URGENT]),
            model.status != ComplaintStatus.CLOSED,
            model.is_deleted == False
        )


class EscalatedComplaintsSpecification(Specification):
    """Escalated complaints."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == ComplaintStatus.ESCALATED,
            model.is_deleted == False
        )


class OverdueComplaintsSpecification(Specification):
    """Complaints past SLA deadline."""
    
    def __init__(self, sla_hours: int = 48):
        self.sla_threshold = datetime.utcnow() - timedelta(hours=sla_hours)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status.in_([ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS]),
            model.created_at < self.sla_threshold,
            model.is_deleted == False
        )


class ComplaintsByCategorySpecification(Specification):
    """Complaints by specific category."""
    
    def __init__(self, category: str):
        self.category = category
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.category == self.category,
            model.is_deleted == False
        )


# ==================== Maintenance Specifications ====================


class PendingMaintenanceSpecification(Specification):
    """Maintenance requests pending assignment."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == MaintenanceStatus.REQUESTED,
            model.is_deleted == False
        )


class InProgressMaintenanceSpecification(Specification):
    """Maintenance tasks in progress."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status.in_([
                MaintenanceStatus.ASSIGNED,
                MaintenanceStatus.IN_PROGRESS
            ]),
            model.is_deleted == False
        )


class OverdueMaintenanceSpecification(Specification):
    """Maintenance past expected completion date."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status.in_([
                MaintenanceStatus.ASSIGNED,
                MaintenanceStatus.IN_PROGRESS
            ]),
            model.expected_completion_date < datetime.utcnow(),
            model.is_deleted == False
        )


class MaintenanceRequiringVerificationSpecification(Specification):
    """Completed maintenance requiring verification."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == MaintenanceStatus.COMPLETED,
            model.verified_at.is_(None),
            model.is_deleted == False
        )


class PreventiveMaintenanceSpecification(Specification):
    """Equipment requiring preventive maintenance."""
    
    def __init__(self, maintenance_interval_days: int = 90):
        self.threshold_date = datetime.utcnow() - timedelta(days=maintenance_interval_days)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            or_(
                model.last_maintenance_date.is_(None),
                model.last_maintenance_date < self.threshold_date
            ),
            model.is_deleted == False
        )


# ==================== Attendance Specifications ====================


class PresentTodaySpecification(Specification):
    """Students marked present today."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        today = datetime.utcnow().date()
        return and_(
            func.date(model.attendance_date) == today,
            model.status == AttendanceStatus.PRESENT,
            model.is_deleted == False
        )


class AbsentTodaySpecification(Specification):
    """Students marked absent today."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        today = datetime.utcnow().date()
        return and_(
            func.date(model.attendance_date) == today,
            model.status == AttendanceStatus.ABSENT,
            model.is_deleted == False
        )


class LowAttendanceSpecification(Specification):
    """Students with low attendance percentage."""
    
    def __init__(self, threshold_percentage: float = 75.0, days: int = 30):
        self.threshold = threshold_percentage
        self.start_date = datetime.utcnow() - timedelta(days=days)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        # This would typically involve aggregation
        # Implementation depends on attendance tracking structure
        return True  # Placeholder


# ==================== Leave Specifications ====================


class PendingLeaveRequestsSpecification(Specification):
    """Leave requests pending approval."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == LeaveStatus.PENDING,
            model.is_deleted == False
        )


class ApprovedLeaveSpecification(Specification):
    """Approved leave requests."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.status == LeaveStatus.APPROVED,
            model.is_deleted == False
        )


class ActiveLeaveSpecification(Specification):
    """Currently active leave (student on leave today)."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        today = datetime.utcnow().date()
        return and_(
            model.status == LeaveStatus.APPROVED,
            model.start_date <= today,
            model.end_date >= today,
            model.is_deleted == False
        )


# ==================== Document Specifications ====================


class ExpiredDocumentsSpecification(Specification):
    """Documents that have expired."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        today = datetime.utcnow().date()
        return and_(
            model.expiry_date < today,
            model.is_deleted == False
        )


class ExpiringDocumentsSpecification(Specification):
    """Documents expiring within specified days."""
    
    def __init__(self, days: int = 30):
        self.threshold_date = datetime.utcnow().date() + timedelta(days=days)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        today = datetime.utcnow().date()
        return and_(
            model.expiry_date.isnot(None),
            model.expiry_date > today,
            model.expiry_date <= self.threshold_date,
            model.is_deleted == False
        )


class UnverifiedDocumentsSpecification(Specification):
    """Documents pending verification."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.verified_at.is_(None),
            model.is_deleted == False
        )


# ==================== Announcement Specifications ====================


class PublishedAnnouncementsSpecification(Specification):
    """Currently published announcements."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        from app.models.base.enums import AnnouncementStatus
        
        now = datetime.utcnow()
        return and_(
            model.status == AnnouncementStatus.PUBLISHED,
            or_(
                model.published_at.is_(None),
                model.published_at <= now
            ),
            or_(
                model.expires_at.is_(None),
                model.expires_at > now
            ),
            model.is_deleted == False
        )


class UrgentAnnouncementsSpecification(Specification):
    """Urgent/emergency announcements."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        from app.models.base.enums import AnnouncementPriority
        
        return and_(
            model.priority == AnnouncementPriority.URGENT,
            model.is_deleted == False
        )


class TargetedAnnouncementsSpecification(Specification):
    """Announcements targeted to specific user."""
    
    def __init__(self, user_id: Any, user_role: str):
        self.user_id = user_id
        self.user_role = user_role
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        # Implementation depends on targeting mechanism
        return True  # Placeholder


# ==================== Hostel Specifications ====================


class ActiveHostelsSpecification(Specification):
    """Active and operational hostels."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        from app.models.base.enums import HostelStatus
        
        return and_(
            model.status == HostelStatus.ACTIVE,
            model.is_deleted == False
        )


class HostelsWithAvailabilitySpecification(Specification):
    """Hostels with available beds."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return and_(
            model.available_beds > 0,
            model.is_deleted == False
        )


class HostelsByLocationSpecification(Specification):
    """Hostels within geographic radius."""
    
    def __init__(self, latitude: float, longitude: float, radius_km: float):
        self.latitude = latitude
        self.longitude = longitude
        self.radius_km = radius_km
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        # Haversine formula for distance calculation
        # This is a simplified version
        return True  # Placeholder - requires PostGIS or similar


# ==================== Utility Specifications ====================


class SoftDeletedSpecification(Specification):
    """Soft-deleted entities."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return model.is_deleted == True


class NotDeletedSpecification(Specification):
    """Non-deleted entities."""
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return model.is_deleted == False


class CreatedInLastDaysSpecification(Specification):
    """Entities created within last N days."""
    
    def __init__(self, days: int):
        self.threshold_date = datetime.utcnow() - timedelta(days=days)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return model.created_at >= self.threshold_date


class UpdatedInLastDaysSpecification(Specification):
    """Entities updated within last N days."""
    
    def __init__(self, days: int):
        self.threshold_date = datetime.utcnow() - timedelta(days=days)
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return model.updated_at >= self.threshold_date


class ByHostelSpecification(Specification):
    """Entities belonging to specific hostel (multi-tenant)."""
    
    def __init__(self, hostel_id: Any):
        self.hostel_id = hostel_id
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return model.hostel_id == self.hostel_id


class ByUserSpecification(Specification):
    """Entities created by specific user."""
    
    def __init__(self, user_id: Any):
        self.user_id = user_id
    
    def to_expression(self, model: Type[ModelType]) -> ClauseElement:
        return model.created_by == self.user_id