# --- File: app/models/visitor/visitor_favorite.py ---
"""
Visitor favorites/wishlist model.

This module defines visitor's favorite hostels with price tracking,
notes, and comparison features.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.visitor.visitor import Visitor
    from app.models.hostel.hostel import Hostel

__all__ = [
    "VisitorFavorite",
    "FavoriteComparison",
    "FavoritePriceHistory",
]


class VisitorFavorite(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Visitor's favorite/saved hostels with tracking and notes.
    
    Tracks favorite hostels with price monitoring, personal notes,
    and view statistics for personalized recommendations.
    """

    __tablename__ = "visitor_favorites"
    __table_args__ = (
        Index("idx_visitor_favorite_visitor_id", "visitor_id"),
        Index("idx_visitor_favorite_hostel_id", "hostel_id"),
        Index("idx_visitor_favorite_added_at", "added_at"),
        Index("idx_visitor_favorite_price_drop", "has_price_drop"),
        UniqueConstraint(
            "visitor_id",
            "hostel_id",
            name="uq_visitor_favorite",
        ),
        CheckConstraint(
            "price_when_saved >= 0",
            name="ck_visitor_favorite_price_saved_positive",
        ),
        CheckConstraint(
            "current_price >= 0",
            name="ck_visitor_favorite_current_price_positive",
        ),
        CheckConstraint(
            "times_viewed >= 0",
            name="ck_visitor_favorite_views_positive",
        ),
        {"comment": "Visitor's favorite/saved hostels with price tracking"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to hostel",
    )

    # ==================== Cached Hostel Information ====================
    hostel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel name",
    )
    hostel_slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel slug",
    )
    hostel_city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Cached hostel city",
    )
    hostel_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Cached hostel type",
    )

    # ==================== Price Tracking ====================
    price_when_saved: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Starting price when hostel was saved",
    )
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Current hostel price",
    )
    has_price_drop: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        index=True,
        comment="Whether price has dropped since saving",
    )
    price_drop_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Price drop percentage if applicable",
    )
    price_drop_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Absolute price drop amount",
    )

    # ==================== Availability ====================
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Current number of available beds",
    )
    has_availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Whether hostel has available beds",
    )

    # ==================== Rating Information ====================
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default="0.00",
        comment="Cached average rating",
    )
    total_reviews: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cached total reviews count",
    )

    # ==================== Media ====================
    cover_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Cached cover image URL",
    )

    # ==================== Personal Notes ====================
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Personal notes about this hostel",
    )

    # ==================== Timestamps ====================
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="CURRENT_TIMESTAMP",
        index=True,
        comment="When hostel was added to favorites",
    )
    last_price_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When price was last checked",
    )
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When hostel was last viewed",
    )

    # ==================== View Tracking ====================
    times_viewed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of times hostel was viewed after saving",
    )

    # ==================== Alerts ====================
    alert_on_price_drop: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Send alert on price drops",
    )
    alert_on_availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Send alert on new availability",
    )

    # ==================== Metadata ====================
    favorite_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional favorite data and tracking",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        back_populates="favorites",
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
    )

    price_history: Mapped[list["FavoritePriceHistory"]] = relationship(
        "FavoritePriceHistory",
        back_populates="favorite",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # ==================== Properties ====================
    @property
    def days_in_favorites(self) -> int:
        """Calculate days since hostel was added to favorites."""
        return (datetime.utcnow() - self.added_at).days

    @property
    def is_highly_rated(self) -> bool:
        """Check if hostel is highly rated (>= 4.0 stars)."""
        return self.average_rating >= Decimal("4.0")

    @property
    def is_popular(self) -> bool:
        """Check if hostel is popular (many reviews)."""
        return self.total_reviews >= 50

    @property
    def is_frequently_viewed(self) -> bool:
        """Check if visitor views this hostel frequently."""
        return self.times_viewed >= 3

    @property
    def price_savings(self) -> Optional[Decimal]:
        """Calculate price savings if price dropped."""
        if self.has_price_drop:
            return self.price_drop_amount
        return None

    def __repr__(self) -> str:
        return (
            f"<VisitorFavorite(id={self.id}, visitor_id={self.visitor_id}, "
            f"hostel_id={self.hostel_id})>"
        )


class FavoriteComparison(UUIDMixin, TimestampModel):
    """
    Comparison sessions for favorite hostels.
    
    Tracks when visitors compare multiple favorite hostels
    for decision-making analytics.
    """

    __tablename__ = "favorite_comparisons"
    __table_args__ = (
        Index("idx_favorite_comparison_visitor_id", "visitor_id"),
        Index("idx_favorite_comparison_created_at", "created_at"),
        {"comment": "Favorite hostel comparison sessions"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    # ==================== Compared Favorites ====================
    favorite_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment="List of favorite IDs being compared",
    )

    # ==================== Comparison Criteria ====================
    comparison_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Criteria used for comparison",
    )

    # ==================== Comparison Result ====================
    selected_favorite_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="Favorite ID selected after comparison (if any)",
    )

    # ==================== Timing ====================
    comparison_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time spent on comparison",
    )

    # ==================== Metadata ====================
    comparison_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional comparison data and insights",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<FavoriteComparison(id={self.id}, visitor_id={self.visitor_id}, "
            f"favorites_count={len(self.favorite_ids)})>"
        )


class FavoritePriceHistory(UUIDMixin, TimestampModel):
    """
    Price history tracking for favorite hostels.
    
    Maintains historical price data for favorites to enable
    price trend analysis and drop detection.
    """

    __tablename__ = "favorite_price_history"
    __table_args__ = (
        Index("idx_favorite_price_history_favorite_id", "favorite_id"),
        Index("idx_favorite_price_history_recorded_at", "recorded_at"),
        CheckConstraint(
            "price >= 0",
            name="ck_favorite_price_history_price_positive",
        ),
        {"comment": "Historical price tracking for favorite hostels"},
    )

    # ==================== Core Fields ====================
    favorite_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitor_favorites.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to favorite",
    )

    # ==================== Price Data ====================
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Price at this point in time",
    )
    price_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of price (monthly_rent, discounted, etc.)",
    )

    # ==================== Timestamp ====================
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this price was recorded",
    )

    # ==================== Change Tracking ====================
    price_change_from_previous: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Change from previous price",
    )
    price_change_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Percentage change from previous price",
    )

    # ==================== Metadata ====================
    price_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional price data and context",
    )

    # ==================== Relationships ====================
    favorite: Mapped["VisitorFavorite"] = relationship(
        "VisitorFavorite",
        back_populates="price_history",
    )

    def __repr__(self) -> str:
        return (
            f"<FavoritePriceHistory(id={self.id}, favorite_id={self.favorite_id}, "
            f"price={self.price})>"
        )