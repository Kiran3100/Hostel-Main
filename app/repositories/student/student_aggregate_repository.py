# --- File: student_aggregate_repository.py ---

"""
Student aggregate repository.

Provides aggregated student data operations, analytics, and cross-entity queries
for comprehensive student insights and reporting.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import and_, or_, func, desc, case
from sqlalchemy.orm import Session, joinedload

from app.models.student.student import Student
from app.models.student.student_profile import StudentProfile
from app.models.student.student_document import StudentDocument
from app.models.student.student_preferences import StudentPreferences
from app.models.student.guardian_contact import GuardianContact
from app.models.student.room_transfer_history import RoomTransferHistory
from app.models.user.user import User
from app.models.hostel.hostel import Hostel
from app.models.room.room import Room
from app.models.base.enums import StudentStatus


class StudentAggregateRepository:
    """
    Student aggregate repository for cross-entity operations and analytics.
    
    Provides:
        - Comprehensive student data aggregation
        - Cross-entity queries and joins
        - Advanced analytics and insights
        - Dashboard and reporting data
        - Performance metrics and KPIs
        - Trend analysis and forecasting
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # COMPREHENSIVE STUDENT DATA
    # ============================================================================

    def get_complete_student_data(
        self,
        student_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get complete student data with all related entities.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Dictionary with complete student information
        """
        student = self.db.query(Student).options(
            joinedload(Student.user),
            joinedload(Student.hostel),
            joinedload(Student.room),
            joinedload(Student.bed),
            joinedload(Student.profile),
            joinedload(Student.preferences)
        ).filter(Student.id == student_id).first()
        
        if not student:
            return None
        
        # Get related entities
        documents = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.student_id == student_id,
                StudentDocument.deleted_at.is_(None)
            )
        ).all()
        
        guardians = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.deleted_at.is_(None)
            )
        ).order_by(GuardianContact.priority.asc()).all()
        
        transfers = self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.student_id == student_id
        ).order_by(desc(RoomTransferHistory.transfer_date)).limit(10).all()
        
        return {
            'student': student,
            'user': student.user,
            'hostel': student.hostel,
            'room': student.room,
            'bed': student.bed,
            'profile': student.profile,
            'preferences': student.preferences,
            'documents': documents,
            'guardians': guardians,
            'recent_transfers': transfers,
            'document_count': len(documents),
            'verified_documents': sum(1 for d in documents if d.verified),
            'guardian_count': len(guardians),
            'transfer_count': len(transfers)
        }

    # ============================================================================
    # DASHBOARD STATISTICS
    # ============================================================================

    def get_hostel_dashboard_stats(
        self,
        hostel_id: str
    ) -> dict[str, Any]:
        """
        Get comprehensive dashboard statistics for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with dashboard statistics
        """
        # Student counts by status
        total_students = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        active_students = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.student_status == StudentStatus.ACTIVE,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        checked_in = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date.isnot(None),
                Student.actual_checkout_date.is_(None),
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Verification stats
        pending_verification = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.documents_verified == False,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Financial stats
        deposit_pending = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.security_deposit_paid == False,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        total_deposits = self.db.query(
            func.sum(Student.security_deposit_amount)
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.security_deposit_paid == True,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Profile completeness
        avg_profile_completeness = self.db.query(
            func.avg(StudentProfile.profile_completeness)
        ).join(Student).filter(
            Student.hostel_id == hostel_id
        ).scalar()
        
        # Document stats
        total_documents = self.db.query(func.count(StudentDocument.id)).join(
            Student
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                StudentDocument.deleted_at.is_(None)
            )
        ).scalar()
        
        verified_documents = self.db.query(func.count(StudentDocument.id)).join(
            Student
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                StudentDocument.verified == True,
                StudentDocument.deleted_at.is_(None)
            )
        ).scalar()
        
        # Guardian stats
        total_guardians = self.db.query(func.count(GuardianContact.id)).join(
            Student
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                GuardianContact.deleted_at.is_(None)
            )
        ).scalar()
        
        verified_guardians = self.db.query(func.count(GuardianContact.id)).join(
            Student
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                GuardianContact.phone_verified == True,
                GuardianContact.email_verified == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).scalar()
        
        # Transfer stats
        pending_transfers = self.db.query(
            func.count(RoomTransferHistory.id)
        ).filter(
            and_(
                RoomTransferHistory.hostel_id == hostel_id,
                RoomTransferHistory.transfer_status == 'pending'
            )
        ).scalar()
        
        return {
            'students': {
                'total': total_students,
                'active': active_students,
                'checked_in': checked_in,
                'occupancy_rate': round((checked_in / total_students * 100), 2) if total_students > 0 else 0
            },
            'verification': {
                'pending': pending_verification,
                'verified': total_students - pending_verification,
                'verification_rate': round(((total_students - pending_verification) / total_students * 100), 2) if total_students > 0 else 0
            },
            'financial': {
                'deposit_pending': deposit_pending,
                'total_deposits_collected': float(total_deposits) if total_deposits else 0
            },
            'profiles': {
                'average_completeness': round(avg_profile_completeness, 2) if avg_profile_completeness else 0
            },
            'documents': {
                'total': total_documents,
                'verified': verified_documents,
                'verification_rate': round((verified_documents / total_documents * 100), 2) if total_documents > 0 else 0
            },
            'guardians': {
                'total': total_guardians,
                'verified': verified_guardians,
                'verification_rate': round((verified_guardians / total_guardians * 100), 2) if total_guardians > 0 else 0
            },
            'transfers': {
                'pending_approval': pending_transfers
            }
        }

    # ============================================================================
    # ANALYTICS AND TRENDS
    # ============================================================================

    def get_enrollment_trends(
        self,
        hostel_id: str,
        months: int = 12
    ) -> list[dict[str, Any]]:
        """
        Get enrollment trends over time.
        
        Args:
            hostel_id: Hostel UUID
            months: Number of months to analyze
            
        Returns:
            List of monthly enrollment data
        """
        start_date = datetime.utcnow() - timedelta(days=months * 30)
        
        results = self.db.query(
            func.strftime('%Y-%m', Student.check_in_date).label('month'),
            func.count(Student.id).label('enrollments')
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date >= start_date,
                Student.deleted_at.is_(None)
            )
        ).group_by('month').order_by('month').all()
        
        return [
            {'month': month, 'enrollments': count}
            for month, count in results
        ]

    def get_checkout_trends(
        self,
        hostel_id: str,
        months: int = 12
    ) -> list[dict[str, Any]]:
        """
        Get checkout trends over time.
        
        Args:
            hostel_id: Hostel UUID
            months: Number of months to analyze
            
        Returns:
            List of monthly checkout data
        """
        start_date = datetime.utcnow() - timedelta(days=months * 30)
        
        results = self.db.query(
            func.strftime('%Y-%m', Student.actual_checkout_date).label('month'),
            func.count(Student.id).label('checkouts')
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.actual_checkout_date >= start_date,
                Student.deleted_at.is_(None)
            )
        ).group_by('month').order_by('month').all()
        
        return [
            {'month': month, 'checkouts': count}
            for month, count in results
        ]

    def get_retention_metrics(
        self,
        hostel_id: str
    ) -> dict[str, Any]:
        """
        Calculate student retention metrics.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with retention metrics
        """
        # Students checked in more than 3 months ago
        three_months_ago = date.today() - timedelta(days=90)
        
        students_3m = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date <= three_months_ago,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        still_active_3m = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date <= three_months_ago,
                Student.student_status == StudentStatus.ACTIVE,
                Student.actual_checkout_date.is_(None),
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Students checked in more than 6 months ago
        six_months_ago = date.today() - timedelta(days=180)
        
        students_6m = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date <= six_months_ago,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        still_active_6m = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date <= six_months_ago,
                Student.student_status == StudentStatus.ACTIVE,
                Student.actual_checkout_date.is_(None),
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Average stay duration
        avg_stay = self.db.query(
            func.avg(
                func.julianday(Student.actual_checkout_date) - 
                func.julianday(Student.check_in_date)
            )
        ).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.check_in_date.isnot(None),
                Student.actual_checkout_date.isnot(None),
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        return {
            'retention_3_months': round((still_active_3m / students_3m * 100), 2) if students_3m > 0 else 0,
            'retention_6_months': round((still_active_6m / students_6m * 100), 2) if students_6m > 0 else 0,
            'average_stay_days': round(avg_stay, 2) if avg_stay else 0
        }

    # ============================================================================
    # STUDENT SEGMENTATION
    # ============================================================================

    def segment_students_by_demographics(
        self,
        hostel_id: str
    ) -> dict[str, Any]:
        """
        Segment students by various demographic factors.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with segmentation data
        """
        # By student type
        institutional = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.institution_name.isnot(None),
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        working = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.company_name.isnot(None),
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # By gender (from user profile)
        gender_dist = self.db.query(
            User.gender,
            func.count(Student.id).label('count')
        ).join(Student).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.deleted_at.is_(None)
            )
        ).group_by(User.gender).all()
        
        # By age groups (from profile)
        age_groups = {
            '18-20': 0,
            '21-23': 0,
            '24-26': 0,
            '27-30': 0,
            '30+': 0
        }
        
        profiles = self.db.query(StudentProfile).join(Student).filter(
            and_(
                Student.hostel_id == hostel_id,
                StudentProfile.age.isnot(None)
            )
        ).all()
        
        for profile in profiles:
            age = profile.age
            if age <= 20:
                age_groups['18-20'] += 1
            elif age <= 23:
                age_groups['21-23'] += 1
            elif age <= 26:
                age_groups['24-26'] += 1
            elif age <= 30:
                age_groups['27-30'] += 1
            else:
                age_groups['30+'] += 1
        
        return {
            'by_type': {
                'institutional': institutional,
                'working_professional': working
            },
            'by_gender': {
                gender: count for gender, count in gender_dist
            },
            'by_age_group': age_groups
        }

    # ============================================================================
    # COMPLIANCE AND RISK ASSESSMENT
    # ============================================================================

    def get_compliance_overview(
        self,
        hostel_id: str
    ) -> dict[str, Any]:
        """
        Get compliance and risk assessment overview.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with compliance data
        """
        total_students = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.student_status == StudentStatus.ACTIVE,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Document compliance
        incomplete_docs = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.documents_verified == False,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        # Expired documents
        expired_docs = self.db.query(
            func.count(func.distinct(StudentDocument.student_id))
        ).join(Student).filter(
            and_(
                Student.hostel_id == hostel_id,
                StudentDocument.is_expired == True,
                StudentDocument.deleted_at.is_(None)
            )
        ).scalar()
        
        # Guardian verification
        no_verified_guardian = self.db.query(
            func.count(func.distinct(Student.id))
        ).outerjoin(GuardianContact).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.deleted_at.is_(None),
                or_(
                    GuardianContact.id.is_(None),
                    GuardianContact.phone_verified == False
                )
            )
        ).scalar()
        
        # Security deposit
        deposit_not_paid = self.db.query(func.count(Student.id)).filter(
            and_(
                Student.hostel_id == hostel_id,
                Student.security_deposit_paid == False,
                Student.deleted_at.is_(None)
            )
        ).scalar()
        
        return {
            'total_active_students': total_students,
            'compliance_issues': {
                'incomplete_documents': incomplete_docs,
                'expired_documents': expired_docs,
                'unverified_guardians': no_verified_guardian,
                'deposit_not_paid': deposit_not_paid
            },
            'compliance_score': round(
                ((total_students - incomplete_docs - expired_docs - 
                  no_verified_guardian - deposit_not_paid) / 
                 (total_students * 4) * 100), 2
            ) if total_students > 0 else 0
        }

    # ============================================================================
    # SEARCH AND FILTERING
    # ============================================================================

    def advanced_search(
        self,
        search_params: dict[str, Any],
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[Student]:
        """
        Advanced student search with multiple criteria.
        
        Args:
            search_params: Dictionary of search parameters
            hostel_id: Optional hostel filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of matching students
        """
        query = self.db.query(Student).join(User).outerjoin(StudentProfile)
        
        filters = [Student.deleted_at.is_(None)]
        
        if hostel_id:
            filters.append(Student.hostel_id == hostel_id)
        
        # Text search
        if search_term := search_params.get('search_term'):
            filters.append(
                or_(
                    User.first_name.ilike(f"%{search_term}%"),
                    User.last_name.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%"),
                    User.phone.ilike(f"%{search_term}%"),
                    Student.student_id_number.ilike(f"%{search_term}%")
                )
            )
        
        # Status filter
        if status := search_params.get('status'):
            filters.append(Student.student_status == status)
        
        # Institution filter
        if institution := search_params.get('institution'):
            filters.append(Student.institution_name.ilike(f"%{institution}%"))
        
        # Company filter
        if company := search_params.get('company'):
            filters.append(Student.company_name.ilike(f"%{company}%"))
        
        # Check-in status
        if checked_in := search_params.get('checked_in'):
            if checked_in:
                filters.append(
                    and_(
                        Student.check_in_date.isnot(None),
                        Student.actual_checkout_date.is_(None)
                    )
                )
            else:
                filters.append(
                    or_(
                        Student.check_in_date.is_(None),
                        Student.actual_checkout_date.isnot(None)
                    )
                )
        
        # Document verification
        if docs_verified := search_params.get('documents_verified'):
            filters.append(Student.documents_verified == docs_verified)
        
        # Security deposit
        if deposit_paid := search_params.get('security_deposit_paid'):
            filters.append(Student.security_deposit_paid == deposit_paid)
        
        # Gender filter
        if gender := search_params.get('gender'):
            filters.append(User.gender == gender)
        
        # Age range
        if min_age := search_params.get('min_age'):
            filters.append(StudentProfile.age >= min_age)
        if max_age := search_params.get('max_age'):
            filters.append(StudentProfile.age <= max_age)
        
        query = query.filter(and_(*filters))
        
        # Sorting
        sort_by = search_params.get('sort_by', 'created_at')
        sort_order = search_params.get('sort_order', 'desc')
        
        if sort_by == 'name':
            order_field = User.first_name
        elif sort_by == 'check_in_date':
            order_field = Student.check_in_date
        else:
            order_field = Student.created_at
        
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())
        
        return query.offset(offset).limit(limit).all()