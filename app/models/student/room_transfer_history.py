# --- File: C:\Hostel-Main\app\models\student\room_transfer_history.py ---
"""
Room transfer history model.

Tracks complete history of room assignments and transfers for students.
Maintains audit trail of all room changes with reasons and approvals.
"""

from datetime import date as Date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, AuditMixin

if TYPE_CHECKING:
    from app.models.student.student import Student
    from app.models.hostel.hostel import Hostel
    from app.models.room.room import Room
    from app.models.room.bed import Bed
    from app.models.user.user import User


class RoomTransferHistory(BaseModel, TimestampMixin, AuditMixin):
    """
    Room transfer history model.
    
    Records all room assignments and transfers for students including:
    - Initial room assignment during check-in
    - Room changes/transfers during stay
    - Room changes due to maintenance
    - Room upgrades/downgrades
    - Final room during checkout
    
    Maintains complete audit trail with reasons, approvals, and
    financial implications of each transfer.
    """

    __tablename__ = "room_transfer_history"

    # Foreign Keys
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to student",
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Hostel (for cross-hostel transfers)",
    )
    
    # Previous Room/Bed (null for initial assignment)
    from_room_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Previous room (null for initial assignment)",
    )
    
    from_bed_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous bed",
    )
    
    # New Room/Bed
    to_room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="New room assigned",
    )
    
    to_bed_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
        comment="New bed assigned",
    )

    # Transfer Details
    transfer_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Transfer type (initial, request, admin, maintenance, upgrade)",
    )
    
    transfer_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Effective transfer date",
    )
    
    move_in_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Date moved into new room",
    )
    
    move_out_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Date moved out (null if current)",
    )

    # Reason and Documentation
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for transfer",
    )
    
    reason_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Reason category (maintenance, request, upgrade, etc.)",
    )
    
    student_initiated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether transfer was student-initiated",
    )

    # Approval Workflow
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether transfer required approval",
    )
    
    requested_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who requested transfer",
    )
    
    approved_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved transfer",
    )
    
    approved_at: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Approval timestamp",
    )
    
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="approved",
        comment="Approval status (pending, approved, rejected)",
    )
    
    approval_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Approval/rejection notes",
    )

    # Financial Impact
    previous_rent: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Previous monthly rent",
    )
    
    new_rent: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="New monthly rent",
    )
    
    rent_difference: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Rent difference (positive=increase, negative=decrease)",
    )
    
    transfer_charges: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="One-time transfer charges",
    )
    
    prorated_rent_calculated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether prorated rent was calculated",
    )
    
    prorated_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Prorated rent amount for partial month",
    )

    # Room Condition and Handover
    previous_room_condition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Condition of previous room at move-out",
    )
    
    previous_room_damages: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Any damages in previous room",
    )
    
    damage_charges: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Charges for damages",
    )
    
    new_room_condition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Condition of new room at move-in",
    )
    
    handover_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether room handover is completed",
    )
    
    handover_photos: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URLs of handover photos (comma-separated)",
    )

    # Supporting Documents
    request_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Transfer request document",
    )
    
    approval_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Approval/authorization document",
    )
    
    supporting_documents: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Other supporting documents (comma-separated URLs)",
    )

    # Notifications
    student_notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Student notified about transfer",
    )
    
    student_notified_at: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Student notification timestamp",
    )
    
    guardian_notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Guardian notified about transfer",
    )
    
    guardian_notified_at: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Guardian notification timestamp",
    )

    # Status Tracking
    transfer_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Transfer status (pending, in_progress, completed, cancelled)",
    )
    
    is_current_assignment: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether this is the current room assignment",
    )
    
    completion_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Transfer completion date",
    )
    
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason if transfer was cancelled",
    )

    # Priority and Urgency
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="Transfer priority (low, normal, high, urgent)",
    )
    
    is_emergency: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Emergency transfer",
    )

    # Notes
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Internal administrative notes",
    )
    
    student_feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Student feedback after transfer",
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="room_transfer_history",
        lazy="joined",
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )
    
    from_room: Mapped["Room | None"] = relationship(
        "Room",
        foreign_keys=[from_room_id],
        lazy="select",
    )
    
    from_bed: Mapped["Bed | None"] = relationship(
        "Bed",
        foreign_keys=[from_bed_id],
        lazy="select",
    )
    
    to_room: Mapped["Room"] = relationship(
        "Room",
        foreign_keys=[to_room_id],
        lazy="select",
    )
    
    to_bed: Mapped["Bed | None"] = relationship(
        "Bed",
        foreign_keys=[to_bed_id],
        lazy="select",
    )
    
    requester: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[requested_by],
        lazy="select",
    )
    
    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTransferHistory(id={self.id}, student_id={self.student_id}, "
            f"type={self.transfer_type}, date={self.transfer_date})>"
        )

    @property
    def duration_days(self) -> int | None:
        """Calculate duration of stay in this room."""
        if not self.move_out_date:
            # Current assignment - calculate till today
            from datetime import date as dt_date
            return (dt_date.today() - self.move_in_date).days
        
        return (self.move_out_date - self.move_in_date).days

    @property
    def is_rent_increase(self) -> bool:
        """Check if transfer resulted in rent increase."""
        if self.rent_difference:
            return self.rent_difference > 0
        return False

    @property
    def is_rent_decrease(self) -> bool:
        """Check if transfer resulted in rent decrease."""
        if self.rent_difference:
            return self.rent_difference < 0
        return False

    @property
    def is_initial_assignment(self) -> bool:
        """Check if this is initial room assignment."""
        return (
            self.transfer_type == "initial"
            or self.from_room_id is None
        )

    @property
    def total_charges(self) -> Decimal:
        """Calculate total charges for transfer."""
        return self.transfer_charges + self.damage_charges

    @property
    def is_completed(self) -> bool:
        """Check if transfer is completed."""
        return self.transfer_status == "completed"

    @property
    def is_pending(self) -> bool:
        """Check if transfer is pending."""
        return self.transfer_status == "pending"
