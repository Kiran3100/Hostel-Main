# models/core/hostel.py
from datetime import time
from decimal import Decimal
from typing import List, Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Float, Integer, JSON, Numeric, String, Time, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import HostelType, HostelStatus
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.core.room import Room
    from app.models.core.bed import Bed
    from app.models.core.student import Student
    from app.models.core.supervisor import Supervisor


class Hostel(BaseEntity):
    """Main Hostel entity."""
    __tablename__ = "core_hostel"

    # Basic
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    description: Mapped[Union[str, None]] = mapped_column(String(2000))
    hostel_type: Mapped[HostelType] = mapped_column(SAEnum(HostelType, name="hostel_type"))

    # Contact
    contact_email: Mapped[Union[str, None]] = mapped_column(String(255))
    contact_phone: Mapped[str] = mapped_column(String(20))

    # Address
    address_line1: Mapped[str] = mapped_column(String(255))
    address_line2: Mapped[Union[str, None]] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(100), index=True)
    pincode: Mapped[str] = mapped_column(String(6))
    country: Mapped[str] = mapped_column(String(100), default="India")

    # Web / media
    website_url: Mapped[Union[str, None]] = mapped_column(String(500))
    cover_image_url: Mapped[Union[str, None]] = mapped_column(String(500))
    gallery_images: Mapped[List[str]] = mapped_column(JSON, default=list)
    virtual_tour_url: Mapped[Union[str, None]] = mapped_column(String(500))

    # Pricing
    starting_price_monthly: Mapped[Union[Decimal, None]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    # Features
    amenities: Mapped[List[str]] = mapped_column(JSON, default=list)
    facilities: Mapped[List[str]] = mapped_column(JSON, default=list)
    security_features: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Policies
    rules: Mapped[Union[str, None]] = mapped_column(String(5000))
    check_in_time: Mapped[Union[time, None]] = mapped_column(Time)
    check_out_time: Mapped[Union[time, None]] = mapped_column(Time)
    visitor_policy: Mapped[Union[str, None]] = mapped_column(String(1000))
    late_entry_policy: Mapped[Union[str, None]] = mapped_column(String(1000))

    # Location metadata
    nearby_landmarks: Mapped[List[dict]] = mapped_column(JSON, default=list)
    connectivity_info: Mapped[Union[str, None]] = mapped_column(String(1000))

    # Capacity and status
    total_rooms: Mapped[int] = mapped_column(Integer, default=0)
    total_beds: Mapped[int] = mapped_column(Integer, default=0)
    occupied_beds: Mapped[int] = mapped_column(Integer, default=0)

    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)

    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[HostelStatus] = mapped_column(SAEnum(HostelStatus, name="hostel_status"))

    # Relationships
    rooms: Mapped[List["Room"]] = relationship(back_populates="hostel", cascade="all, delete-orphan")
    beds: Mapped[List["Bed"]] = relationship(back_populates="hostel", cascade="all, delete-orphan")
    students: Mapped[List["Student"]] = relationship(back_populates="hostel")
    supervisors: Mapped[List["Supervisor"]] = relationship(back_populates="hostel")

    def __repr__(self) -> str:
        return f"<Hostel id={self.id} name={self.name!r} city={self.city!r}>"