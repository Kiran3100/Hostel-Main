"""
Student profile service.

Extended profile management with completeness tracking,
demographic analysis, and privacy controls.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.student_profile_repository import StudentProfileRepository
from app.repositories.student.student_repository import StudentRepository
from app.models.student.student_profile import StudentProfile
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError
)


class StudentProfileService:
    """
    Student profile service for extended information management.
    
    Handles:
        - Profile CRUD operations
        - Profile completeness tracking
        - Demographic data management
        - Medical information handling
        - Referral tracking
        - Privacy controls
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.profile_repo = StudentProfileRepository(db)
        self.student_repo = StudentRepository(db)

    # ============================================================================
    # PROFILE CRUD OPERATIONS
    # ============================================================================

    def create_profile(
        self,
        student_id: str,
        profile_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Create student profile.
        
        Args:
            student_id: Student UUID
            profile_data: Profile information
            audit_context: Audit context
            
        Returns:
            Created profile instance
            
        Raises:
            NotFoundError: If student not found
            ConflictError: If profile already exists
        """
        try:
            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Check if profile already exists
            if self.profile_repo.exists_for_student(student_id):
                raise ConflictError(
                    f"Profile already exists for student {student_id}"
                )
            
            profile_data['student_id'] = student_id
            
            profile = self.profile_repo.create(profile_data, audit_context)
            
            self.db.commit()
            
            return profile
            
        except (NotFoundError, ConflictError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_profile_by_student_id(
        self,
        student_id: str,
        include_student: bool = False
    ) -> StudentProfile:
        """
        Get profile by student ID.
        
        Args:
            student_id: Student UUID
            include_student: Load student entity
            
        Returns:
            Profile instance
            
        Raises:
            NotFoundError: If profile not found
        """
        profile = self.profile_repo.find_by_student_id(
            student_id,
            eager_load=include_student
        )
        
        if not profile:
            raise NotFoundError(f"Profile not found for student {student_id}")
        
        return profile

    def update_profile(
        self,
        student_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update student profile.
        
        Args:
            student_id: Student UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated profile instance
            
        Raises:
            NotFoundError: If profile not found
        """
        try:
            profile = self.profile_repo.update_by_student_id(
                student_id,
                update_data,
                audit_context
            )
            
            if not profile:
                raise NotFoundError(f"Profile not found for student {student_id}")
            
            self.db.commit()
            
            return profile
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # PERSONAL INFORMATION
    # ============================================================================

    def update_personal_info(
        self,
        student_id: str,
        personal_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update personal information.
        
        Args:
            student_id: Student UUID
            personal_data: Personal information
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        allowed_fields = [
            'date_of_birth',
            'age',
            'blood_group',
            'height_cm',
            'weight_kg',
            'nationality',
            'religion',
            'caste_category',
            'marital_status',
            'languages_known'
        ]
        
        update_data = {
            key: value for key, value in personal_data.items()
            if key in allowed_fields
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    def update_contact_info(
        self,
        student_id: str,
        contact_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update contact information.
        
        Args:
            student_id: Student UUID
            contact_data: Contact information
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        allowed_fields = [
            'alternate_email',
            'alternate_phone',
            'whatsapp_number',
            'preferred_contact_method'
        ]
        
        update_data = {
            key: value for key, value in contact_data.items()
            if key in allowed_fields
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    def update_permanent_address(
        self,
        student_id: str,
        address_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update permanent address.
        
        Args:
            student_id: Student UUID
            address_data: Address information
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        allowed_fields = [
            'permanent_address_line1',
            'permanent_address_line2',
            'permanent_city',
            'permanent_state',
            'permanent_country',
            'permanent_pincode'
        ]
        
        update_data = {
            key: value for key, value in address_data.items()
            if key in allowed_fields
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    # ============================================================================
    # EDUCATIONAL INFORMATION
    # ============================================================================

    def update_educational_info(
        self,
        student_id: str,
        education_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update educational information.
        
        Args:
            student_id: Student UUID
            education_data: Educational information
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        allowed_fields = [
            'previous_institution',
            'highest_qualification',
            'field_of_study',
            'academic_year',
            'semester',
            'expected_graduation_date',
            'cgpa',
            'scholarship_holder',
            'scholarship_details'
        ]
        
        update_data = {
            key: value for key, value in education_data.items()
            if key in allowed_fields
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    # ============================================================================
    # EMPLOYMENT INFORMATION
    # ============================================================================

    def update_employment_info(
        self,
        student_id: str,
        employment_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update employment information.
        
        Args:
            student_id: Student UUID
            employment_data: Employment information
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        allowed_fields = [
            'employment_type',
            'department',
            'years_of_experience',
            'joining_date',
            'office_address',
            'office_phone',
            'work_email',
            'reporting_manager_name',
            'reporting_manager_phone'
        ]
        
        update_data = {
            key: value for key, value in employment_data.items()
            if key in allowed_fields
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    # ============================================================================
    # MEDICAL INFORMATION
    # ============================================================================

    def update_medical_info(
        self,
        student_id: str,
        medical_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Update medical information.
        
        Args:
            student_id: Student UUID
            medical_data: Medical information
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        allowed_fields = [
            'has_medical_conditions',
            'medical_conditions',
            'medications',
            'allergies',
            'disabilities',
            'requires_special_accommodation',
            'special_accommodation_details',
            'family_doctor_name',
            'family_doctor_phone',
            'health_insurance_provider',
            'health_insurance_number'
        ]
        
        update_data = {
            key: value for key, value in medical_data.items()
            if key in allowed_fields
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    def get_students_with_medical_conditions(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Get students with medical conditions.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of profiles with medical conditions
        """
        return self.profile_repo.find_with_medical_conditions(hostel_id)

    def get_students_with_allergies(
        self,
        allergy_type: Optional[str] = None,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Get students with allergies.
        
        Args:
            allergy_type: Specific allergy to search
            hostel_id: Optional hostel filter
            
        Returns:
            List of profiles with allergies
        """
        return self.profile_repo.find_with_allergies(allergy_type, hostel_id)

    # ============================================================================
    # PROFILE COMPLETENESS
    # ============================================================================

    def get_profile_completeness(self, student_id: str) -> int:
        """
        Get profile completion percentage.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Completion percentage (0-100)
        """
        return self.profile_repo.get_profile_completeness(student_id)

    def get_incomplete_profiles(
        self,
        threshold: int = 50,
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[StudentProfile]:
        """
        Get profiles below completeness threshold.
        
        Args:
            threshold: Minimum completeness percentage
            hostel_id: Optional hostel filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of incomplete profiles
        """
        return self.profile_repo.find_incomplete_profiles(
            threshold,
            hostel_id,
            offset,
            limit
        )

    # ============================================================================
    # DEMOGRAPHICS AND ANALYTICS
    # ============================================================================

    def get_age_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get age distribution.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Age group distribution
        """
        return self.profile_repo.get_age_distribution(hostel_id)

    def get_blood_group_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get blood group distribution.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Blood group distribution
        """
        return self.profile_repo.get_blood_group_distribution(hostel_id)

    def get_nationality_breakdown(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get nationality distribution.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of top nationalities
            
        Returns:
            List of nationalities with counts
        """
        return self.profile_repo.get_nationality_breakdown(hostel_id, limit)

    def count_international_students(
        self,
        hostel_id: Optional[str] = None
    ) -> int:
        """
        Count international students.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Count of international students
        """
        return self.profile_repo.count_international_students(hostel_id)

    # ============================================================================
    # REFERRAL TRACKING
    # ============================================================================

    def track_referral(
        self,
        student_id: str,
        referrer_student_id: str,
        referral_code: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentProfile:
        """
        Track student referral.
        
        Args:
            student_id: Student UUID
            referrer_student_id: Referrer student UUID
            referral_code: Optional referral code
            audit_context: Audit context
            
        Returns:
            Updated profile instance
        """
        update_data = {
            'referred_by_student_id': referrer_student_id,
            'referral_code': referral_code
        }
        
        return self.update_profile(student_id, update_data, audit_context)

    def get_referrals(self, student_id: str) -> list[StudentProfile]:
        """
        Get students referred by a student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of referred student profiles
        """
        return self.profile_repo.find_referred_students(student_id)

    def get_referral_count(self, student_id: str) -> int:
        """
        Get referral count for a student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Number of referrals
        """
        return self.profile_repo.count_referrals(student_id)

    def get_top_referrers(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get top students by referral count.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of top referrers
            
        Returns:
            List of top referrers with counts
        """
        return self.profile_repo.get_top_referrers(hostel_id, limit)

    # ============================================================================
    # SEARCH AND FILTERING
    # ============================================================================

    def search_by_qualification(
        self,
        qualification: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Search profiles by qualification.
        
        Args:
            qualification: Qualification name
            hostel_id: Optional hostel filter
            
        Returns:
            List of matching profiles
        """
        return self.profile_repo.search_by_qualification(qualification, hostel_id)

    def search_by_field_of_study(
        self,
        field: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Search profiles by field of study.
        
        Args:
            field: Field of study
            hostel_id: Optional hostel filter
            
        Returns:
            List of matching profiles
        """
        return self.profile_repo.search_by_field_of_study(field, hostel_id)

    def get_scholarship_holders(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentProfile]:
        """
        Get scholarship holders.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of scholarship holders
        """
        return self.profile_repo.find_scholarship_holders(hostel_id)

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_average_profile_completeness(
        self,
        hostel_id: Optional[str] = None
    ) -> float:
        """
        Get average profile completeness.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Average completeness percentage
        """
        return self.profile_repo.get_average_profile_completeness(hostel_id)

    def get_completeness_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get profile completeness distribution.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Distribution by ranges
        """
        return self.profile_repo.count_profiles_by_completeness_range(hostel_id)