"""
User Address model configuration.
"""
from sqlalchemy import Boolean, Column, ForeignKey, Numeric, String, Text, DateTime
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import TimestampMixin, UUIDMixin

class UserAddress(BaseModel, UUIDMixin, TimestampMixin):
    """
    User address management with geolocation support.
    
    Supports multiple address types (home, permanent, billing)
    with verification and privacy controls.
    """
    __tablename__ = "user_addresses"
    __table_args__ = (
        {"comment": "User address information with geolocation"}
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True,
        comment="Foreign key to users table"
    )
    
    # Address Type & Priority
    address_type = Column(
        String(50), 
        default="home", 
        nullable=False,
        comment="Address type: home, permanent, billing, work"
    )
    is_primary = Column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="Primary address flag"
    )
    
    # Address Components (following AddressMixin pattern)
    address_line1 = Column(
        String(255), 
        nullable=False,
        comment="Primary address line (street, house number)"
    )
    address_line2 = Column(
        String(255), 
        nullable=True,
        comment="Secondary address line (apartment, suite)"
    )
    landmark = Column(
        String(255), 
        nullable=True,
        comment="Nearby landmark for easier navigation"
    )
    city = Column(
        String(100), 
        nullable=False,
        index=True,
        comment="City name"
    )
    state = Column(
        String(100), 
        nullable=False,
        index=True,
        comment="State/province/region"
    )
    country = Column(
        String(100), 
        nullable=False, 
        default="India",
        index=True,
        comment="Country name"
    )
    pincode = Column(
        String(20), 
        nullable=False,
        index=True,
        comment="Postal/ZIP code"
    )
    
    # Geolocation (for mapping and distance calculations)
    latitude = Column(
        Numeric(10, 8), 
        nullable=True,
        comment="Latitude coordinate"
    )
    longitude = Column(
        Numeric(11, 8), 
        nullable=True,
        comment="Longitude coordinate"
    )
    geohash = Column(
        String(20), 
        nullable=True,
        index=True,
        comment="Geohash for spatial queries"
    )
    
    # Verification & Validation
    is_verified = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Address verification status"
    )
    verified_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Verification timestamp"
    )
    verification_method = Column(
        String(50), 
        nullable=True,
        comment="Verification method: document, postal, manual"
    )
    
    # Privacy
    is_public = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Public visibility flag"
    )
    
    # Address Metadata
    label = Column(
        String(100), 
        nullable=True,
        comment="Custom address label (e.g., 'Parents House')"
    )
    instructions = Column(
        Text, 
        nullable=True,
        comment="Delivery or access instructions"
    )
    
    # Validity
    is_active = Column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="Active address flag"
    )
    valid_from = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Address validity start date"
    )
    valid_until = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Address validity end date (for temporary addresses)"
    )

    # Relationships
    user = relationship("User", back_populates="address")

    def __repr__(self):
        return f"<UserAddress user_id={self.user_id} type={self.address_type} city={self.city}>"
    
    @property
    def full_address(self):
        """Get formatted full address."""
        parts = [
            self.address_line1,
            self.address_line2,
            self.landmark,
            self.city,
            self.state,
            self.pincode,
            self.country
        ]
        return ", ".join([p for p in parts if p])
    
    @property
    def coordinates(self):
        """Get coordinates as tuple."""
        if self.latitude and self.longitude:
            return (float(self.latitude), float(self.longitude))
        return None