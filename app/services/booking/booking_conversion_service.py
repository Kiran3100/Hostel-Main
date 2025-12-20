# app/services/booking/booking_conversion_service.py
"""
Booking conversion service for student conversion workflow management.

Handles conversion of confirmed bookings to student profiles with validation
checklists, document verification, and payment tracking.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from app.models.base.enums import BookingStatus
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_conversion_repository import (
    BookingConversionRepository,
    ConversionChecklistRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingConversionService:
    """
    Service for booking to student conversion management.
    
    Responsibilities:
    - Process booking to student conversions
    - Manage conversion checklists
    - Track document verification
    - Monitor payment completion
    - Generate conversion analytics
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        conversion_repo: Optional[BookingConversionRepository] = None,
        checklist_repo: Optional[ConversionChecklistRepository] = None,
    ):
        """Initialize conversion service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.conversion_repo = conversion_repo or BookingConversionRepository(session)
        self.checklist_repo = checklist_repo or ConversionChecklistRepository(session)
    
    # ==================== CONVERSION OPERATIONS ====================
    
    def initiate_conversion(
        self,
        booking_id: UUID,
        student_profile_id: UUID,
        actual_check_in_date: date,
        security_deposit_amount: Decimal,
        first_month_rent_amount: Decimal,
        monthly_rent_amount: Decimal,
        student_id_number: Optional[str] = None,
        guardian_address: Optional[str] = None,
        conversion_notes: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Initiate booking to student conversion.
        
        Args:
            booking_id: Booking UUID
            student_profile_id: Created student profile UUID
            actual_check_in_date: Actual check-in date
            security_deposit_amount: Security deposit paid
            first_month_rent_amount: First month rent paid
            monthly_rent_amount: Ongoing monthly rent
            student_id_number: Student ID number
            guardian_address: Guardian address
            conversion_notes: Conversion notes
            audit_context: Audit context
            
        Returns:
            Conversion record dictionary
            
        Raises:
            EntityNotFoundError: If booking not found
            BusinessRuleViolationError: If conversion not allowed
        """
        # Get booking
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Validate booking status
        if booking.booking_status != BookingStatus.CONFIRMED:
            raise BusinessRuleViolationError(
                "Only confirmed bookings can be converted to student"
            )
        
        # Check for existing conversion
        existing = self.conversion_repo.find_by_booking(booking_id)
        if existing:
            raise BusinessRuleViolationError("Booking already has a conversion record")
        
        # Calculate next payment date (1 month from check-in)
        from datetime import timedelta
        next_payment_due = actual_check_in_date + timedelta(days=30)
        
        # Create conversion record
        conversion_data = {
            "booking_id": booking_id,
            "student_profile_id": student_profile_id,
            "actual_check_in_date": actual_check_in_date,
            "security_deposit_amount": security_deposit_amount,
            "first_month_rent_amount": first_month_rent_amount,
            "monthly_rent_amount": monthly_rent_amount,
            "student_id_number": student_id_number,
            "guardian_address": guardian_address,
            "conversion_notes": conversion_notes,
            "next_payment_due_date": next_payment_due,
        }
        
        conversion = self.conversion_repo.create_conversion(
            conversion_data, audit_context
        )
        
        # Update booking status to checked-in
        self.booking_repo.mark_as_checked_in(booking_id, audit_context)
        
        return self._conversion_to_dict(conversion, include_checklist=True)
    
    def mark_payment_received(
        self,
        conversion_id: UUID,
        payment_type: str,
        payment_id: UUID,
        amount: Decimal,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark payment as received for conversion.
        
        Args:
            conversion_id: Conversion UUID
            payment_type: "security_deposit" or "first_month_rent"
            payment_id: Payment transaction UUID
            amount: Payment amount
            audit_context: Audit context
            
        Returns:
            Updated conversion dictionary
        """
        conversion = self.conversion_repo.mark_payment_received(
            conversion_id, payment_type, payment_id, amount, audit_context
        )
        
        # Update checklist
        checklist = self.checklist_repo.find_by_conversion(conversion_id)
        if checklist:
            self.checklist_repo._update_checklist_metrics(checklist.id, audit_context)
        
        return self._conversion_to_dict(conversion)
    
    def verify_documents(
        self,
        conversion_id: UUID,
        verified_by_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark documents as verified for conversion.
        
        Args:
            conversion_id: Conversion UUID
            verified_by_id: Admin UUID
            audit_context: Audit context
            
        Returns:
            Updated conversion dictionary
        """
        conversion = self.conversion_repo.verify_documents(
            conversion_id, verified_by_id, audit_context
        )
        
        return self._conversion_to_dict(conversion)
    
    def mark_conversion_failed(
        self,
        conversion_id: UUID,
        errors: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark conversion as failed.
        
        Args:
            conversion_id: Conversion UUID
            errors: Error details
            audit_context: Audit context
            
        Returns:
            Updated conversion dictionary
        """
        conversion = self.conversion_repo.mark_as_failed(
            conversion_id, errors, audit_context
        )
        
        return self._conversion_to_dict(conversion)
    
    # ==================== CHECKLIST MANAGEMENT ====================
    
    def get_conversion_checklist(
        self,
        conversion_id: UUID,
    ) -> Dict:
        """
        Get conversion checklist with all items.
        
        Args:
            conversion_id: Conversion UUID
            
        Returns:
            Checklist dictionary with items
        """
        checklist = self.checklist_repo.find_by_conversion(conversion_id)
        if not checklist:
            raise EntityNotFoundError(f"Checklist for conversion {conversion_id} not found")
        
        return self._checklist_to_dict(checklist)
    
    def add_checklist_item(
        self,
        conversion_id: UUID,
        item_name: str,
        item_description: str,
        is_required: bool = True,
        item_category: str = "general",
        item_order: int = 0,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Add item to conversion checklist.
        
        Args:
            conversion_id: Conversion UUID
            item_name: Item name
            item_description: Item description
            is_required: Whether item is mandatory
            item_category: Item category
            item_order: Display order
            audit_context: Audit context
            
        Returns:
            Created item dictionary
        """
        checklist = self.checklist_repo.find_by_conversion(conversion_id)
        if not checklist:
            raise EntityNotFoundError(f"Checklist for conversion {conversion_id} not found")
        
        item_data = {
            "item_name": item_name,
            "item_description": item_description,
            "is_required": is_required,
            "item_category": item_category,
            "item_order": item_order,
        }
        
        item = self.checklist_repo.add_checklist_item(
            checklist.id, item_data, audit_context
        )
        
        return self._checklist_item_to_dict(item)
    
    def complete_checklist_item(
        self,
        item_id: UUID,
        completed_by_id: UUID,
        verification_notes: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark checklist item as completed.
        
        Args:
            item_id: Item UUID
            completed_by_id: User UUID completing item
            verification_notes: Verification notes
            audit_context: Audit context
            
        Returns:
            Updated item dictionary
        """
        item = self.checklist_repo.complete_checklist_item(
            item_id, completed_by_id, verification_notes, audit_context
        )
        
        return self._checklist_item_to_dict(item)
    
    def get_incomplete_checklist_items(
        self,
        conversion_id: UUID,
        required_only: bool = False,
    ) -> List[Dict]:
        """
        Get incomplete checklist items.
        
        Args:
            conversion_id: Conversion UUID
            required_only: Only required items
            
        Returns:
            List of incomplete item dictionaries
        """
        checklist = self.checklist_repo.find_by_conversion(conversion_id)
        if not checklist:
            return []
        
        items = self.checklist_repo.get_incomplete_items(checklist.id, required_only)
        return [self._checklist_item_to_dict(item) for item in items]
    
    # ==================== CONVERSION QUERIES ====================
    
    def get_conversion_by_booking(
        self,
        booking_id: UUID,
        include_checklist: bool = True,
    ) -> Optional[Dict]:
        """
        Get conversion record for a booking.
        
        Args:
            booking_id: Booking UUID
            include_checklist: Include checklist data
            
        Returns:
            Conversion dictionary or None
        """
        conversion = self.conversion_repo.find_by_booking(booking_id)
        if not conversion:
            return None
        
        return self._conversion_to_dict(conversion, include_checklist)
    
    def get_conversion_by_student(
        self,
        student_id: UUID,
    ) -> Optional[Dict]:
        """
        Get conversion record by student profile.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Conversion dictionary or None
        """
        conversion = self.conversion_repo.find_by_student(student_id)
        if not conversion:
            return None
        
        return self._conversion_to_dict(conversion)
    
    def get_pending_conversions(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get conversions pending completion.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of pending conversion dictionaries
        """
        conversions = self.conversion_repo.find_pending_conversions(hostel_id)
        return [self._conversion_to_dict(c, include_checklist=True) for c in conversions]
    
    def get_ready_for_conversion(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get conversions ready to complete (all checks passed).
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of ready conversion dictionaries
        """
        conversions = self.conversion_repo.find_ready_for_conversion(hostel_id)
        return [self._conversion_to_dict(c) for c in conversions]
    
    # ==================== ANALYTICS ====================
    
    def get_conversion_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """
        Get conversion statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        return self.conversion_repo.get_conversion_statistics(
            hostel_id, date_from, date_to
        )
    
    # ==================== HELPER METHODS ====================
    
    def _conversion_to_dict(
        self,
        conversion,
        include_checklist: bool = False,
    ) -> Dict:
        """Convert conversion model to dictionary."""
        result = {
            "id": str(conversion.id),
            "booking_id": str(conversion.booking_id),
            "student_profile_id": str(conversion.student_profile_id),
            "actual_check_in_date": conversion.actual_check_in_date.isoformat(),
            "security_deposit_paid": conversion.security_deposit_paid,
            "security_deposit_amount": float(conversion.security_deposit_amount),
            "first_month_rent_paid": conversion.first_month_rent_paid,
            "first_month_rent_amount": float(conversion.first_month_rent_amount),
            "monthly_rent_amount": float(conversion.monthly_rent_amount),
            "student_id_number": conversion.student_id_number,
            "guardian_address": conversion.guardian_address,
            "id_proof_uploaded": conversion.id_proof_uploaded,
            "photo_uploaded": conversion.photo_uploaded,
            "documents_verified": conversion.documents_verified,
            "conversion_notes": conversion.conversion_notes,
            "converted_by": (
                str(conversion.converted_by) if conversion.converted_by else None
            ),
            "converted_at": conversion.converted_at.isoformat(),
            "checklist_completed": conversion.checklist_completed,
            "checklist_completion_rate": float(conversion.checklist_completion_rate),
            "next_payment_due_date": conversion.next_payment_due_date.isoformat(),
            "is_successful": conversion.is_successful,
            "conversion_errors": conversion.conversion_errors,
            # Computed properties
            "days_since_check_in": conversion.days_since_check_in,
            "all_payments_received": conversion.all_payments_received,
            "all_documents_uploaded": conversion.all_documents_uploaded,
            "is_ready_for_conversion": conversion.is_ready_for_conversion,
        }
        
        if include_checklist and conversion.checklist:
            result["checklist"] = self._checklist_to_dict(conversion.checklist)
        
        return result
    
    def _checklist_to_dict(self, checklist) -> Dict:
        """Convert checklist model to dictionary."""
        return {
            "id": str(checklist.id),
            "conversion_id": str(checklist.conversion_id),
            "booking_id": str(checklist.booking_id),
            "all_checks_passed": checklist.all_checks_passed,
            "can_convert": checklist.can_convert,
            "total_items": checklist.total_items,
            "completed_items": checklist.completed_items,
            "required_items": checklist.required_items,
            "missing_items": checklist.missing_items,
            "completion_percentage": float(checklist.completion_percentage),
            "required_completion_percentage": float(
                checklist.required_completion_percentage
            ),
            "items": [self._checklist_item_to_dict(item) for item in checklist.items],
        }
    
    def _checklist_item_to_dict(self, item) -> Dict:
        """Convert checklist item to dictionary."""
        return {
            "id": str(item.id),
            "checklist_id": str(item.checklist_id),
            "item_name": item.item_name,
            "item_description": item.item_description,
            "is_completed": item.is_completed,
            "is_required": item.is_required,
            "item_order": item.item_order,
            "item_category": item.item_category,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "completed_by": str(item.completed_by) if item.completed_by else None,
            "verification_notes": item.verification_notes,
        }