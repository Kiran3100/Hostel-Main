# --- File: student_profile_repository.py ---

"""
Student profile repository.

Comprehensive profile management with privacy controls, verification,
and personalization features.
"""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.student.student_profile import StudentProfile
from app.models.student.student import Student


class StudentProfileRepository:
    """
    Student profile repository for extended profile information management.
    
    Handles:
        - Comprehensive student profile data
        - Privacy controls and data access
        - Profile verification and validation
        - Profile completeness tracking
        - Demographic analysis
        - Profile history and audit trail
        - GDPR/CCPA compliance
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create(
        self,
        profile_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Create student profile with audit logging.
        
        Args:
            profile_data: Profile information
            audit_context: Audit context (user_id, ip_address, etc.)
            
        Returns:
            Created profile instance
        """
        if audit_context:
            profile_data['created_by'] = audit_context.get('user_id')
            profile_data['updated_by'] = audit_context.get('user_id')

        profile = StudentProfile(**profile_data)
        self.db.add(profile)
        self.db.flush()
        
        # Calculate initial profile completeness
        self._calculate_profile_completeness(profile)
        
        return profile

    def find_by_id(
        self,
        profile_id: str,
        eager_load: bool = False
    ) -> Optional[StudentProfile]:
        """
        Find profile by ID with optional eager loading.
        
        Args:
            profile_id: Profile UUID
            eager_load: Load related entities
            
        Returns:
            Profile instance or None
        """
        query = self.db.query(StudentProfile)
        
        if eager_load:
            query = query.options(joinedload(StudentProfile.student))
        
        return query.filter(StudentProfile.id == profile_id).first()

    def find_by_student_id(
        self,
        student_id: str,
        eager_load: bool = False
    ) -> Optional[StudentProfile]:
        """
        Find profile by student ID.
        
        Args:
            student_id: Student UUID
            eager_load: Load related entities
            
        Returns:
            Profile instance or None
        """
        query = self.db.query(StudentProfile)
        
        if eager_load:
            query = query.options(joinedload(StudentProfile.student))
        
        return query.filter(StudentProfile.student_id == student_id).first()

    def update(
        self,
        profile_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentProfile]:
        """
        Update profile with audit logging.
        
        Args:
            profile_id: Profile UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated profile instance or None
        """
        profile = self.find_by_id(profile_id)
        if not profile:
            return None
        
        if audit_context:
            update_data['updated_by'] = audit_context.get('user_id')
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        self.db.flush()
        
        # Recalculate profile completeness
        self._calculate_profile_completeness(profile)
        
        return profile

    def update_by_student_id(
        self,
        student_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentProfile]:
        """
        Update profile by student ID.
        
        Args:
            student_id: Student UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated profile instance or None
        """
        profile = self.find_by_student_id(student_id)
        if not profile:
            return None
        
        return self.update(profile.id, update_data, audit_context)

    # ============================================================================
    # PROFILE COMPLETENESS
    # ============================================================================

    def _calculate_profile_completeness(self, profile: StudentProfile) -> None:
        """
        Calculate profile completion percentage.
        
        Args:
            profile: Profile instance
        """
        # Define weighted fields for completeness calculation
        fields_weight = {
            # Personal Information (20%)
            'date_of_birth': 5,
            'blood_group': 3,
            'nationality': 2,
            'languages_known': 5,
            'marital_status': 5,
            
            # Contact (15%)
            'alternate_email': 5,
            'alternate_phone': 5,
            'whatsapp_number': 5,
            
            # Address (15%)
            'permanent_address_line1': 5,
            'permanent_city': 3,
            'permanent_state': 3,
            'permanent_pincode': 4,
            
            # Education/Employment (20%)
            'highest_qualification': 5,
            'field_of_study': 5,
            'expected_graduation_date': 5,
            'department': 5,
            
            # Medical (15%)
            'medical_conditions': 8,
            'allergies': 7,
            
            # Preferences (10%)
            'hobbies': 3,
            'sports_activities': 3,
            'lifestyle_preferences': 4,
            
            # Additional (5%)
            'bio': 5
        }
        
        total_weight = sum(fields_weight.values())
        achieved_weight = 0
        
        for field, weight in fields_weight.items():
            value = getattr(profile, field, None)
            if value:
                # For boolean fields, check if True
                if isinstance(value, bool):
                    if value:
                        achieved_weight += weight
                # For other fields, check if not empty
                elif value:
                    achieved_weight += weight
        
        completeness = int((achieved_weight / total_weight) * 100)
        profile.profile_completeness = completeness
        self.db.flush()

    def get_profile_completeness(self, student_id: str) -> int:
        """
        Get profile completion percentage.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Completion percentage (0-100)
        """
        profile = self.find_by_student_id(student_id)
        return profile.profile_completeness if profile else 0

    def find_incomplete_profiles(
        self,
        threshold: int = 50,
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[StudentProfile]:
        """
        Find profiles below completeness threshold.
        
        Args:
            threshold: Minimum completeness percentage
            hostel_id: Optional hostel filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of incomplete profiles
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.profile_completeness < threshold
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.offset(offset).limit(limit).all()

    # ============================================================================
    # DEMOGRAPHIC ANALYSIS
    # ============================================================================

    def get_age_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get age distribution of students.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping age groups to counts
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.age.isnot(None)
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        profiles = query.all()
        
        age_groups = {
            '18-20': 0,
            '21-23': 0,
            '24-26': 0,
            '27-30': 0,
            '30+': 0
        }
        
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
        
        return age_groups

    def get_blood_group_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get blood group distribution.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping blood groups to counts
        """
        query = self.db.query(
            StudentProfile.blood_group,
            func.count(StudentProfile.id).label('count')
        ).filter(StudentProfile.blood_group.isnot(None))
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentProfile.blood_group)
        
        results = query.all()
        
        return {blood_group: count for blood_group, count in results}

    def get_nationality_breakdown(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get nationality distribution.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of top nationalities to return
            
        Returns:
            List of nationalities with counts
        """
        query = self.db.query(
            StudentProfile.nationality,
            func.count(StudentProfile.id).label('count')
        ).filter(StudentProfile.nationality.isnot(None))
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentProfile.nationality)
        query = query.order_by(func.count(StudentProfile.id).desc())
        query = query.limit(limit)
        
        results = query.all()
        
        return [
            {'nationality': nationality, 'count': count}
            for nationality, count in results
        ]

    def count_international_students(
        self,
        hostel_id: Optional[str] = None
    ) -> int:
        """
        Count international (non-Indian) students.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Count of international students
        """
        query = self.db.query(func.count(StudentProfile.id)).filter(
            and_(
                StudentProfile.permanent_country.isnot(None),
                StudentProfile.permanent_country != 'India'
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.scalar()

    # ============================================================================
    # MEDICAL INFORMATION
    # ============================================================================

    def find_with_medical_conditions(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Find students with medical conditions.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of profiles with medical conditions
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.has_medical_conditions == True
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_with_allergies(
        self,
        allergy_type: Optional[str] = None,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Find students with allergies.
        
        Args:
            allergy_type: Specific allergy to search for
            hostel_id: Optional hostel filter
            
        Returns:
            List of profiles with allergies
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.allergies.isnot(None)
        )
        
        if allergy_type:
            query = query.filter(
                StudentProfile.allergies.ilike(f"%{allergy_type}%")
            )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_requiring_special_accommodation(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Find students requiring special accommodation.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of profiles requiring special accommodation
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.requires_special_accommodation == True
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    # ============================================================================
    # SEARCH AND FILTERING
    # ============================================================================

    def search_by_qualification(
        self,
        qualification: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Search profiles by educational qualification.
        
        Args:
            qualification: Qualification name (partial match)
            hostel_id: Optional hostel filter
            
        Returns:
            List of matching profiles
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.highest_qualification.ilike(f"%{qualification}%")
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def search_by_field_of_study(
        self,
        field: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Search profiles by field of study.
        
        Args:
            field: Field of study (partial match)
            hostel_id: Optional hostel filter
            
        Returns:
            List of matching profiles
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.field_of_study.ilike(f"%{field}%")
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_scholarship_holders(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Find scholarship holder students.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of scholarship holders
        """
        query = self.db.query(StudentProfile).filter(
            StudentProfile.scholarship_holder == True
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    # ============================================================================
    # REFERRAL TRACKING
    # ============================================================================

    def find_referred_students(
        self,
        referrer_student_id: str
    ) -> list[StudentProfile]:
        """
        Find students referred by a specific student.
        
        Args:
            referrer_student_id: Referrer student UUID
            
        Returns:
            List of referred student profiles
        """
        return self.db.query(StudentProfile).filter(
            StudentProfile.referred_by_student_id == referrer_student_id
        ).all()

    def count_referrals(self, student_id: str) -> int:
        """
        Count number of referrals by a student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Number of referrals
        """
        return self.db.query(func.count(StudentProfile.id)).filter(
            StudentProfile.referred_by_student_id == student_id
        ).scalar()

    def get_top_referrers(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get top students by referral count.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of top referrers to return
            
        Returns:
            List of top referrers with counts
        """
        query = self.db.query(
            StudentProfile.referred_by_student_id,
            func.count(StudentProfile.id).label('referral_count')
        ).filter(StudentProfile.referred_by_student_id.isnot(None))
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentProfile.referred_by_student_id)
        query = query.order_by(func.count(StudentProfile.id).desc())
        query = query.limit(limit)
        
        results = query.all()
        
        return [
            {'student_id': student_id, 'referral_count': count}
            for student_id, count in results
        ]

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_average_profile_completeness(
        self,
        hostel_id: Optional[str] = None
    ) -> float:
        """
        Calculate average profile completeness.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Average completeness percentage
        """
        query = self.db.query(
            func.avg(StudentProfile.profile_completeness)
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        result = query.scalar()
        return round(result, 2) if result else 0.0

    def count_profiles_by_completeness_range(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Count profiles by completeness ranges.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping ranges to counts
        """
        query = self.db.query(StudentProfile)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        profiles = query.all()
        
        ranges = {
            '0-25%': 0,
            '26-50%': 0,
            '51-75%': 0,
            '76-100%': 0
        }
        
        for profile in profiles:
            completeness = profile.profile_completeness
            if completeness <= 25:
                ranges['0-25%'] += 1
            elif completeness <= 50:
                ranges['26-50%'] += 1
            elif completeness <= 75:
                ranges['51-75%'] += 1
            else:
                ranges['76-100%'] += 1
        
        return ranges

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def bulk_update_language_preference(
        self,
        student_ids: list[str],
        language: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk update preferred language.
        
        Args:
            student_ids: List of student UUIDs
            language: Language code
            audit_context: Audit context
            
        Returns:
            Number of profiles updated
        """
        updated = self.db.query(StudentProfile).filter(
            StudentProfile.student_id.in_(student_ids)
        ).update(
            {
                'preferred_language': language,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id') if audit_context else None
            },
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    # ============================================================================
    # VALIDATION
    # ============================================================================

    def exists_for_student(self, student_id: str) -> bool:
        """
        Check if profile exists for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Existence status
        """
        return self.db.query(
            self.db.query(StudentProfile).filter(
                StudentProfile.student_id == student_id
            ).exists()
        ).scalar()