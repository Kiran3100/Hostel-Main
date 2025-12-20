"""
Student service.

Core student lifecycle management orchestrating business logic,
validation, and cross-entity operations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.student_repository import StudentRepository
from app.repositories.student.student_profile_repository import StudentProfileRepository
from app.repositories.student.student_preferences_repository import StudentPreferencesRepository
from app.repositories.student.guardian_contact_repository import GuardianContactRepository
from app.repositories.student.room_transfer_history_repository import RoomTransferHistoryRepository
from app.models.student.student import Student
from app.models.base.enums import StudentStatus
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleViolationError,
    ConflictError
)


class StudentService:
    """
    Student service for core lifecycle management.
    
    Handles:
        - Student creation and registration
        - Check-in and check-out processes
        - Status management and transitions
        - Verification workflows
        - Financial tracking
        - Data validation and business rules
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.student_repo = StudentRepository(db)
        self.profile_repo = StudentProfileRepository(db)
        self.preferences_repo = StudentPreferencesRepository(db)
        self.guardian_repo = GuardianContactRepository(db)
        self.transfer_repo = RoomTransferHistoryRepository(db)

    # ============================================================================
    # STUDENT CREATION AND REGISTRATION
    # ============================================================================

    def create_student(
        self,
        user_id: str,
        hostel_id: str,
        student_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Create new student with validation.
        
        Args:
            user_id: User UUID
            hostel_id: Hostel UUID
            student_data: Student information
            audit_context: Audit context
            
        Returns:
            Created student instance
            
        Raises:
            ValidationError: If validation fails
            ConflictError: If student already exists for user
        """
        try:
            # Validate user doesn't already have student record
            if self.student_repo.exists_by_user_id(user_id):
                raise ConflictError(
                    f"Student record already exists for user {user_id}"
                )
            
            # Validate student ID number if provided
            if student_id_number := student_data.get('student_id_number'):
                if self.student_repo.exists_by_student_id_number(student_id_number):
                    raise ConflictError(
                        f"Student ID number {student_id_number} already exists"
                    )
            
            # Set required fields
            student_data['user_id'] = user_id
            student_data['hostel_id'] = hostel_id
            student_data['student_status'] = StudentStatus.PENDING
            
            # Create student
            student = self.student_repo.create(student_data, audit_context)
            
            # Create associated profile
            self._create_default_profile(student.id, audit_context)
            
            # Create default preferences
            self._create_default_preferences(student.id, audit_context)
            
            self.db.commit()
            
            return student
            
        except (ValidationError, ConflictError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _create_default_profile(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> None:
        """Create default student profile."""
        profile_data = {
            'student_id': student_id,
            'profile_completeness': 0
        }
        self.profile_repo.create(profile_data, audit_context)

    def _create_default_preferences(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> None:
        """Create default student preferences."""
        preferences_data = {
            'student_id': student_id
        }
        self.preferences_repo.create(preferences_data, audit_context)

    # ============================================================================
    # STUDENT RETRIEVAL
    # ============================================================================

    def get_student_by_id(
        self,
        student_id: str,
        include_relations: bool = False
    ) -> Student:
        """
        Get student by ID.
        
        Args:
            student_id: Student UUID
            include_relations: Load related entities
            
        Returns:
            Student instance
            
        Raises:
            NotFoundError: If student not found
        """
        student = self.student_repo.find_by_id(
            student_id,
            eager_load=include_relations
        )
        
        if not student:
            raise NotFoundError(f"Student {student_id} not found")
        
        return student

    def get_student_by_user_id(self, user_id: str) -> Student:
        """
        Get student by user ID.
        
        Args:
            user_id: User UUID
            
        Returns:
            Student instance
            
        Raises:
            NotFoundError: If student not found
        """
        student = self.student_repo.find_by_user_id(user_id)
        
        if not student:
            raise NotFoundError(f"No student found for user {user_id}")
        
        return student

    def get_students_by_hostel(
        self,
        hostel_id: str,
        status: Optional[StudentStatus] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[Student]:
        """
        Get students by hostel with optional status filter.
        
        Args:
            hostel_id: Hostel UUID
            status: Optional status filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of students
        """
        return self.student_repo.find_by_hostel(
            hostel_id,
            status=status,
            offset=offset,
            limit=limit
        )

    def search_students(
        self,
        search_term: str,
        hostel_id: Optional[str] = None,
        status: Optional[StudentStatus] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[Student]:
        """
        Search students by multiple criteria.
        
        Args:
            search_term: Search term
            hostel_id: Optional hostel filter
            status: Optional status filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of matching students
        """
        return self.student_repo.search_students(
            search_term,
            hostel_id=hostel_id,
            status=status,
            offset=offset,
            limit=limit
        )

    # ============================================================================
    # STUDENT UPDATE
    # ============================================================================

    def update_student(
        self,
        student_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Update student information.
        
        Args:
            student_id: Student UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated student instance
            
        Raises:
            NotFoundError: If student not found
            ValidationError: If validation fails
        """
        try:
            # Validate student ID number if being updated
            if 'student_id_number' in update_data:
                student_id_number = update_data['student_id_number']
                if self.student_repo.exists_by_student_id_number(
                    student_id_number,
                    exclude_id=student_id
                ):
                    raise ConflictError(
                        f"Student ID number {student_id_number} already exists"
                    )
            
            student = self.student_repo.update(
                student_id,
                update_data,
                audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except (ValidationError, ConflictError, NotFoundError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # CHECK-IN PROCESS
    # ============================================================================

    def check_in_student(
        self,
        student_id: str,
        room_id: str,
        bed_id: Optional[str] = None,
        check_in_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Process student check-in with validation.
        
        Args:
            student_id: Student UUID
            room_id: Room UUID
            bed_id: Bed UUID (optional)
            check_in_date: Check-in date
            audit_context: Audit context
            
        Returns:
            Updated student instance
            
        Raises:
            NotFoundError: If student not found
            BusinessRuleViolationError: If check-in not allowed
        """
        try:
            # Validate check-in eligibility
            can_check_in, reason = self.student_repo.can_check_in(student_id)
            if not can_check_in:
                raise BusinessRuleViolationError(
                    f"Cannot check in student: {reason}"
                )
            
            # Perform check-in
            student = self.student_repo.check_in_student(
                student_id,
                room_id,
                bed_id=bed_id,
                check_in_date=check_in_date,
                audit_context=audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Create initial room assignment record
            self._create_initial_room_assignment(
                student,
                room_id,
                bed_id,
                check_in_date or date.today(),
                audit_context
            )
            
            self.db.commit()
            
            return student
            
        except (NotFoundError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _create_initial_room_assignment(
        self,
        student: Student,
        room_id: str,
        bed_id: Optional[str],
        check_in_date: date,
        audit_context: Optional[dict[str, Any]] = None
    ) -> None:
        """Create initial room assignment record."""
        transfer_data = {
            'student_id': student.id,
            'hostel_id': student.hostel_id,
            'to_room_id': room_id,
            'to_bed_id': bed_id,
            'transfer_type': 'initial',
            'transfer_date': check_in_date,
            'move_in_date': check_in_date,
            'reason': 'Initial room assignment during check-in',
            'student_initiated': False,
            'requires_approval': False,
            'approval_status': 'approved',
            'transfer_status': 'completed',
            'is_current_assignment': True,
            'completion_date': check_in_date
        }
        
        self.transfer_repo.create(transfer_data, audit_context)

    # ============================================================================
    # CHECK-OUT PROCESS
    # ============================================================================

    def initiate_checkout(
        self,
        student_id: str,
        expected_checkout_date: date,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Initiate checkout process (notice period).
        
        Args:
            student_id: Student UUID
            expected_checkout_date: Expected checkout date
            audit_context: Audit context
            
        Returns:
            Updated student instance
            
        Raises:
            NotFoundError: If student not found
            ValidationError: If validation fails
        """
        try:
            student = self.get_student_by_id(student_id)
            
            # Calculate notice period days
            notice_days = (expected_checkout_date - date.today()).days
            
            if notice_days < 0:
                raise ValidationError(
                    "Expected checkout date cannot be in the past"
                )
            
            # Initiate notice period
            student = self.student_repo.initiate_notice_period(
                student_id,
                notice_days,
                audit_context
            )
            
            self.db.commit()
            
            return student
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def complete_checkout(
        self,
        student_id: str,
        checkout_date: Optional[date] = None,
        checkout_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Complete student checkout.
        
        Args:
            student_id: Student UUID
            checkout_date: Checkout date
            checkout_notes: Checkout notes
            audit_context: Audit context
            
        Returns:
            Updated student instance
            
        Raises:
            NotFoundError: If student not found
            BusinessRuleViolationError: If checkout not allowed
        """
        try:
            # Validate checkout eligibility
            can_check_out, reason = self.student_repo.can_check_out(student_id)
            if not can_check_out:
                raise BusinessRuleViolationError(
                    f"Cannot check out student: {reason}"
                )
            
            # Perform checkout
            student = self.student_repo.check_out_student(
                student_id,
                checkout_date=checkout_date,
                checkout_notes=checkout_notes,
                audit_context=audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Update current room assignment
            self._close_current_room_assignment(
                student_id,
                checkout_date or date.today()
            )
            
            self.db.commit()
            
            return student
            
        except (NotFoundError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _close_current_room_assignment(
        self,
        student_id: str,
        checkout_date: date
    ) -> None:
        """Close current room assignment record."""
        current_assignment = self.transfer_repo.get_current_assignment(student_id)
        
        if current_assignment:
            self.transfer_repo.update(
                current_assignment.id,
                {
                    'move_out_date': checkout_date,
                    'is_current_assignment': False
                }
            )

    # ============================================================================
    # STATUS MANAGEMENT
    # ============================================================================

    def update_student_status(
        self,
        student_id: str,
        new_status: StudentStatus,
        reason: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Update student status with validation.
        
        Args:
            student_id: Student UUID
            new_status: New status
            reason: Reason for status change
            audit_context: Audit context
            
        Returns:
            Updated student instance
            
        Raises:
            NotFoundError: If student not found
            BusinessRuleViolationError: If status transition not allowed
        """
        try:
            student = self.get_student_by_id(student_id)
            
            # Validate status transition
            self._validate_status_transition(student.student_status, new_status)
            
            update_data = {'student_status': new_status}
            
            if reason:
                update_data['admin_notes'] = reason
            
            student = self.student_repo.update(
                student_id,
                update_data,
                audit_context
            )
            
            self.db.commit()
            
            return student
            
        except (NotFoundError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _validate_status_transition(
        self,
        current_status: StudentStatus,
        new_status: StudentStatus
    ) -> None:
        """
        Validate status transition is allowed.
        
        Args:
            current_status: Current status
            new_status: Desired new status
            
        Raises:
            BusinessRuleViolationError: If transition not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            StudentStatus.PENDING: [StudentStatus.ACTIVE, StudentStatus.REJECTED],
            StudentStatus.ACTIVE: [
                StudentStatus.NOTICE_PERIOD,
                StudentStatus.SUSPENDED,
                StudentStatus.CHECKED_OUT
            ],
            StudentStatus.NOTICE_PERIOD: [
                StudentStatus.ACTIVE,
                StudentStatus.CHECKED_OUT
            ],
            StudentStatus.SUSPENDED: [StudentStatus.ACTIVE, StudentStatus.TERMINATED],
            StudentStatus.CHECKED_OUT: [],  # Terminal state
            StudentStatus.REJECTED: [],  # Terminal state
            StudentStatus.TERMINATED: []  # Terminal state
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise BusinessRuleViolationError(
                f"Cannot transition from {current_status.value} to {new_status.value}"
            )

    def suspend_student(
        self,
        student_id: str,
        reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Suspend student with reason.
        
        Args:
            student_id: Student UUID
            reason: Suspension reason
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            student = self.student_repo.suspend_student(
                student_id,
                reason,
                audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def reactivate_student(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Reactivate suspended student.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            student = self.student_repo.reactivate_student(
                student_id,
                audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # VERIFICATION MANAGEMENT
    # ============================================================================

    def verify_id_proof(
        self,
        student_id: str,
        verified_by: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Verify student ID proof.
        
        Args:
            student_id: Student UUID
            verified_by: Admin user ID
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            student = self.student_repo.verify_id_proof(
                student_id,
                verified_by,
                audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def verify_institutional_id(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Verify student institutional ID.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            student = self.student_repo.verify_institutional_id(
                student_id,
                audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def verify_company_id(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Verify student company ID.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            student = self.student_repo.verify_company_id(
                student_id,
                audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # FINANCIAL OPERATIONS
    # ============================================================================

    def mark_security_deposit_paid(
        self,
        student_id: str,
        amount: Decimal,
        payment_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Mark security deposit as paid.
        
        Args:
            student_id: Student UUID
            amount: Deposit amount
            payment_date: Payment date
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            if amount <= 0:
                raise ValidationError("Deposit amount must be positive")
            
            student = self.student_repo.mark_security_deposit_paid(
                student_id,
                amount,
                payment_date=payment_date,
                audit_context=audit_context
            )
            
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return student
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def process_security_deposit_refund(
        self,
        student_id: str,
        refund_amount: Decimal,
        deductions: Optional[dict[str, Decimal]] = None,
        refund_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Process security deposit refund with deductions.
        
        Args:
            student_id: Student UUID
            refund_amount: Refund amount
            deductions: Optional deduction breakdown
            refund_date: Refund date
            audit_context: Audit context
            
        Returns:
            Updated student instance
        """
        try:
            student = self.get_student_by_id(student_id)
            
            # Validate refund amount
            if refund_amount < 0:
                raise ValidationError("Refund amount cannot be negative")
            
            if refund_amount > student.security_deposit_amount:
                raise ValidationError(
                    "Refund amount cannot exceed deposit amount"
                )
            
            student = self.student_repo.process_security_deposit_refund(
                student_id,
                refund_amount,
                refund_date=refund_date,
                audit_context=audit_context
            )
            
            self.db.commit()
            
            return student
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # STATISTICS AND ANALYTICS
    # ============================================================================

    def get_hostel_statistics(self, hostel_id: str) -> dict[str, Any]:
        """
        Get comprehensive hostel statistics.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with statistics
        """
        return self.student_repo.get_hostel_statistics(hostel_id)

    def get_status_breakdown(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get student count by status.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Status breakdown
        """
        return self.student_repo.get_status_breakdown(hostel_id)

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def bulk_update_status(
        self,
        student_ids: list[str],
        new_status: StudentStatus,
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk update student status.
        
        Args:
            student_ids: List of student UUIDs
            new_status: New status
            audit_context: Audit context
            
        Returns:
            Number of students updated
        """
        try:
            updated = self.student_repo.bulk_update_status(
                student_ids,
                new_status,
                audit_context
            )
            
            self.db.commit()
            
            return updated
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # DELETE OPERATIONS
    # ============================================================================

    def soft_delete_student(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Soft delete student.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Success status
        """
        try:
            success = self.student_repo.soft_delete(student_id, audit_context)
            
            if not success:
                raise NotFoundError(f"Student {student_id} not found")
            
            self.db.commit()
            
            return success
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def restore_student(self, student_id: str) -> bool:
        """
        Restore soft-deleted student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Success status
        """
        try:
            success = self.student_repo.restore(student_id)
            
            if not success:
                raise NotFoundError(
                    f"Student {student_id} not found or not deleted"
                )
            
            self.db.commit()
            
            return success
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")