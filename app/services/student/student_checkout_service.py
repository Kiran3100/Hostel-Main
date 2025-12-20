"""
Student checkout service.

Comprehensive checkout workflow including clearances, refunds,
final settlements, and exit formalities.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.student.student_service import StudentService
from app.services.student.room_transfer_service import RoomTransferService
from app.models.student.student import Student
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleViolationError
)


class StudentCheckoutService:
    """
    Student checkout service for complete exit workflow.
    
    Handles:
        - Notice period management
        - Clearance tracking
        - Room handover
        - Financial settlement
        - Security deposit refund
        - Exit documentation
        - Final clearance
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.student_service = StudentService(db)
        self.transfer_service = RoomTransferService(db)

    # ============================================================================
    # CHECKOUT INITIATION
    # ============================================================================

    def initiate_checkout(
        self,
        student_id: str,
        expected_checkout_date: date,
        reason: str,
        notice_period_days: int = 30,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Initiate student checkout process.
        
        Args:
            student_id: Student UUID
            expected_checkout_date: Expected checkout date
            reason: Checkout reason
            notice_period_days: Notice period in days
            audit_context: Audit context
            
        Returns:
            Dictionary with checkout details
            
        Raises:
            NotFoundError: If student not found
            ValidationError: If validation fails
            BusinessRuleViolationError: If checkout not allowed
        """
        try:
            # Validate student
            student = self.student_service.get_student_by_id(student_id)
            
            # Validate checkout eligibility
            if student.student_status not in ['active', 'notice_period']:
                raise BusinessRuleViolationError(
                    f"Cannot initiate checkout for student with status: {student.student_status}"
                )
            
            if not student.check_in_date:
                raise BusinessRuleViolationError(
                    "Student was never checked in"
                )
            
            if student.actual_checkout_date:
                raise BusinessRuleViolationError(
                    "Student is already checked out"
                )
            
            # Validate reason
            if not reason or len(reason.strip()) < 10:
                raise ValidationError(
                    "Checkout reason must be at least 10 characters"
                )
            
            # Initiate notice period
            student = self.student_service.initiate_checkout(
                student_id,
                expected_checkout_date,
                audit_context
            )
            
            # Create checkout record
            checkout_record = {
                'student_id': student_id,
                'initiated_date': date.today(),
                'expected_checkout_date': expected_checkout_date,
                'notice_period_days': notice_period_days,
                'reason': reason,
                'status': 'initiated',
                'clearances': self._initialize_clearances(),
                'financial_summary': self._get_financial_summary(student_id)
            }
            
            self.db.commit()
            
            return checkout_record
            
        except (NotFoundError, ValidationError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _initialize_clearances(self) -> dict[str, dict[str, Any]]:
        """
        Initialize checkout clearance checklist.
        
        Returns:
            Dictionary with clearance items
        """
        return {
            'room_handover': {
                'required': True,
                'complete': False,
                'notes': None,
                'completed_by': None,
                'completed_at': None
            },
            'library_clearance': {
                'required': True,
                'complete': False,
                'notes': None,
                'completed_by': None,
                'completed_at': None
            },
            'financial_clearance': {
                'required': True,
                'complete': False,
                'pending_amount': Decimal('0.00'),
                'notes': None,
                'completed_by': None,
                'completed_at': None
            },
            'mess_clearance': {
                'required': True,
                'complete': False,
                'notes': None,
                'completed_by': None,
                'completed_at': None
            },
            'hostel_property': {
                'required': True,
                'complete': False,
                'notes': None,
                'completed_by': None,
                'completed_at': None
            },
            'complaint_resolution': {
                'required': False,
                'complete': False,
                'pending_complaints': 0,
                'notes': None,
                'completed_by': None,
                'completed_at': None
            }
        }

    # ============================================================================
    # CLEARANCE MANAGEMENT
    # ============================================================================

    def mark_clearance_complete(
        self,
        student_id: str,
        clearance_type: str,
        completed_by: str,
        notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Mark a clearance item as complete.
        
        Args:
            student_id: Student UUID
            clearance_type: Type of clearance
            completed_by: Admin user ID who verified
            notes: Clearance notes
            audit_context: Audit context
            
        Returns:
            Updated clearance status
        """
        valid_clearances = [
            'room_handover',
            'library_clearance',
            'financial_clearance',
            'mess_clearance',
            'hostel_property',
            'complaint_resolution'
        ]
        
        if clearance_type not in valid_clearances:
            raise ValidationError(f"Invalid clearance type: {clearance_type}")
        
        # In a real implementation, this would update a checkout record table
        # For now, we'll return the clearance status
        clearance_status = {
            'clearance_type': clearance_type,
            'complete': True,
            'completed_by': completed_by,
            'completed_at': datetime.utcnow(),
            'notes': notes
        }
        
        return clearance_status

    def get_clearance_status(
        self,
        student_id: str
    ) -> dict[str, Any]:
        """
        Get comprehensive clearance status.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Dictionary with clearance details
        """
        student = self.student_service.get_student_by_id(student_id)
        
        clearances = self._initialize_clearances()
        
        # Check financial clearance
        financial_summary = self._get_financial_summary(student_id)
        if financial_summary['pending_amount'] == 0:
            clearances['financial_clearance']['complete'] = True
        else:
            clearances['financial_clearance']['pending_amount'] = financial_summary['pending_amount']
        
        # Calculate overall status
        required_clearances = [
            key for key, value in clearances.items()
            if value.get('required', False)
        ]
        
        completed_clearances = [
            key for key in required_clearances
            if clearances[key].get('complete', False)
        ]
        
        all_clear = len(completed_clearances) == len(required_clearances)
        
        return {
            'student_id': student_id,
            'clearances': clearances,
            'required_count': len(required_clearances),
            'completed_count': len(completed_clearances),
            'all_clear': all_clear,
            'can_checkout': all_clear
        }

    # ============================================================================
    # ROOM HANDOVER
    # ============================================================================

    def process_room_handover(
        self,
        student_id: str,
        room_condition: str,
        damages_found: Optional[str] = None,
        damage_charges: Decimal = Decimal('0.00'),
        photos: Optional[list[str]] = None,
        inspected_by: str = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Process room handover inspection.
        
        Args:
            student_id: Student UUID
            room_condition: Room condition description
            damages_found: Description of any damages
            damage_charges: Charges for damages
            photos: List of photo URLs
            inspected_by: Admin user ID who inspected
            audit_context: Audit context
            
        Returns:
            Room handover details
        """
        try:
            student = self.student_service.get_student_by_id(student_id)
            
            if not student.room_id:
                raise BusinessRuleViolationError("Student has no room assigned")
            
            # Get current room assignment
            current_assignment = self.transfer_service.get_current_assignment(student_id)
            
            handover_record = {
                'student_id': student_id,
                'room_id': student.room_id,
                'bed_id': student.bed_id,
                'room_condition': room_condition,
                'damages_found': damages_found,
                'damage_charges': damage_charges,
                'photos': photos or [],
                'inspected_by': inspected_by,
                'inspected_at': datetime.utcnow(),
                'handover_complete': True
            }
            
            # Update current assignment with handover details
            if current_assignment:
                self.transfer_service.transfer_repo.update(
                    current_assignment.id,
                    {
                        'previous_room_condition': room_condition,
                        'previous_room_damages': damages_found,
                        'damage_charges': damage_charges,
                        'handover_photos': ','.join(photos) if photos else None,
                        'handover_completed': True
                    },
                    audit_context
                )
            
            self.db.commit()
            
            return handover_record
            
        except (NotFoundError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # FINANCIAL SETTLEMENT
    # ============================================================================

    def _get_financial_summary(
        self,
        student_id: str
    ) -> dict[str, Any]:
        """
        Get financial summary for checkout.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Financial summary
        """
        student = self.student_service.get_student_by_id(student_id)
        
        # Calculate pending amounts
        # In real implementation, this would query payment records
        pending_rent = Decimal('0.00')
        pending_mess = Decimal('0.00')
        pending_utilities = Decimal('0.00')
        pending_damages = Decimal('0.00')
        
        # Get damage charges from room transfers
        total_damage_charges = self.transfer_service.transfer_repo.calculate_total_damage_charges(
            student_id
        )
        pending_damages = total_damage_charges
        
        total_pending = (
            pending_rent +
            pending_mess +
            pending_utilities +
            pending_damages
        )
        
        # Calculate refundable amount
        security_deposit = student.security_deposit_amount
        refundable_amount = security_deposit - total_pending
        
        if refundable_amount < 0:
            additional_due = abs(refundable_amount)
            refundable_amount = Decimal('0.00')
        else:
            additional_due = Decimal('0.00')
        
        return {
            'security_deposit': security_deposit,
            'pending_rent': pending_rent,
            'pending_mess': pending_mess,
            'pending_utilities': pending_utilities,
            'pending_damages': pending_damages,
            'total_pending': total_pending,
            'additional_due': additional_due,
            'refundable_amount': refundable_amount,
            'financial_clear': total_pending == 0
        }

    def calculate_final_settlement(
        self,
        student_id: str,
        additional_charges: Optional[dict[str, Decimal]] = None,
        waived_charges: Optional[dict[str, Decimal]] = None
    ) -> dict[str, Any]:
        """
        Calculate final financial settlement.
        
        Args:
            student_id: Student UUID
            additional_charges: Additional charges to add
            waived_charges: Charges to waive
            
        Returns:
            Final settlement details
        """
        summary = self._get_financial_summary(student_id)
        
        # Add additional charges
        if additional_charges:
            for charge_type, amount in additional_charges.items():
                summary['total_pending'] += amount
                summary[f'additional_{charge_type}'] = amount
        
        # Apply waivers
        if waived_charges:
            total_waived = sum(waived_charges.values())
            summary['total_pending'] -= total_waived
            summary['total_waived'] = total_waived
            summary['waived_charges'] = waived_charges
        
        # Recalculate refundable amount
        security_deposit = summary['security_deposit']
        total_pending = summary['total_pending']
        
        if total_pending > security_deposit:
            summary['refundable_amount'] = Decimal('0.00')
            summary['additional_due'] = total_pending - security_deposit
        else:
            summary['refundable_amount'] = security_deposit - total_pending
            summary['additional_due'] = Decimal('0.00')
        
        summary['settlement_complete'] = summary['additional_due'] == 0
        
        return summary

    def process_security_deposit_refund(
        self,
        student_id: str,
        refund_amount: Decimal,
        deductions: Optional[dict[str, Decimal]] = None,
        refund_mode: str = 'bank_transfer',
        refund_reference: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Process security deposit refund.
        
        Args:
            student_id: Student UUID
            refund_amount: Amount to refund
            deductions: Deduction breakdown
            refund_mode: Refund mode (bank_transfer, check, cash)
            refund_reference: Refund transaction reference
            audit_context: Audit context
            
        Returns:
            Refund details
        """
        try:
            student = self.student_service.process_security_deposit_refund(
                student_id,
                refund_amount,
                deductions,
                audit_context=audit_context
            )
            
            refund_record = {
                'student_id': student_id,
                'original_deposit': student.security_deposit_amount,
                'refund_amount': refund_amount,
                'deductions': deductions or {},
                'total_deductions': sum(deductions.values()) if deductions else Decimal('0.00'),
                'refund_mode': refund_mode,
                'refund_reference': refund_reference,
                'refund_date': student.security_deposit_refund_date,
                'processed_at': datetime.utcnow()
            }
            
            self.db.commit()
            
            return refund_record
            
        except Exception as e:
            self.db.rollback()
            raise ValidationError(f"Refund processing failed: {str(e)}")

    # ============================================================================
    # FINAL CHECKOUT
    # ============================================================================

    def complete_checkout(
        self,
        student_id: str,
        checkout_date: Optional[date] = None,
        checkout_notes: Optional[str] = None,
        forwarding_address: Optional[str] = None,
        final_feedback: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Complete student checkout process.
        
        Args:
            student_id: Student UUID
            checkout_date: Checkout date
            checkout_notes: Final checkout notes
            forwarding_address: Student's forwarding address
            final_feedback: Student feedback
            audit_context: Audit context
            
        Returns:
            Checkout completion details
            
        Raises:
            BusinessRuleViolationError: If clearances not complete
        """
        try:
            # Validate all clearances are complete
            clearance_status = self.get_clearance_status(student_id)
            
            if not clearance_status['all_clear']:
                pending = [
                    key for key, value in clearance_status['clearances'].items()
                    if value.get('required') and not value.get('complete')
                ]
                raise BusinessRuleViolationError(
                    f"Cannot complete checkout. Pending clearances: {', '.join(pending)}"
                )
            
            # Update student record
            update_data = {
                'forwarding_address': forwarding_address,
                'all_clearances_received': True
            }
            
            self.student_service.update_student(
                student_id,
                update_data,
                audit_context
            )
            
            # Complete checkout
            student = self.student_service.complete_checkout(
                student_id,
                checkout_date,
                checkout_notes,
                audit_context
            )
            
            checkout_summary = {
                'student_id': student_id,
                'checkout_date': student.actual_checkout_date,
                'check_in_date': student.check_in_date,
                'total_stay_days': (
                    student.actual_checkout_date - student.check_in_date
                ).days if student.check_in_date else 0,
                'clearances': clearance_status,
                'financial_summary': self._get_financial_summary(student_id),
                'forwarding_address': forwarding_address,
                'final_feedback': final_feedback,
                'checkout_complete': True,
                'completed_at': datetime.utcnow()
            }
            
            self.db.commit()
            
            return checkout_summary
            
        except BusinessRuleViolationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # CHECKOUT ANALYTICS
    # ============================================================================

    def get_checkout_summary(
        self,
        student_id: str
    ) -> dict[str, Any]:
        """
        Get comprehensive checkout summary.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Complete checkout summary
        """
        student = self.student_service.get_student_by_id(student_id)
        
        return {
            'student': {
                'id': student.id,
                'status': student.student_status.value,
                'check_in_date': student.check_in_date,
                'expected_checkout_date': student.expected_checkout_date,
                'actual_checkout_date': student.actual_checkout_date,
                'notice_period_start': student.notice_period_start,
                'notice_period_end': student.notice_period_end
            },
            'clearances': self.get_clearance_status(student_id),
            'financial': self._get_financial_summary(student_id),
            'room_handover': {
                'room_id': student.room_id,
                'bed_id': student.bed_id,
                'handover_complete': False  # Would check actual handover record
            },
            'can_proceed': self.get_clearance_status(student_id)['all_clear']
        }

    def get_pending_checkouts(
        self,
        hostel_id: Optional[str] = None,
        days_threshold: int = 7
    ) -> list[dict[str, Any]]:
        """
        Get students with pending checkout.
        
        Args:
            hostel_id: Optional hostel filter
            days_threshold: Days until expected checkout
            
        Returns:
            List of students pending checkout
        """
        students = self.student_service.student_repo.find_pending_checkout(
            hostel_id,
            days_threshold
        )
        
        return [
            {
                'student_id': student.id,
                'expected_checkout_date': student.expected_checkout_date,
                'days_remaining': (
                    student.expected_checkout_date - date.today()
                ).days if student.expected_checkout_date else None,
                'clearance_status': self.get_clearance_status(student.id)
            }
            for student in students
        ]