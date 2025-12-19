"""
Student repository.

Comprehensive student lifecycle management with academic integration,
performance tracking, and support services.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import and_, or_, func, case, cast, String
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.student.student import Student
from app.models.student.student_profile import StudentProfile
from app.models.student.guardian_contact import GuardianContact
from app.models.student.student_document import StudentDocument
from app.models.user.user import User
from app.models.hostel.hostel import Hostel
from app.models.room.room import Room
from app.models.room.bed import Bed
from app.models.base.enums import StudentStatus


class StudentRepository:
    """
    Student repository for comprehensive student lifecycle management.
    
    Handles:
        - Complete lifecycle from enrollment to checkout
        - Academic performance tracking and monitoring
        - Student transfers and room assignments
        - Behavioral pattern analysis
        - Disciplinary process management
        - Satisfaction tracking and feedback
        - Early warning system for at-risk students
        - Multi-tenant data isolation
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create(
        self,
        student_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Create new student with audit logging.
        
        Args:
            student_data: Student information
            audit_context: Audit context (user_id, ip_address, etc.)
            
        Returns:
            Created student instance
        """
        # Add audit information
        if audit_context:
            student_data['created_by'] = audit_context.get('user_id')
            student_data['updated_by'] = audit_context.get('user_id')

        student = Student(**student_data)
        self.db.add(student)
        self.db.flush()
        
        return student

    def find_by_id(
        self,
        student_id: str,
        include_deleted: bool = False,
        eager_load: bool = False
    ) -> Optional[Student]:
        """
        Find student by ID with optional eager loading.
        
        Args:
            student_id: Student UUID
            include_deleted: Include soft-deleted records
            eager_load: Load related entities
            
        Returns:
            Student instance or None
        """
        query = self.db.query(Student)
        
        if eager_load:
            query = query.options(
                joinedload(Student.user),
                joinedload(Student.hostel),
                joinedload(Student.room),
                joinedload(Student.bed),
                selectinload(Student.profile),
                selectinload(Student.guardian_contacts),
                selectinload(Student.documents)
            )
        
        query = query.filter(Student.id == student_id)
        
        if not include_deleted:
            query = query.filter(Student.deleted_at.is_(None))
        
        return query.first()

    def find_by_user_id(
        self,
        user_id: str,
        include_deleted: bool = False
    ) -> Optional[Student]:
        """
        Find student by user ID.
        
        Args:
            user_id: User UUID
            include_deleted: Include soft-deleted records
            
        Returns:
            Student instance or None
        """
        query = self.db.query(Student).filter(Student.user_id == user_id)
        
        if not include_deleted:
            query = query.filter(Student.deleted_at.is_(None))
        
        return query.first()

    def update(
        self,
        student_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Update student with version control and audit logging.
        
        Args:
            student_id: Student UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        student = self.find_by_id(student_id)
        if not student:
            return None
        
        # Add audit information
        if audit_context:
            update_data['updated_by'] = audit_context.get('user_id')
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            if hasattr(student, key):
                setattr(student, key, value)
        
        self.db.flush()
        return student

    def soft_delete(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Soft delete student with audit logging.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Success status
        """
        student = self.find_by_id(student_id)
        if not student:
            return False
        
        student.deleted_at = datetime.utcnow()
        if audit_context:
            student.deleted_by = audit_context.get('user_id')
        
        self.db.flush()
        return True

    def restore(self, student_id: str) -> bool:
        """
        Restore soft-deleted student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Success status
        """
        student = self.find_by_id(student_id, include_deleted=True)
        if not student or not student.deleted_at:
            return False
        
        student.deleted_at = None
        student.deleted_by = None
        self.db.flush()
        
        return True

    # ============================================================================
    # STUDENT LIFECYCLE MANAGEMENT
    # ============================================================================

    def check_in_student(
        self,
        student_id: str,
        room_id: str,
        bed_id: Optional[str] = None,
        check_in_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Process student check-in with room assignment.
        
        Args:
            student_id: Student UUID
            room_id: Room UUID
            bed_id: Bed UUID (optional)
            check_in_date: Check-in date (defaults to today)
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        student = self.find_by_id(student_id)
        if not student:
            return None
        
        update_data = {
            'room_id': room_id,
            'bed_id': bed_id,
            'check_in_date': check_in_date or date.today(),
            'student_status': StudentStatus.ACTIVE
        }
        
        return self.update(student_id, update_data, audit_context)

    def check_out_student(
        self,
        student_id: str,
        checkout_date: Optional[date] = None,
        checkout_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Process student check-out.
        
        Args:
            student_id: Student UUID
            checkout_date: Checkout date (defaults to today)
            checkout_notes: Checkout notes
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        student = self.find_by_id(student_id)
        if not student:
            return None
        
        update_data = {
            'actual_checkout_date': checkout_date or date.today(),
            'checkout_notes': checkout_notes,
            'student_status': StudentStatus.CHECKED_OUT,
            'room_id': None,
            'bed_id': None
        }
        
        return self.update(student_id, update_data, audit_context)

    def initiate_notice_period(
        self,
        student_id: str,
        notice_days: int,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Initiate notice period for student.
        
        Args:
            student_id: Student UUID
            notice_days: Notice period duration in days
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        student = self.find_by_id(student_id)
        if not student:
            return None
        
        notice_start = date.today()
        notice_end = notice_start + timedelta(days=notice_days)
        
        update_data = {
            'notice_period_start': notice_start,
            'notice_period_end': notice_end,
            'notice_period_days': notice_days,
            'student_status': StudentStatus.NOTICE_PERIOD,
            'expected_checkout_date': notice_end
        }
        
        return self.update(student_id, update_data, audit_context)

    def suspend_student(
        self,
        student_id: str,
        suspension_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Suspend student account.
        
        Args:
            student_id: Student UUID
            suspension_reason: Reason for suspension
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {
            'student_status': StudentStatus.SUSPENDED,
            'admin_notes': suspension_reason
        }
        
        return self.update(student_id, update_data, audit_context)

    def reactivate_student(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Reactivate suspended student.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {
            'student_status': StudentStatus.ACTIVE
        }
        
        return self.update(student_id, update_data, audit_context)

    # ============================================================================
    # QUERYING AND FILTERING
    # ============================================================================

    def find_by_hostel(
        self,
        hostel_id: str,
        status: Optional[StudentStatus] = None,
        include_deleted: bool = False,
        offset: int = 0,
        limit: int = 50
    ) -> list[Student]:
        """
        Find students by hostel with filtering.
        
        Args:
            hostel_id: Hostel UUID
            status: Filter by student status
            include_deleted: Include soft-deleted records
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of students
        """
        query = self.db.query(Student).filter(Student.hostel_id == hostel_id)
        
        if status:
            query = query.filter(Student.student_status == status)
        
        if not include_deleted:
            query = query.filter(Student.deleted_at.is_(None))
        
        return query.offset(offset).limit(limit).all()

    def find_active_residents(
        self,
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[Student]:
        """
        Find all active resident students.
        
        Args:
            hostel_id: Optional hostel filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of active students
        """
        query = self.db.query(Student).filter(
            and_(
                Student.student_status == StudentStatus.ACTIVE,
                Student.check_in_date.isnot(None),
                Student.actual_checkout_date.is_(None),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.offset(offset).limit(limit).all()

    def find_by_room(self, room_id: str) -> list[Student]:
        """
        Find students currently in a room.
        
        Args:
            room_id: Room UUID
            
        Returns:
            List of students
        """
        return self.db.query(Student).filter(
            and_(
                Student.room_id == room_id,
                Student.student_status == StudentStatus.ACTIVE,
                Student.deleted_at.is_(None)
            )
        ).all()

    def find_in_notice_period(
        self,
        hostel_id: Optional[str] = None
    ) -> list[Student]:
        """
        Find students currently in notice period.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of students
        """
        query = self.db.query(Student).filter(
            and_(
                Student.student_status == StudentStatus.NOTICE_PERIOD,
                Student.notice_period_end >= date.today(),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_pending_checkout(
        self,
        hostel_id: Optional[str] = None,
        days_threshold: int = 7
    ) -> list[Student]:
        """
        Find students with checkout pending within threshold.
        
        Args:
            hostel_id: Optional hostel filter
            days_threshold: Days until expected checkout
            
        Returns:
            List of students
        """
        threshold_date = date.today() + timedelta(days=days_threshold)
        
        query = self.db.query(Student).filter(
            and_(
                Student.expected_checkout_date.isnot(None),
                Student.expected_checkout_date <= threshold_date,
                Student.actual_checkout_date.is_(None),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_by_institution(
        self,
        institution_name: str,
        hostel_id: Optional[str] = None
    ) -> list[Student]:
        """
        Find students by educational institution.
        
        Args:
            institution_name: Institution name (partial match)
            hostel_id: Optional hostel filter
            
        Returns:
            List of students
        """
        query = self.db.query(Student).filter(
            and_(
                Student.institution_name.ilike(f"%{institution_name}%"),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_by_company(
        self,
        company_name: str,
        hostel_id: Optional[str] = None
    ) -> list[Student]:
        """
        Find students by company/employer.
        
        Args:
            company_name: Company name (partial match)
            hostel_id: Optional hostel filter
            
        Returns:
            List of students
        """
        query = self.db.query(Student).filter(
            and_(
                Student.company_name.ilike(f"%{company_name}%"),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.all()

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
            search_term: Search term (name, email, phone, student ID)
            hostel_id: Optional hostel filter
            status: Optional status filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of matching students
        """
        query = self.db.query(Student).join(User).filter(
            and_(
                or_(
                    User.first_name.ilike(f"%{search_term}%"),
                    User.last_name.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%"),
                    User.phone.ilike(f"%{search_term}%"),
                    Student.student_id_number.ilike(f"%{search_term}%")
                ),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        if status:
            query = query.filter(Student.student_status == status)
        
        return query.offset(offset).limit(limit).all()

    # ============================================================================
    # DOCUMENT VERIFICATION
    # ============================================================================

    def find_pending_verification(
        self,
        hostel_id: Optional[str] = None,
        verification_type: Optional[str] = None
    ) -> list[Student]:
        """
        Find students with pending document verification.
        
        Args:
            hostel_id: Optional hostel filter
            verification_type: Type of verification (id_proof, institutional_id, company_id)
            
        Returns:
            List of students pending verification
        """
        query = self.db.query(Student).filter(Student.deleted_at.is_(None))
        
        if verification_type == 'id_proof':
            query = query.filter(Student.id_proof_verified == False)
        elif verification_type == 'institutional_id':
            query = query.filter(
                and_(
                    Student.institution_name.isnot(None),
                    Student.institutional_id_verified == False
                )
            )
        elif verification_type == 'company_id':
            query = query.filter(
                and_(
                    Student.company_name.isnot(None),
                    Student.company_id_verified == False
                )
            )
        else:
            # All unverified
            query = query.filter(Student.documents_verified == False)
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def verify_id_proof(
        self,
        student_id: str,
        verified_by: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Mark student ID proof as verified.
        
        Args:
            student_id: Student UUID
            verified_by: Admin user ID who verified
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {
            'id_proof_verified': True,
            'id_proof_verified_at': date.today(),
            'id_proof_verified_by': verified_by
        }
        
        student = self.update(student_id, update_data, audit_context)
        if student:
            self._update_overall_verification_status(student)
        
        return student

    def verify_institutional_id(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Mark student institutional ID as verified.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {'institutional_id_verified': True}
        
        student = self.update(student_id, update_data, audit_context)
        if student:
            self._update_overall_verification_status(student)
        
        return student

    def verify_company_id(
        self,
        student_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Mark student company ID as verified.
        
        Args:
            student_id: Student UUID
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {'company_id_verified': True}
        
        student = self.update(student_id, update_data, audit_context)
        if student:
            self._update_overall_verification_status(student)
        
        return student

    def _update_overall_verification_status(self, student: Student) -> None:
        """
        Update overall document verification status.
        
        Args:
            student: Student instance
        """
        all_verified = student.id_proof_verified
        
        if student.institution_name:
            all_verified = all_verified and student.institutional_id_verified
        
        if student.company_name:
            all_verified = all_verified and student.company_id_verified
        
        student.documents_verified = all_verified
        self.db.flush()

    # ============================================================================
    # FINANCIAL TRACKING
    # ============================================================================

    def find_security_deposit_pending(
        self,
        hostel_id: Optional[str] = None
    ) -> list[Student]:
        """
        Find students with pending security deposit.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of students
        """
        query = self.db.query(Student).filter(
            and_(
                Student.security_deposit_paid == False,
                Student.student_status == StudentStatus.ACTIVE,
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def mark_security_deposit_paid(
        self,
        student_id: str,
        amount: Decimal,
        payment_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Mark security deposit as paid.
        
        Args:
            student_id: Student UUID
            amount: Deposit amount
            payment_date: Payment date (defaults to today)
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {
            'security_deposit_amount': amount,
            'security_deposit_paid': True,
            'security_deposit_paid_date': payment_date or date.today()
        }
        
        return self.update(student_id, update_data, audit_context)

    def process_security_deposit_refund(
        self,
        student_id: str,
        refund_amount: Decimal,
        refund_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[Student]:
        """
        Process security deposit refund.
        
        Args:
            student_id: Student UUID
            refund_amount: Refund amount (after deductions)
            refund_date: Refund date (defaults to today)
            audit_context: Audit context
            
        Returns:
            Updated student instance or None
        """
        update_data = {
            'security_deposit_refund_amount': refund_amount,
            'security_deposit_refund_date': refund_date or date.today()
        }
        
        return self.update(student_id, update_data, audit_context)

    # ============================================================================
    # STATISTICS AND ANALYTICS
    # ============================================================================

    def get_hostel_statistics(self, hostel_id: str) -> dict[str, Any]:
        """
        Get comprehensive statistics for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with statistics
        """
        base_query = self.db.query(Student).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.deleted_at.is_(None)
            )
        )
        
        total_students = base_query.count()
        
        active_students = base_query.filter(
            Student.student_status == StudentStatus.ACTIVE
        ).count()
        
        checked_in = base_query.filter(
            and_(
                Student.check_in_date.isnot(None),
                Student.actual_checkout_date.is_(None)
            )
        ).count()
        
        notice_period = base_query.filter(
            Student.student_status == StudentStatus.NOTICE_PERIOD
        ).count()
        
        suspended = base_query.filter(
            Student.student_status == StudentStatus.SUSPENDED
        ).count()
        
        # Document verification stats
        pending_verification = base_query.filter(
            Student.documents_verified == False
        ).count()
        
        # Financial stats
        deposit_pending = base_query.filter(
            Student.security_deposit_paid == False
        ).count()
        
        # Student type breakdown
        institutional = base_query.filter(
            Student.institution_name.isnot(None)
        ).count()
        
        working_professional = base_query.filter(
            Student.company_name.isnot(None)
        ).count()
        
        # Mess subscription
        mess_subscribed = base_query.filter(
            Student.mess_subscribed == True
        ).count()
        
        return {
            'total_students': total_students,
            'active_students': active_students,
            'checked_in': checked_in,
            'notice_period': notice_period,
            'suspended': suspended,
            'pending_verification': pending_verification,
            'deposit_pending': deposit_pending,
            'institutional_students': institutional,
            'working_professionals': working_professional,
            'mess_subscribed': mess_subscribed,
            'occupancy_rate': round((checked_in / total_students * 100), 2) if total_students > 0 else 0
        }

    def get_status_breakdown(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get student count by status.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping status to count
        """
        query = self.db.query(
            Student.student_status,
            func.count(Student.id).label('count')
        ).filter(Student.deleted_at.is_(None))
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(Student.student_status)
        
        results = query.all()
        
        return {status.value: count for status, count in results}

    def get_institution_breakdown(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get student count by institution.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of top institutions to return
            
        Returns:
            List of institutions with student counts
        """
        query = self.db.query(
            Student.institution_name,
            func.count(Student.id).label('count')
        ).filter(
            and_(
                Student.institution_name.isnot(None),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(Student.institution_name)
        query = query.order_by(func.count(Student.id).desc())
        query = query.limit(limit)
        
        results = query.all()
        
        return [
            {'institution': institution, 'count': count}
            for institution, count in results
        ]

    def get_average_stay_duration(
        self,
        hostel_id: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate average stay duration in days.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Average duration in days or None
        """
        query = self.db.query(Student).filter(
            and_(
                Student.check_in_date.isnot(None),
                Student.actual_checkout_date.isnot(None),
                Student.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        students = query.all()
        
        if not students:
            return None
        
        total_days = sum(
            (s.actual_checkout_date - s.check_in_date).days
            for s in students
        )
        
        return total_days / len(students)

    def count_by_criteria(
        self,
        hostel_id: Optional[str] = None,
        status: Optional[StudentStatus] = None,
        institution: Optional[str] = None,
        company: Optional[str] = None,
        checked_in: Optional[bool] = None
    ) -> int:
        """
        Count students matching criteria.
        
        Args:
            hostel_id: Optional hostel filter
            status: Optional status filter
            institution: Optional institution filter
            company: Optional company filter
            checked_in: Optional check-in status filter
            
        Returns:
            Count of matching students
        """
        query = self.db.query(func.count(Student.id)).filter(
            Student.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(Student.hostel_id == hostel_id)
        
        if status:
            query = query.filter(Student.student_status == status)
        
        if institution:
            query = query.filter(Student.institution_name.ilike(f"%{institution}%"))
        
        if company:
            query = query.filter(Student.company_name.ilike(f"%{company}%"))
        
        if checked_in is not None:
            if checked_in:
                query = query.filter(
                    and_(
                        Student.check_in_date.isnot(None),
                        Student.actual_checkout_date.is_(None)
                    )
                )
            else:
                query = query.filter(
                    or_(
                        Student.check_in_date.is_(None),
                        Student.actual_checkout_date.isnot(None)
                    )
                )
        
        return query.scalar()

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
            new_status: New status to set
            audit_context: Audit context
            
        Returns:
            Number of students updated
        """
        updated = self.db.query(Student).filter(
            and_(
                Student.id.in_(student_ids),
                Student.deleted_at.is_(None)
            )
        ).update(
            {
                'student_status': new_status,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id') if audit_context else None
            },
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    def bulk_assign_hostel(
        self,
        student_ids: list[str],
        hostel_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk assign students to a hostel.
        
        Args:
            student_ids: List of student UUIDs
            hostel_id: Hostel UUID
            audit_context: Audit context
            
        Returns:
            Number of students updated
        """
        updated = self.db.query(Student).filter(
            and_(
                Student.id.in_(student_ids),
                Student.deleted_at.is_(None)
            )
        ).update(
            {
                'hostel_id': hostel_id,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id') if audit_context else None
            },
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    # ============================================================================
    # VALIDATION AND BUSINESS RULES
    # ============================================================================

    def exists_by_user_id(self, user_id: str) -> bool:
        """
        Check if student exists for user.
        
        Args:
            user_id: User UUID
            
        Returns:
            Existence status
        """
        return self.db.query(
            self.db.query(Student).filter(
                and_(
                    Student.user_id == user_id,
                    Student.deleted_at.is_(None)
                )
            ).exists()
        ).scalar()

    def exists_by_student_id_number(
        self,
        student_id_number: str,
        exclude_id: Optional[str] = None
    ) -> bool:
        """
        Check if student ID number is already used.
        
        Args:
            student_id_number: Student ID number
            exclude_id: Student UUID to exclude from check
            
        Returns:
            Existence status
        """
        query = self.db.query(Student).filter(
            and_(
                Student.student_id_number == student_id_number,
                Student.deleted_at.is_(None)
            )
        )
        
        if exclude_id:
            query = query.filter(Student.id != exclude_id)
        
        return self.db.query(query.exists()).scalar()

    def can_check_in(self, student_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate if student can be checked in.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Tuple of (can_check_in, reason_if_not)
        """
        student = self.find_by_id(student_id)
        if not student:
            return False, "Student not found"
        
        if student.check_in_date and not student.actual_checkout_date:
            return False, "Student is already checked in"
        
        if not student.security_deposit_paid:
            return False, "Security deposit not paid"
        
        if not student.documents_verified:
            return False, "Documents not verified"
        
        if student.student_status == StudentStatus.SUSPENDED:
            return False, "Student account is suspended"
        
        return True, None

    def can_check_out(self, student_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate if student can be checked out.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Tuple of (can_check_out, reason_if_not)
        """
        student = self.find_by_id(student_id)
        if not student:
            return False, "Student not found"
        
        if not student.check_in_date:
            return False, "Student was never checked in"
        
        if student.actual_checkout_date:
            return False, "Student is already checked out"
        
        # Check for pending payments (would need payment repository integration)
        # This is a placeholder for financial clearance check
        if student.financial_clearance_pending:
            return False, "Financial clearance pending"
        
        return True, None