"""
Leave calendar and scheduling schemas.

Provides calendar views, events, and occupancy tracking
for hostel leave management and planning.
"""

from datetime import date as Date, datetime
from typing import List, Union

from pydantic import ConfigDict, Field, computed_field
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import LeaveStatus, LeaveType

__all__ = [
    "CalendarEvent",
    "CalendarDay", 
    "StudentCalendarResponse",
    "HostelCalendarResponse",
    "OccupancyStats",
]


class CalendarEvent(BaseSchema):
    """
    Calendar event representing a leave application.
    
    Used in calendar views to display leave information.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "student_name": "John Student",
                "leave_type": "casual",
                "status": "approved",
                "start_date": "2024-02-01",
                "end_date": "2024-02-05",
                "title": "Casual Leave",
                "is_multi_day": True
            }
        }
    )

    leave_id: UUID = Field(..., description="Leave application ID")
    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    room_number: Union[str, None] = Field(None, description="Room number")
    leave_type: LeaveType = Field(..., description="Leave type")
    status: LeaveStatus = Field(..., description="Leave status")
    start_date: Date = Field(..., description="Leave start date")
    end_date: Date = Field(..., description="Leave end date")
    title: str = Field(..., description="Event title")
    description: Union[str, None] = Field(None, description="Event description")
    
    @computed_field
    @property
    def is_multi_day(self) -> bool:
        """Check if event spans multiple days."""
        return self.start_date != self.end_date
    
    @computed_field
    @property
    def duration_days(self) -> int:
        """Calculate event duration in days."""
        return (self.end_date - self.start_date).days + 1


class CalendarDay(BaseSchema):
    """
    Single day in calendar view with events and metadata.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-02-01",
                "events": [],
                "is_today": False,
                "is_weekend": False,
                "students_on_leave": 5,
                "occupancy_rate": 0.85
            }
        }
    )

    date: Date = Field(..., description="Calendar date")
    events: List[CalendarEvent] = Field(default=[], description="Events on this date")
    is_today: bool = Field(default=False, description="Is today's date")
    is_weekend: bool = Field(default=False, description="Is weekend day")
    is_holiday: bool = Field(default=False, description="Is public holiday")
    students_on_leave: int = Field(default=0, description="Number of students on leave")
    total_students: Union[int, None] = Field(None, description="Total students in hostel")
    
    @computed_field
    @property
    def occupancy_rate(self) -> float:
        """Calculate occupancy rate for the day."""
        if self.total_students is None or self.total_students == 0:
            return 1.0
        return (self.total_students - self.students_on_leave) / self.total_students


class StudentCalendarResponse(BaseSchema):
    """
    Calendar response for individual student view.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_name": "John Student",
                "year": 2024,
                "month": 2,
                "days": []
            }
        }
    )

    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    year: int = Field(..., description="Calendar year")
    month: int = Field(..., description="Calendar month")
    days: List[CalendarDay] = Field(..., description="Calendar days")
    total_events: int = Field(default=0, description="Total events in month")
    upcoming_leaves: int = Field(default=0, description="Upcoming approved leaves")
    pending_applications: int = Field(default=0, description="Pending applications")


class HostelCalendarResponse(BaseSchema):
    """
    Calendar response for hostel-wide view.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "hostel_name": "North Campus Hostel A",
                "year": 2024,
                "month": 2,
                "days": [],
                "total_capacity": 200
            }
        }
    )

    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    year: int = Field(..., description="Calendar year")
    month: int = Field(..., description="Calendar month")
    days: List[CalendarDay] = Field(..., description="Calendar days")
    total_capacity: int = Field(..., description="Total hostel capacity")
    average_occupancy: float = Field(..., description="Average occupancy rate")
    peak_leave_days: List[Date] = Field(default=[], description="Days with highest leaves")
    total_leave_applications: int = Field(default=0, description="Total applications in month")


class OccupancyStats(BaseSchema):
    """
    Occupancy statistics and trends for hostel management.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "period_start": "2024-02-01",
                "period_end": "2024-02-29",
                "total_capacity": 200,
                "average_occupancy": 185,
                "occupancy_rate": 0.925
            }
        }
    )

    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    period_start: Date = Field(..., description="Analysis period start")
    period_end: Date = Field(..., description="Analysis period end")
    total_capacity: int = Field(..., description="Total hostel capacity")
    average_occupancy: float = Field(..., description="Average daily occupancy")
    min_occupancy: int = Field(..., description="Minimum occupancy")
    max_occupancy: int = Field(..., description="Maximum occupancy")
    occupancy_rate: float = Field(..., description="Overall occupancy rate")
    peak_leave_date: Union[Date, None] = Field(None, description="Date with most leaves")
    peak_leave_count: int = Field(default=0, description="Maximum leaves on single day")
    trend: str = Field(default="stable", description="Occupancy trend")
    
    @computed_field
    @property
    def occupancy_percentage(self) -> float:
        """Get occupancy as percentage."""
        return round(self.occupancy_rate * 100, 2)