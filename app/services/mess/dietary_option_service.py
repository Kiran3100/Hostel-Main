# app/services/mess/dietary_option_service.py
"""
Dietary Option Service

Manages hostel-level dietary options and student-level dietary preferences:

- Hostel dietary configuration (veg, vegan, Jain, allergy policies, etc.)
- Student dietary preferences and restrictions
- Allergen profiles
- Per-meal customizations
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException


class DietaryOptionService:
    """
    High-level orchestration for all dietary-related mess features.
    """

    def __init__(
        self,
        dietary_repo: DietaryOptionRepository,
        preference_repo: StudentDietaryPreferenceRepository,
        allergen_repo: AllergenProfileRepository,
        restriction_repo: DietaryRestrictionRepository,
        customization_repo: MealCustomizationRepository,
    ) -> None:
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
        """
        obj = self.dietary_repo.get_by_hostel_id(db, hostel_id)
        if not obj:
            # Provide an empty/default config rather than erroring
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
        return DietaryOptions.model_validate(obj)

    def set_hostel_dietary_options(
        self,
        db: Session,
        hostel_id: UUID,
        options: DietaryOptions,
    ) -> DietaryOptions:
        """
        Create or update hostel-level dietary options.
        """
        existing = self.dietary_repo.get_by_hostel_id(db, hostel_id)
        payload = options.model_dump(exclude_none=True)
        payload["hostel_id"] = hostel_id

        if existing:
            obj = self.dietary_repo.update(db, existing, payload)
        else:
            obj = self.dietary_repo.create(db, payload)

        return DietaryOptions.model_validate(obj)

    # -------------------------------------------------------------------------
    # Student-level preferences
    # -------------------------------------------------------------------------

    def get_student_preferences(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[StudentDietaryPreference]:
        obj = self.preference_repo.get_by_student_id(db, student_id)
        if not obj:
            return None
        return StudentDietaryPreference.model_validate(obj)

    def set_student_preferences(
        self,
        db: Session,
        student_id: UUID,
        prefs: StudentDietaryPreference,
    ) -> StudentDietaryPreference:
        existing = self.preference_repo.get_by_student_id(db, student_id)
        payload = prefs.model_dump(exclude_none=True)
        payload["student_id"] = student_id

        if existing:
            obj = self.preference_repo.update(db, existing, payload)
        else:
            obj = self.preference_repo.create(db, payload)

        return StudentDietaryPreference.model_validate(obj)

    # -------------------------------------------------------------------------
    # Allergen profiles & restrictions
    # -------------------------------------------------------------------------

    def get_allergen_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[AllergenInfo]:
        obj = self.allergen_repo.get_by_student_id(db, student_id)
        if not obj:
            return None
        return AllergenInfo.model_validate(obj)

    def set_allergen_profile(
        self,
        db: Session,
        student_id: UUID,
        profile: AllergenInfo,
    ) -> AllergenInfo:
        existing = self.allergen_repo.get_by_student_id(db, student_id)
        payload = profile.model_dump(exclude_none=True)
        payload["student_id"] = student_id

        if existing:
            obj = self.allergen_repo.update(db, existing, payload)
        else:
            obj = self.allergen_repo.create(db, payload)

        return AllergenInfo.model_validate(obj)

    def list_restrictions_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> List[DietaryRestriction]:
        objs = self.restriction_repo.get_by_student_id(db, student_id)
        return [DietaryRestriction.model_validate(o) for o in objs]

    def add_restriction(
        self,
        db: Session,
        student_id: UUID,
        restriction: DietaryRestriction,
    ) -> DietaryRestriction:
        payload = restriction.model_dump(exclude_none=True)
        payload["student_id"] = student_id
        obj = self.restriction_repo.create(db, payload)
        return DietaryRestriction.model_validate(obj)

    def remove_restriction(
        self,
        db: Session,
        restriction_id: UUID,
    ) -> None:
        obj = self.restriction_repo.get_by_id(db, restriction_id)
        if not obj:
            return
        self.restriction_repo.delete(db, obj)

    # -------------------------------------------------------------------------
    # Meal customizations
    # -------------------------------------------------------------------------

    def list_customizations_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> List[MealCustomization]:
        objs = self.customization_repo.get_by_student_id(db, student_id)
        return [MealCustomization.model_validate(o) for o in objs]

    def create_customization(
        self,
        db: Session,
        customization: MealCustomization,
    ) -> MealCustomization:
        obj = self.customization_repo.create(
            db,
            data=customization.model_dump(exclude_none=True),
        )
        return MealCustomization.model_validate(obj)

    def delete_customization(
        self,
        db: Session,
        customization_id: UUID,
    ) -> None:
        obj = self.customization_repo.get_by_id(db, customization_id)
        if not obj:
            return
        self.customization_repo.delete(db, obj)