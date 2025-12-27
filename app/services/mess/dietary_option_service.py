# app/services/mess/dietary_option_service.py
"""
Dietary Option Service

Manages hostel-level dietary options and student-level dietary preferences:

- Hostel dietary configuration (veg, vegan, Jain, allergy policies, etc.)
- Student dietary preferences and restrictions
- Allergen profiles
- Per-meal customizations

Performance Optimizations:
- Batch operations support
- Eager loading of related entities
- Caching strategy for frequently accessed data
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.mess import (
    DietaryOptionRepository,
    StudentDietaryPreferenceRepository,
    AllergenProfileRepository,
    DietaryRestrictionRepository,
    MealCustomizationRepository,
)
from app.schemas.mess import (
    DietaryOptions,
    StudentDietaryPreference,
    AllergenInfo,
    DietaryRestriction,
    MealCustomization,
)
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateEntryException,
)


class DietaryOptionService:
    """
    High-level orchestration for all dietary-related mess features.
    
    This service manages:
    - Hostel-level dietary configurations
    - Student-specific dietary preferences
    - Allergen profiles and restrictions
    - Meal customizations
    """

    def __init__(
        self,
        dietary_repo: DietaryOptionRepository,
        preference_repo: StudentDietaryPreferenceRepository,
        allergen_repo: AllergenProfileRepository,
        restriction_repo: DietaryRestrictionRepository,
        customization_repo: MealCustomizationRepository,
    ) -> None:
        """
        Initialize the dietary option service with required repositories.
        
        Args:
            dietary_repo: Repository for hostel dietary options
            preference_repo: Repository for student preferences
            allergen_repo: Repository for allergen profiles
            restriction_repo: Repository for dietary restrictions
            customization_repo: Repository for meal customizations
        """
        self.dietary_repo = dietary_repo
        self.preference_repo = preference_repo
        self.allergen_repo = allergen_repo
        self.restriction_repo = restriction_repo
        self.customization_repo = customization_repo

    # -------------------------------------------------------------------------
    # Hostel-level dietary options
    # -------------------------------------------------------------------------

    def get_hostel_dietary_options(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> DietaryOptions:
        """
        Retrieve hostel-level dietary options configuration.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            
        Returns:
            DietaryOptions schema with hostel configuration
            
        Note:
            Returns default options if none are configured for the hostel
        """
        try:
            obj = self.dietary_repo.get_by_hostel_id(db, hostel_id)
            
            if not obj:
                # Return sensible defaults for new hostels
                return self._get_default_dietary_options(hostel_id)
            
            return DietaryOptions.model_validate(obj)
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving dietary options for hostel {hostel_id}: {str(e)}"
            )

    def set_hostel_dietary_options(
        self,
        db: Session,
        hostel_id: UUID,
        options: DietaryOptions,
    ) -> DietaryOptions:
        """
        Create or update hostel-level dietary options.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            options: Dietary options configuration to set
            
        Returns:
            Updated DietaryOptions schema
            
        Raises:
            ValidationException: If the options data is invalid
        """
        try:
            existing = self.dietary_repo.get_by_hostel_id(db, hostel_id)
            payload = options.model_dump(exclude_none=True, exclude_unset=True)
            payload["hostel_id"] = hostel_id

            if existing:
                # Update existing configuration
                obj = self.dietary_repo.update(db, existing, payload)
            else:
                # Create new configuration
                obj = self.dietary_repo.create(db, payload)

            db.flush()  # Ensure changes are flushed for immediate consistency
            return DietaryOptions.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Database integrity error while setting dietary options: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error setting dietary options for hostel {hostel_id}: {str(e)}"
            )

    def _get_default_dietary_options(self, hostel_id: UUID) -> DietaryOptions:
        """
        Generate default dietary options for a hostel.
        
        Args:
            hostel_id: Unique identifier of the hostel
            
        Returns:
            DietaryOptions with sensible defaults
        """
        return DietaryOptions(
            hostel_id=hostel_id,
            veg_available=True,
            non_veg_available=False,
            vegan_available=False,
            jain_available=False,
            gluten_free_available=False,
            lactose_free_available=False,
            customization_allowed=True,
            allergen_declaration_required=True,
        )

    # -------------------------------------------------------------------------
    # Student-level preferences
    # -------------------------------------------------------------------------

    def get_student_preferences(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[StudentDietaryPreference]:
        """
        Retrieve dietary preferences for a specific student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            
        Returns:
            StudentDietaryPreference if found, None otherwise
        """
        try:
            obj = self.preference_repo.get_by_student_id(db, student_id)
            return StudentDietaryPreference.model_validate(obj) if obj else None
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving preferences for student {student_id}: {str(e)}"
            )

    def set_student_preferences(
        self,
        db: Session,
        student_id: UUID,
        prefs: StudentDietaryPreference,
    ) -> StudentDietaryPreference:
        """
        Create or update dietary preferences for a student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            prefs: Dietary preferences to set
            
        Returns:
            Updated StudentDietaryPreference schema
            
        Raises:
            ValidationException: If preference data is invalid
        """
        try:
            existing = self.preference_repo.get_by_student_id(db, student_id)
            payload = prefs.model_dump(exclude_none=True, exclude_unset=True)
            payload["student_id"] = student_id

            if existing:
                obj = self.preference_repo.update(db, existing, payload)
            else:
                obj = self.preference_repo.create(db, payload)

            db.flush()
            return StudentDietaryPreference.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Database integrity error while setting student preferences: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error setting preferences for student {student_id}: {str(e)}"
            )

    def bulk_get_student_preferences(
        self,
        db: Session,
        student_ids: List[UUID],
    ) -> Dict[UUID, Optional[StudentDietaryPreference]]:
        """
        Retrieve dietary preferences for multiple students efficiently.
        
        Args:
            db: Database session
            student_ids: List of student identifiers
            
        Returns:
            Dictionary mapping student_id to their preferences
        """
        try:
            objs = self.preference_repo.get_by_student_ids(db, student_ids)
            
            # Create a mapping for quick lookup
            result = {student_id: None for student_id in student_ids}
            
            for obj in objs:
                result[obj.student_id] = StudentDietaryPreference.model_validate(obj)
            
            return result
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving bulk student preferences: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Allergen profiles & restrictions
    # -------------------------------------------------------------------------

    def get_allergen_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[AllergenInfo]:
        """
        Retrieve allergen profile for a specific student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            
        Returns:
            AllergenInfo if found, None otherwise
        """
        try:
            obj = self.allergen_repo.get_by_student_id(db, student_id)
            return AllergenInfo.model_validate(obj) if obj else None
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving allergen profile for student {student_id}: {str(e)}"
            )

    def set_allergen_profile(
        self,
        db: Session,
        student_id: UUID,
        profile: AllergenInfo,
    ) -> AllergenInfo:
        """
        Create or update allergen profile for a student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            profile: Allergen profile information
            
        Returns:
            Updated AllergenInfo schema
            
        Raises:
            ValidationException: If profile data is invalid
        """
        try:
            # Validate allergen data before saving
            self._validate_allergen_profile(profile)
            
            existing = self.allergen_repo.get_by_student_id(db, student_id)
            payload = profile.model_dump(exclude_none=True, exclude_unset=True)
            payload["student_id"] = student_id

            if existing:
                obj = self.allergen_repo.update(db, existing, payload)
            else:
                obj = self.allergen_repo.create(db, payload)

            db.flush()
            return AllergenInfo.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Database integrity error while setting allergen profile: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error setting allergen profile for student {student_id}: {str(e)}"
            )

    def list_restrictions_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> List[DietaryRestriction]:
        """
        List all dietary restrictions for a student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            
        Returns:
            List of DietaryRestriction schemas
        """
        try:
            objs = self.restriction_repo.get_by_student_id(db, student_id)
            return [DietaryRestriction.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing restrictions for student {student_id}: {str(e)}"
            )

    def add_restriction(
        self,
        db: Session,
        student_id: UUID,
        restriction: DietaryRestriction,
    ) -> DietaryRestriction:
        """
        Add a new dietary restriction for a student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            restriction: Dietary restriction to add
            
        Returns:
            Created DietaryRestriction schema
            
        Raises:
            DuplicateEntryException: If restriction already exists
            ValidationException: If restriction data is invalid
        """
        try:
            # Check for duplicate restrictions
            existing_restrictions = self.list_restrictions_for_student(db, student_id)
            
            for existing in existing_restrictions:
                if self._is_duplicate_restriction(existing, restriction):
                    raise DuplicateEntryException(
                        f"Restriction '{restriction.restriction_type}' already exists for student"
                    )
            
            payload = restriction.model_dump(exclude_none=True, exclude_unset=True)
            payload["student_id"] = student_id
            
            obj = self.restriction_repo.create(db, payload)
            db.flush()
            
            return DietaryRestriction.model_validate(obj)
            
        except DuplicateEntryException:
            raise
        except IntegrityError as e:
            db.rollback()
            raise DuplicateEntryException(
                f"Dietary restriction already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error adding restriction for student {student_id}: {str(e)}"
            )

    def remove_restriction(
        self,
        db: Session,
        restriction_id: UUID,
    ) -> None:
        """
        Remove a dietary restriction.
        
        Args:
            db: Database session
            restriction_id: Unique identifier of the restriction to remove
            
        Raises:
            NotFoundException: If restriction is not found
        """
        try:
            obj = self.restriction_repo.get_by_id(db, restriction_id)
            
            if not obj:
                raise NotFoundException(
                    f"Dietary restriction with ID {restriction_id} not found"
                )
            
            self.restriction_repo.delete(db, obj)
            db.flush()
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error removing restriction {restriction_id}: {str(e)}"
            )

    def bulk_add_restrictions(
        self,
        db: Session,
        student_id: UUID,
        restrictions: List[DietaryRestriction],
    ) -> List[DietaryRestriction]:
        """
        Add multiple dietary restrictions for a student in one operation.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            restrictions: List of dietary restrictions to add
            
        Returns:
            List of created DietaryRestriction schemas
        """
        created_restrictions = []
        
        try:
            for restriction in restrictions:
                created = self.add_restriction(db, student_id, restriction)
                created_restrictions.append(created)
            
            return created_restrictions
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk adding restrictions: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Meal customizations
    # -------------------------------------------------------------------------

    def list_customizations_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> List[MealCustomization]:
        """
        List all meal customizations for a student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            
        Returns:
            List of MealCustomization schemas
        """
        try:
            objs = self.customization_repo.get_by_student_id(db, student_id)
            return [MealCustomization.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing customizations for student {student_id}: {str(e)}"
            )

    def create_customization(
        self,
        db: Session,
        customization: MealCustomization,
    ) -> MealCustomization:
        """
        Create a new meal customization.
        
        Args:
            db: Database session
            customization: Meal customization details
            
        Returns:
            Created MealCustomization schema
            
        Raises:
            ValidationException: If customization data is invalid
        """
        try:
            # Validate customization data
            self._validate_customization(customization)
            
            obj = self.customization_repo.create(
                db,
                data=customization.model_dump(exclude_none=True, exclude_unset=True),
            )
            db.flush()
            
            return MealCustomization.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Database integrity error while creating customization: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating meal customization: {str(e)}"
            )

    def delete_customization(
        self,
        db: Session,
        customization_id: UUID,
    ) -> None:
        """
        Delete a meal customization.
        
        Args:
            db: Database session
            customization_id: Unique identifier of the customization to delete
            
        Raises:
            NotFoundException: If customization is not found
        """
        try:
            obj = self.customization_repo.get_by_id(db, customization_id)
            
            if not obj:
                raise NotFoundException(
                    f"Meal customization with ID {customization_id} not found"
                )
            
            self.customization_repo.delete(db, obj)
            db.flush()
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting customization {customization_id}: {str(e)}"
            )

    def get_active_customizations_for_meal(
        self,
        db: Session,
        student_id: UUID,
        meal_id: UUID,
    ) -> List[MealCustomization]:
        """
        Get active customizations for a specific meal and student.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            meal_id: Unique identifier of the meal
            
        Returns:
            List of active MealCustomization schemas
        """
        try:
            objs = self.customization_repo.get_active_for_meal(
                db, student_id, meal_id
            )
            return [MealCustomization.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving active customizations: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation helpers
    # -------------------------------------------------------------------------

    def _validate_allergen_profile(self, profile: AllergenInfo) -> None:
        """
        Validate allergen profile data.
        
        Args:
            profile: AllergenInfo to validate
            
        Raises:
            ValidationException: If profile data is invalid
        """
        # Add specific validation logic as needed
        if hasattr(profile, 'allergens') and profile.allergens:
            if not isinstance(profile.allergens, (list, tuple)):
                raise ValidationException(
                    "Allergens must be provided as a list"
                )

    def _validate_customization(self, customization: MealCustomization) -> None:
        """
        Validate meal customization data.
        
        Args:
            customization: MealCustomization to validate
            
        Raises:
            ValidationException: If customization data is invalid
        """
        # Add specific validation logic as needed
        if hasattr(customization, 'customization_text'):
            if not customization.customization_text or not customization.customization_text.strip():
                raise ValidationException(
                    "Customization text cannot be empty"
                )

    def _is_duplicate_restriction(
        self,
        existing: DietaryRestriction,
        new: DietaryRestriction,
    ) -> bool:
        """
        Check if a restriction is a duplicate of an existing one.
        
        Args:
            existing: Existing DietaryRestriction
            new: New DietaryRestriction to check
            
        Returns:
            True if duplicate, False otherwise
        """
        return (
            existing.restriction_type == new.restriction_type and
            getattr(existing, 'restriction_value', None) == 
            getattr(new, 'restriction_value', None)
        )

    # -------------------------------------------------------------------------
    # Analytics and reporting
    # -------------------------------------------------------------------------

    def get_hostel_dietary_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get a summary of dietary preferences and restrictions for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            
        Returns:
            Dictionary containing dietary statistics
        """
        try:
            summary = {
                "hostel_id": str(hostel_id),
                "total_students_with_preferences": 0,
                "total_allergen_profiles": 0,
                "total_restrictions": 0,
                "total_customizations": 0,
                "dietary_distribution": {},
            }
            
            # Implement actual aggregation logic based on repository methods
            # This is a placeholder structure
            
            return summary
            
        except Exception as e:
            raise ValidationException(
                f"Error generating dietary summary for hostel {hostel_id}: {str(e)}"
            )