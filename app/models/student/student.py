# --- File: C:\Hostel-Main\app\models\student\student.py ---
"""
Student core model.

Represents the main student entity linking users to hostels with
comprehensive student-specific information and lifecycle management.
"""

from datetime import date as Date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from app.models.base.enums import StudentStatus, IDProofType, DietaryPreference

if TYPE_CHECKING:
    from app.models.user.user import User
    from app.models.hostel.hostel import Hostel
    from app.models.room.room import Room
    from app.models.room.bed import Bed
    from app.models.booking.booking import Booking
    from app.models.student.student_profile import StudentProfile
    from app.models.student.student_document import StudentDocument
    from app.models.student.student_preferences import StudentPreferences
    from app.models.student.guardian_contact import GuardianContact
    from app.models.student.room_transfer_history import RoomTransferHistory
    from app.models.payment.payment import Payment
    from app.models.complaint.complaint import Complaint
    from app.models.attendance.attendance_record import AttendanceRecord
    from app.models.leave.leave_application import LeaveApplication


class Student(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Core student model.
    
    Represents a student who has been admitted to the hostel system,
    either through direct admission or booking conversion.
    
    Lifecycle:
        1. Created from booking conversion or direct admission
        2. Check-in with room/bed assignment
        3. Active residency with payments and attendance
        4. Notice period (optional)
        5. Check-out and account settlement
    
    Relationships:
        - Links to User for authentication and basic profile
        - Links to Hostel for current residence
        - Links to Room and Bed for accommodation
        - Links to Booking if converted from reservation
        - Has StudentProfile for extended information
        - Has StudentDocuments for verification
        - Has GuardianContacts for emergency
        - Has Payments for financial tracking
        - Has Complaints for issue management
        - Has AttendanceRecords for presence tracking
    """

    __tablename__ = "students"

    # Foreign Keys - Core Relationships
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to user account",
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Current hostel assignment",
    )
    
    room_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Current room assignment (null if not assigned)",
    )
    
    bed_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Current bed assignment (null if not assigned)",
    )
    
    booking_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source booking if converted from reservation",
    )

    # Identification Documents
    id_proof_type: Mapped[IDProofType | None] = mapped_column(
        Enum(IDProofType, native_enum=False, length=50),
        nullable=True,
        comment="Type of ID proof submitted",
    )
    
    id_proof_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="ID proof number/reference",
    )
    
    id_proof_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Uploaded ID proof document URL",
    )
    
    id_proof_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="ID proof verification status",
    )
    
    id_proof_verified_at: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="ID proof verification timestamp",
    )
    
    id_proof_verified_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who verified ID proof",
    )

    # Guardian Information (Required for students)
    guardian_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Guardian/parent full name",
    )
    
    guardian_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Guardian contact phone",
    )
    
    guardian_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Guardian email address",
    )
    
    guardian_relation: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Relation to student (Father, Mother, etc.)",
    )
    
    guardian_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Guardian residential address",
    )

    # Institutional Information (for students)
    institution_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="College/University/School name",
    )
    
    course: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Course/Program name",
    )
    
    year_of_study: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Current year/semester",
    )
    
    student_id_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="College/University ID number",
    )
    
    institutional_id_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Uploaded institutional ID card URL",
    )
    
    institutional_id_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Institutional ID verification status",
    )

    # Employment Information (for working professionals)
    company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Employer/Company name",
    )
    
    designation: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Job title/designation",
    )
    
    company_id_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Company ID card URL",
    )
    
    company_id_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Company ID verification status",
    )

    # Check-in/Check-out Dates
    check_in_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Actual check-in date",
    )
    
    expected_checkout_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Expected/planned checkout date",
    )
    
    actual_checkout_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Actual checkout date (when checked out)",
    )
    
    checkout_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from checkout process",
    )

    # Financial Information
    security_deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Security deposit amount",
    )
    
    security_deposit_paid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Security deposit payment status",
    )
    
    security_deposit_paid_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Date security deposit was paid",
    )
    
    security_deposit_refund_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Security deposit refund amount (after deductions)",
    )
    
    security_deposit_refund_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Security deposit refund date",
    )
    
    monthly_rent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        index=True,
        comment="Monthly rent amount for the student",
    )
    
    rent_due_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Day of month when rent is due (1-31)",
    )

    # Meal Preferences
    mess_subscribed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Subscribed to mess/canteen facility",
    )
    
    dietary_preference: Mapped[DietaryPreference | None] = mapped_column(
        Enum(DietaryPreference, native_enum=False, length=50),
        nullable=True,
        comment="Dietary preference (veg/non-veg/vegan/jain)",
    )
    
    food_allergies: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Food allergies and restrictions",
    )
    
    mess_advance_paid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Mess advance payment status",
    )
    
    mess_monthly_charge: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Monthly mess charges",
    )

    # Status Tracking
    student_status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, native_enum=False, length=50),
        nullable=False,
        default=StudentStatus.ACTIVE,
        index=True,
        comment="Current student status",
    )
    
    notice_period_start: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Notice period start date (if leaving)",
    )
    
    notice_period_end: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Notice period end date",
    )
    
    notice_period_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Notice period duration in days",
    )

    # Additional Tracking
    initial_rent_paid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether initial/first month rent is paid",
    )
    
    documents_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="All required documents verified",
    )
    
    all_clearances_received: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="All clearances received during checkout",
    )
    
    forwarding_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Forwarding address after checkout",
    )

    # Internal Notes
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Internal administrative notes",
    )
    
    special_requirements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Special requirements or accommodations",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="student",
        lazy="joined",
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="students",
        lazy="joined",
    )
    
    room: Mapped["Room | None"] = relationship(
        "Room",
        back_populates="students",
        lazy="select",
    )
    
    bed: Mapped["Bed | None"] = relationship(
        "Bed",
        back_populates="student",
        lazy="select",
    )
    
    booking: Mapped["Booking | None"] = relationship(
        "Booking",
        back_populates="student",
        lazy="select",
    )
    
    profile: Mapped["StudentProfile | None"] = relationship(
        "StudentProfile",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    documents: Mapped[list["StudentDocument"]] = relationship(
        "StudentDocument",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    preferences: Mapped["StudentPreferences | None"] = relationship(
        "StudentPreferences",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    guardian_contacts: Mapped[list["GuardianContact"]] = relationship(
        "GuardianContact",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    room_transfer_history: Mapped[list["RoomTransferHistory"]] = relationship(
        "RoomTransferHistory",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(RoomTransferHistory.created_at)",
    )
    
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="student",
        lazy="select",
    )
    
    complaints: Mapped[list["Complaint"]] = relationship(
        "Complaint",
        back_populates="student",
        lazy="select",
    )
    
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord",
        back_populates="student",
        lazy="select",
    )
    
    leave_applications: Mapped[list["LeaveApplication"]] = relationship(
        "LeaveApplication",
        back_populates="student",
        lazy="select",
    )

    # Verifier relationship (for ID proof verification)
    verified_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[id_proof_verified_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Student(id={self.id}, user_id={self.user_id}, "
            f"hostel_id={self.hostel_id}, status={self.student_status})>"
        )

    @property
    def is_checked_in(self) -> bool:
        """Check if student is currently checked in."""
        return (
            self.check_in_date is not None
            and self.actual_checkout_date is None
        )

    @property
    def is_active_resident(self) -> bool:
        """Check if student is an active resident."""
        return (
            self.student_status == StudentStatus.ACTIVE
            and self.is_checked_in
        )

    @property
    def days_in_hostel(self) -> int | None:
        """Calculate total days stayed in hostel."""
        if not self.check_in_date:
            return None
        
        from datetime import date as dt_date
        end_date = self.actual_checkout_date or dt_date.today()
        return (end_date - self.check_in_date).days

    @property
    def is_student(self) -> bool:
        """Check if this is an institutional student."""
        return bool(
            self.institution_name
            or self.course
            or self.student_id_number
        )

    @property
    def is_working_professional(self) -> bool:
        """Check if this is a working professional."""
        return bool(self.company_name or self.designation)

    @property
    def has_valid_guardian(self) -> bool:
        """Check if guardian information is complete."""
        return bool(
            self.guardian_name
            and self.guardian_phone
        )

    @property
    def all_documents_verified(self) -> bool:
        """Check if all required documents are verified."""
        has_id_verified = self.id_proof_verified
        
        # Check institutional ID if student
        if self.is_student:
            has_institutional = self.institutional_id_verified
            return has_id_verified and has_institutional
        
        # Check company ID if working professional
        if self.is_working_professional:
            has_company = self.company_id_verified
            return has_id_verified and has_company
        
        return has_id_verified

    @property
    def financial_clearance_pending(self) -> bool:
        """Check if financial clearances are pending."""
        # This would typically check related payment records
        # For now, basic check on security deposit
        if not self.security_deposit_paid:
            return True
        
        if self.actual_checkout_date and not self.security_deposit_refund_date:
            return True
        
        return False
