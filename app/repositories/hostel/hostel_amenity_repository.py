"""
Hostel amenity repository for comprehensive amenity management.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import selectinload, joinedload

from app.models.hostel.hostel_amenity import HostelAmenity, AmenityCategory, AmenityBooking
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationRequest, PaginationResult


class AvailableAmenitiesSpecification(Specification[HostelAmenity]):
    """Specification for available amenities."""
    
    def is_satisfied_by(self, entity: HostelAmenity) -> bool:
        return entity.is_available and entity.has_capacity
    
    def to_sql_condition(self):
        return and_(
            HostelAmenity.is_available == True,
            or_(
                HostelAmenity.capacity.is_(None),
                HostelAmenity.current_usage < HostelAmenity.capacity
            )
        )


class BookableAmenitiesSpecification(Specification[HostelAmenity]):
    """Specification for bookable amenities."""
    
    def is_satisfied_by(self, entity: HostelAmenity) -> bool:
        return entity.is_bookable and entity.is_available
    
    def to_sql_condition(self):
        return and_(
            HostelAmenity.is_bookable == True,
            HostelAmenity.is_available == True
        )


class HostelAmenityRepository(BaseRepository[HostelAmenity]):
    """Repository for hostel amenity management."""
    
    def __init__(self, session):
        super().__init__(session, HostelAmenity)
    
    # ===== Core Operations =====
    
    async def find_by_hostel(self, hostel_id: UUID, include_inactive: bool = False) -> List[HostelAmenity]:
        """Find all amenities for a hostel."""
        criteria = {"hostel_id": hostel_id}
        if not include_inactive:
            criteria["is_available"] = True
        
        return await self.find_by_criteria(
            criteria,
            order_by=[asc(HostelAmenity.display_order), asc(HostelAmenity.name)]
        )
    
    async def find_by_category(
        self,
        hostel_id: UUID,
        category: str,
        only_available: bool = True
    ) -> List[HostelAmenity]:
        """Find amenities by category for a hostel."""
        criteria = {
            "hostel_id": hostel_id,
            "category": category
        }
        if only_available:
            criteria["is_available"] = True
        
        return await self.find_by_criteria(
            criteria,
            order_by=[asc(HostelAmenity.display_order)]
        )
    
    async def find_bookable_amenities(self, hostel_id: UUID) -> List[HostelAmenity]:
        """Find all bookable amenities for a hostel."""
        spec = BookableAmenitiesSpecification()
        return await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=spec.to_sql_condition(),
            order_by=[asc(HostelAmenity.category), asc(HostelAmenity.display_order)]
        )
    
    async def find_available_amenities(self, hostel_id: UUID) -> List[HostelAmenity]:
        """Find available amenities with capacity."""
        spec = AvailableAmenitiesSpecification()
        return await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=spec.to_sql_condition(),
            order_by=[asc(HostelAmenity.category), asc(HostelAmenity.display_order)]
        )
    
    # ===== Booking Operations =====
    
    async def check_availability_for_booking(
        self,
        amenity_id: UUID,
        start_time: datetime,
        end_time: datetime,
        participants: int = 1
    ) -> bool:
        """Check if amenity is available for booking in given time slot."""
        amenity = await self.get_by_id(amenity_id)
        if not amenity or not amenity.can_be_used():
            return False
        
        # Check capacity
        if amenity.capacity and participants > amenity.capacity:
            return False
        
        # Check for conflicting bookings
        conflicting_bookings = await self.session.query(AmenityBooking).filter(
            and_(
                AmenityBooking.amenity_id == amenity_id,
                AmenityBooking.status.in_(["confirmed", "pending"]),
                or_(
                    and_(
                        AmenityBooking.start_time <= start_time,
                        AmenityBooking.end_time > start_time
                    ),
                    and_(
                        AmenityBooking.start_time < end_time,
                        AmenityBooking.end_time >= end_time
                    ),
                    and_(
                        AmenityBooking.start_time >= start_time,
                        AmenityBooking.end_time <= end_time
                    )
                )
            )
        ).count()
        
        return conflicting_bookings == 0
    
    async def get_amenity_schedule(
        self,
        amenity_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[AmenityBooking]:
        """Get booking schedule for an amenity."""
        return await self.session.query(AmenityBooking).filter(
            and_(
                AmenityBooking.amenity_id == amenity_id,
                AmenityBooking.start_time >= start_date,
                AmenityBooking.end_time <= end_date,
                AmenityBooking.status.in_(["confirmed", "pending"])
            )
        ).order_by(AmenityBooking.start_time).all()
    
    # ===== Maintenance Tracking =====
    
    async def find_amenities_needing_maintenance(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[HostelAmenity]:
        """Find amenities that need maintenance."""
        criteria = {}
        if hostel_id:
            criteria["hostel_id"] = hostel_id
        
        return await self.find_by_criteria(
            criteria,
            custom_filter=or_(
                HostelAmenity.condition_status.in_(["fair", "poor"]),
                HostelAmenity.next_maintenance_at <= datetime.utcnow()
            ),
            order_by=[
                asc(HostelAmenity.condition_status),
                asc(HostelAmenity.next_maintenance_at)
            ]
        )
    
    async def update_maintenance_status(
        self,
        amenity_id: UUID,
        condition_status: str,
        next_maintenance_date: Optional[datetime] = None
    ) -> HostelAmenity:
        """Update maintenance status of an amenity."""
        amenity = await self.get_by_id(amenity_id)
        if not amenity:
            raise ValueError(f"Amenity {amenity_id} not found")
        
        amenity.condition_status = condition_status
        amenity.last_maintained_at = datetime.utcnow()
        if next_maintenance_date:
            amenity.next_maintenance_at = next_maintenance_date
        
        await self.session.commit()
        return amenity
    
    # ===== Analytics =====
    
    async def get_amenity_usage_stats(self, hostel_id: UUID) -> Dict[str, Any]:
        """Get usage statistics for hostel amenities."""
        query = self.session.query(
            HostelAmenity.category,
            func.count(HostelAmenity.id).label("total_amenities"),
            func.sum(func.case([(HostelAmenity.is_available == True, 1)], else_=0)).label("available_amenities"),
            func.sum(func.case([(HostelAmenity.is_bookable == True, 1)], else_=0)).label("bookable_amenities"),
            func.avg(HostelAmenity.current_usage).label("avg_usage")
        ).filter(
            HostelAmenity.hostel_id == hostel_id
        ).group_by(HostelAmenity.category)
        
        results = await query.all()
        
        stats = {}
        for row in results:
            stats[row.category] = {
                "total_amenities": row.total_amenities,
                "available_amenities": row.available_amenities,
                "bookable_amenities": row.bookable_amenities,
                "average_usage": float(row.avg_usage or 0)
            }
        
        return stats
    
    async def get_popular_amenities(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most popular amenities by usage."""
        query = self.session.query(
            HostelAmenity,
            func.count(AmenityBooking.id).label("booking_count")
        ).outerjoin(
            AmenityBooking
        ).filter(
            HostelAmenity.hostel_id == hostel_id
        ).group_by(
            HostelAmenity.id
        ).order_by(
            desc("booking_count"),
            desc(HostelAmenity.current_usage)
        ).limit(limit)
        
        results = await query.all()
        
        return [
            {
                "amenity": amenity,
                "booking_count": booking_count,
                "usage_rate": (amenity.current_usage / max(amenity.capacity or 1, 1)) * 100 if amenity.capacity else 0
            }
            for amenity, booking_count in results
        ]


class AmenityCategoryRepository(BaseRepository[AmenityCategory]):
    """Repository for amenity category management."""
    
    def __init__(self, session):
        super().__init__(session, AmenityCategory)
    
    async def find_active_categories(self) -> List[AmenityCategory]:
        """Find all active amenity categories."""
        return await self.find_by_criteria(
            {"is_active": True},
            order_by=[asc(AmenityCategory.display_order), asc(AmenityCategory.name)]
        )
    
    async def find_basic_categories(self) -> List[AmenityCategory]:
        """Find basic/essential amenity categories."""
        return await self.find_by_criteria(
            {"is_basic": True, "is_active": True},
            order_by=[asc(AmenityCategory.display_order)]
        )


class AmenityBookingRepository(BaseRepository[AmenityBooking]):
    """Repository for amenity booking management."""
    
    def __init__(self, session):
        super().__init__(session, AmenityBooking)
    
    async def create_booking(
        self,
        amenity_id: UUID,
        student_id: UUID,
        start_time: datetime,
        end_time: datetime,
        participants_count: int = 1,
        notes: Optional[str] = None
    ) -> AmenityBooking:
        """Create a new amenity booking."""
        booking_data = {
            "amenity_id": amenity_id,
            "student_id": student_id,
            "booking_date": datetime.utcnow().date(),
            "start_time": start_time,
            "end_time": end_time,
            "participants_count": participants_count,
            "notes": notes,
            "status": "pending"
        }
        
        return await self.create(booking_data)
    
    async def find_student_bookings(
        self,
        student_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AmenityBooking]:
        """Find bookings for a student."""
        criteria = {"student_id": student_id}
        custom_filter = None
        
        if start_date and end_date:
            custom_filter = and_(
                AmenityBooking.start_time >= start_date,
                AmenityBooking.end_time <= end_date
            )
        elif start_date:
            custom_filter = AmenityBooking.start_time >= start_date
        
        return await self.find_by_criteria(
            criteria,
            custom_filter=custom_filter,
            order_by=[desc(AmenityBooking.start_time)]
        )
    
    async def find_amenity_bookings(
        self,
        amenity_id: UUID,
        status: Optional[str] = None
    ) -> List[AmenityBooking]:
        """Find bookings for an amenity."""
        criteria = {"amenity_id": amenity_id}
        if status:
            criteria["status"] = status
        
        return await self.find_by_criteria(
            criteria,
            order_by=[asc(AmenityBooking.start_time)]
        )
    
    async def confirm_booking(self, booking_id: UUID) -> AmenityBooking:
        """Confirm a pending booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        
        if booking.status != "pending":
            raise ValueError(f"Booking {booking_id} is not in pending status")
        
        booking.status = "confirmed"
        await self.session.commit()
        return booking
    
    async def cancel_booking(
        self,
        booking_id: UUID,
        reason: Optional[str] = None
    ) -> AmenityBooking:
        """Cancel a booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        
        booking.status = "cancelled"
        booking.cancelled_at = datetime.utcnow()
        booking.cancellation_reason = reason
        await self.session.commit()
        return booking