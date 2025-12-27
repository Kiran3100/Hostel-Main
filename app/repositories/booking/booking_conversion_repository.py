# app/repositories/booking/booking_conversion_repository.py
"""
Booking conversion repository for student conversion management.

Provides conversion workflow management, checklist tracking, document verification,
and conversion analytics.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core1.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_conversion import (
    BookingConversion,
    ChecklistItem,
    ConversionChecklist,
)
from app.models.booking.booking import Booking
from app.models.base.enums import BookingStatus
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingConversionRepository(BaseRepository[BookingConversion]):
    """
    Repository for booking conversion operations.
    
    Provides:
    - Conversion record management
    - Conversion workflow tracking
    - Document verification
    - Payment tracking
    - Conversion analytics
    """
    
    def __init__(self, session: Session):
        """Initialize conversion repository."""
        super().__init__(session, BookingConversion)
    
    # ==================== CONVERSION OPERATIONS ====================
    
    def create_conversion(
        self,
        conversion_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingConversion:
        """
        Create conversion record for a booking.
        
        Args:
            conversion_data: Conversion information
            audit_context: Audit context
            
        Returns:
            Created conversion record
            
        Raises:
            ValidationError: If conversion validation fails
        """
        booking_id = conversion_data.get('booking_id')
        
        # Validate booking exists and is in correct status
        booking = self.session.get(Booking, booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        if booking.booking_status != BookingStatus.CONFIRMED:
            raise ValidationError("Only confirmed bookings can be converted")
        
        # Validate no existing conversion
        existing = self.find_by_booking(booking_id)
        if existing:
            raise ValidationError(f"Booking {booking_id} already has a conversion record")
        
        conversion = BookingConversion(
            converted_by=audit_context.user_id if audit_context else None,
            converted_at=datetime.utcnow(),
            **conversion_data,
        )
        
        created = self.create(conversion, audit_context)
        
        # Create checklist
        self._create_default_checklist(created, audit_context)
        
        return created
    
    def _create_default_checklist(
        self,
        conversion: BookingConversion,
        audit_context: Optional[AuditContext] = None,
    ) -> ConversionChecklist:
        """Create default conversion checklist."""
        checklist_repo = ConversionChecklistRepository(self.session)
        
        checklist = checklist_repo.create_checklist(
            conversion_id=conversion.id,
            booking_id=conversion.booking_id,
            audit_context=audit_context,
        )
        
        # Add default checklist items
        default_items = [
            {
                "item_name": "Security Deposit Paid",
                "item_description": "Verify security deposit payment has been received",
                "item_category": "financial",
                "is_required": True,
                "item_order": 1,
            },
            {
                "item_name": "First Month Rent Paid",
                "item_description": "Verify first month's rent payment has been received",
                "item_category": "financial",
                "is_required": True,
                "item_order": 2,
            },
            {
                "item_name": "ID Proof Uploaded",
                "item_description": "Valid ID proof document uploaded and verified",
                "item_category": "documents",
                "is_required": True,
                "item_order": 3,
            },
            {
                "item_name": "Photo Uploaded",
                "item_description": "Student photo uploaded for records",
                "item_category": "documents",
                "is_required": True,
                "item_order": 4,
            },
            {
                "item_name": "Profile Information Complete",
                "item_description": "All required profile fields completed",
                "item_category": "profile",
                "is_required": True,
                "item_order": 5,
            },
            {
                "item_name": "Guardian Information Verified",
                "item_description": "Guardian contact information verified",
                "item_category": "verification",
                "is_required": True,
                "item_order": 6,
            },
            {
                "item_name": "Room Assignment Confirmed",
                "item_description": "Room and bed assignment confirmed",
                "item_category": "assignment",
                "is_required": True,
                "item_order": 7,
            },
        ]
        
        for item_data in default_items:
            checklist_repo.add_checklist_item(
                checklist.id,
                item_data,
                audit_context,
            )
        
        return checklist
    
    def find_by_booking(self, booking_id: UUID) -> Optional[BookingConversion]:
        """
        Find conversion record for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Conversion record if found
        """
        query = select(BookingConversion).where(
            BookingConversion.booking_id == booking_id
        ).where(
            BookingConversion.deleted_at.is_(None)
        ).options(
            joinedload(BookingConversion.booking),
            joinedload(BookingConversion.student_profile),
            joinedload(BookingConversion.converter),
            selectinload(BookingConversion.checklist).selectinload(
                ConversionChecklist.items
            ),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_by_student(self, student_id: UUID) -> Optional[BookingConversion]:
        """
        Find conversion record by student profile.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Conversion record if found
        """
        query = select(BookingConversion).where(
            BookingConversion.student_profile_id == student_id
        ).where(
            BookingConversion.deleted_at.is_(None)
        ).options(
            joinedload(BookingConversion.booking),
            joinedload(BookingConversion.student_profile),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def verify_documents(
        self,
        conversion_id: UUID,
        verified_by: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingConversion:
        """
        Mark documents as verified.
        
        Args:
            conversion_id: Conversion UUID
            verified_by: Admin UUID verifying documents
            audit_context: Audit context
            
        Returns:
            Updated conversion
        """
        conversion = self.find_by_id(conversion_id)
        if not conversion:
            raise EntityNotFoundError(f"Conversion {conversion_id} not found")
        
        conversion.verify_documents(verified_by)
        
        # Update checklist items
        if conversion.checklist:
            checklist_repo = ConversionChecklistRepository(self.session)
            
            if conversion.id_proof_uploaded:
                checklist_repo.complete_item_by_name(
                    conversion.checklist.id,
                    "ID Proof Uploaded",
                    verified_by,
                    "Document verified",
                )
            
            if conversion.photo_uploaded:
                checklist_repo.complete_item_by_name(
                    conversion.checklist.id,
                    "Photo Uploaded",
                    verified_by,
                    "Photo verified",
                )
        
        self.session.flush()
        self.session.refresh(conversion)
        
        return conversion
    
    def mark_payment_received(
        self,
        conversion_id: UUID,
        payment_type: str,
        payment_id: UUID,
        amount: Decimal,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingConversion:
        """
        Mark payment as received.
        
        Args:
            conversion_id: Conversion UUID
            payment_type: "security_deposit" or "first_month_rent"
            payment_id: Payment transaction UUID
            amount: Payment amount
            audit_context: Audit context
            
        Returns:
            Updated conversion
        """
        conversion = self.find_by_id(conversion_id)
        if not conversion:
            raise EntityNotFoundError(f"Conversion {conversion_id} not found")
        
        if payment_type == "security_deposit":
            conversion.security_deposit_paid = True
            conversion.security_deposit_amount = amount
            conversion.security_deposit_payment_id = payment_id
            
            # Update checklist
            if conversion.checklist:
                checklist_repo = ConversionChecklistRepository(self.session)
                checklist_repo.complete_item_by_name(
                    conversion.checklist.id,
                    "Security Deposit Paid",
                    audit_context.user_id if audit_context else None,
                    f"Payment received: {amount}",
                )
        
        elif payment_type == "first_month_rent":
            conversion.first_month_rent_paid = True
            conversion.first_month_rent_amount = amount
            conversion.first_month_rent_payment_id = payment_id
            
            # Update checklist
            if conversion.checklist:
                checklist_repo = ConversionChecklistRepository(self.session)
                checklist_repo.complete_item_by_name(
                    conversion.checklist.id,
                    "First Month Rent Paid",
                    audit_context.user_id if audit_context else None,
                    f"Payment received: {amount}",
                )
        
        else:
            raise ValidationError(f"Invalid payment type: {payment_type}")
        
        self.session.flush()
        self.session.refresh(conversion)
        
        return conversion
    
    def mark_as_failed(
        self,
        conversion_id: UUID,
        errors: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingConversion:
        """
        Mark conversion as failed.
        
        Args:
            conversion_id: Conversion UUID
            errors: Error details
            audit_context: Audit context
            
        Returns:
            Updated conversion
        """
        conversion = self.find_by_id(conversion_id)
        if not conversion:
            raise EntityNotFoundError(f"Conversion {conversion_id} not found")
        
        conversion.mark_as_failed(errors)
        
        self.session.flush()
        self.session.refresh(conversion)
        
        return conversion
    
    def find_pending_conversions(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingConversion]:
        """
        Find conversions that are pending completion.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of pending conversions
        """
        query = select(BookingConversion).join(
            Booking,
            BookingConversion.booking_id == Booking.id
        ).join(
            ConversionChecklist,
            BookingConversion.id == ConversionChecklist.conversion_id
        ).where(
            and_(
                BookingConversion.is_successful == True,
                ConversionChecklist.all_checks_passed == False,
                BookingConversion.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.options(
            joinedload(BookingConversion.booking),
            selectinload(BookingConversion.checklist).selectinload(
                ConversionChecklist.items
            ),
        ).order_by(BookingConversion.created_at.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_ready_for_conversion(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingConversion]:
        """
        Find conversions ready to complete (all checks passed).
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of ready conversions
        """
        query = select(BookingConversion).join(
            Booking,
            BookingConversion.booking_id == Booking.id
        ).join(
            ConversionChecklist,
            BookingConversion.id == ConversionChecklist.conversion_id
        ).where(
            and_(
                BookingConversion.is_successful == True,
                ConversionChecklist.can_convert == True,
                BookingConversion.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.options(
            joinedload(BookingConversion.booking),
            selectinload(BookingConversion.checklist),
        ).order_by(BookingConversion.created_at.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_conversion_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get conversion statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(BookingConversion).join(
            Booking,
            BookingConversion.booking_id == Booking.id
        ).where(
            BookingConversion.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingConversion.converted_at >= date_from)
        
        if date_to:
            query = query.where(BookingConversion.converted_at <= date_to)
        
        conversions = self.session.execute(query).scalars().all()
        
        total_conversions = len(conversions)
        successful = sum(1 for c in conversions if c.is_successful)
        failed = sum(1 for c in conversions if not c.is_successful)
        
        # Payment statistics
        security_deposit_paid = sum(1 for c in conversions if c.security_deposit_paid)
        first_month_paid = sum(1 for c in conversions if c.first_month_rent_paid)
        all_payments_received = sum(1 for c in conversions if c.all_payments_received)
        
        # Document statistics
        documents_uploaded = sum(1 for c in conversions if c.all_documents_uploaded)
        documents_verified = sum(1 for c in conversions if c.documents_verified)
        
        # Checklist statistics
        avg_completion_rate = (
            sum(c.checklist_completion_rate for c in conversions) / total_conversions
            if total_conversions > 0 else Decimal("0.00")
        )
        
        ready_for_completion = sum(
            1 for c in conversions
            if c.is_ready_for_conversion
        )
        
        # Average days since check-in
        avg_days_since_checkin = (
            sum(c.days_since_check_in for c in conversions) / total_conversions
            if total_conversions > 0 else 0
        )
        
        return {
            "total_conversions": total_conversions,
            "successful_conversions": successful,
            "failed_conversions": failed,
            "success_rate": (successful / total_conversions * 100) if total_conversions > 0 else 0,
            "security_deposit_paid_count": security_deposit_paid,
            "first_month_paid_count": first_month_paid,
            "all_payments_received_count": all_payments_received,
            "payment_completion_rate": (all_payments_received / total_conversions * 100) if total_conversions > 0 else 0,
            "documents_uploaded_count": documents_uploaded,
            "documents_verified_count": documents_verified,
            "document_verification_rate": (documents_verified / total_conversions * 100) if total_conversions > 0 else 0,
            "average_checklist_completion": avg_completion_rate,
            "ready_for_completion": ready_for_completion,
            "average_days_since_checkin": avg_days_since_checkin,
        }


class ConversionChecklistRepository(BaseRepository[ConversionChecklist]):
    """Repository for conversion checklist management."""
    
    def __init__(self, session: Session):
        """Initialize checklist repository."""
        super().__init__(session, ConversionChecklist)
    
    def create_checklist(
        self,
        conversion_id: UUID,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> ConversionChecklist:
        """
        Create conversion checklist.
        
        Args:
            conversion_id: Conversion UUID
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Created checklist
        """
        checklist = ConversionChecklist(
            conversion_id=conversion_id,
            booking_id=booking_id,
            last_checked_by=audit_context.user_id if audit_context else None,
        )
        
        return self.create(checklist, audit_context)
    
    def find_by_conversion(self, conversion_id: UUID) -> Optional[ConversionChecklist]:
        """
        Find checklist for a conversion.
        
        Args:
            conversion_id: Conversion UUID
            
        Returns:
            Checklist if found
        """
        query = select(ConversionChecklist).where(
            ConversionChecklist.conversion_id == conversion_id
        ).where(
            ConversionChecklist.deleted_at.is_(None)
        ).options(
            selectinload(ConversionChecklist.items),
            joinedload(ConversionChecklist.conversion),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_by_booking(self, booking_id: UUID) -> Optional[ConversionChecklist]:
        """
        Find checklist for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Checklist if found
        """
        query = select(ConversionChecklist).where(
            ConversionChecklist.booking_id == booking_id
        ).where(
            ConversionChecklist.deleted_at.is_(None)
        ).options(
            selectinload(ConversionChecklist.items),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def add_checklist_item(
        self,
        checklist_id: UUID,
        item_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> ChecklistItem:
        """
        Add item to checklist.
        
        Args:
            checklist_id: Checklist UUID
            item_data: Item data
            audit_context: Audit context
            
        Returns:
            Created item
        """
        item = ChecklistItem(
            checklist_id=checklist_id,
            **item_data,
        )
        
        self.session.add(item)
        self.session.flush()
        
        # Update checklist metrics
        self._update_checklist_metrics(checklist_id, audit_context)
        
        return item
    
    def complete_checklist_item(
        self,
        item_id: UUID,
        completed_by: UUID,
        notes: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> ChecklistItem:
        """
        Mark checklist item as completed.
        
        Args:
            item_id: Item UUID
            completed_by: User UUID completing the item
            notes: Optional notes
            audit_context: Audit context
            
        Returns:
            Updated item
        """
        item = self.session.get(ChecklistItem, item_id)
        if not item:
            raise EntityNotFoundError(f"Checklist item {item_id} not found")
        
        item.mark_completed(completed_by, notes)
        
        self.session.flush()
        
        # Update checklist metrics
        self._update_checklist_metrics(item.checklist_id, audit_context)
        
        return item
    
    def complete_item_by_name(
        self,
        checklist_id: UUID,
        item_name: str,
        completed_by: UUID,
        notes: Optional[str] = None,
    ) -> Optional[ChecklistItem]:
        """
        Complete checklist item by name.
        
        Args:
            checklist_id: Checklist UUID
            item_name: Item name
            completed_by: User completing the item
            notes: Optional notes
            
        Returns:
            Updated item if found
        """
        query = select(ChecklistItem).where(
            and_(
                ChecklistItem.checklist_id == checklist_id,
                ChecklistItem.item_name == item_name,
                ChecklistItem.deleted_at.is_(None),
            )
        )
        
        result = self.session.execute(query)
        item = result.scalar_one_or_none()
        
        if item and not item.is_completed:
            item.mark_completed(completed_by, notes)
            self.session.flush()
            self._update_checklist_metrics(checklist_id, None)
        
        return item
    
    def _update_checklist_metrics(
        self,
        checklist_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> None:
        """Update checklist completion metrics."""
        checklist = self.session.get(ConversionChecklist, checklist_id)
        if not checklist:
            return
        
        checklist.evaluate_checklist(
            checked_by=audit_context.user_id if audit_context else None
        )
        
        # Update conversion completion rate
        if checklist.conversion:
            checklist.conversion.update_checklist_completion(
                checklist.completion_percentage,
                checklist.all_checks_passed,
            )
        
        self.session.flush()
    
    def get_incomplete_items(
        self,
        checklist_id: UUID,
        required_only: bool = False,
    ) -> List[ChecklistItem]:
        """
        Get incomplete checklist items.
        
        Args:
            checklist_id: Checklist UUID
            required_only: If True, only return required items
            
        Returns:
            List of incomplete items
        """
        query = select(ChecklistItem).where(
            and_(
                ChecklistItem.checklist_id == checklist_id,
                ChecklistItem.is_completed == False,
                ChecklistItem.deleted_at.is_(None),
            )
        )
        
        if required_only:
            query = query.where(ChecklistItem.is_required == True)
        
        query = query.order_by(ChecklistItem.item_order.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())