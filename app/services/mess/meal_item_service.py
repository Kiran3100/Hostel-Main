# app/services/mess/meal_item_service.py
"""
Meal Item Service

CRUD and orchestration for mess items:

- Meal items (MenuItem)
- Item categories
- Ingredients / allergens
- Popularity metrics
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.mess import (
    MealItemRepository,
    RecipeRepository,
    IngredientMasterRepository,
    ItemCategoryRepository,
    ItemAllergenRepository,
    ItemPopularityRepository,
)
from app.schemas.mess import (
    MenuItem,
    ItemCategory,
    AllergenInfo,
)
from app.core.exceptions import ValidationException


class MealItemService:
    """
    High-level service for meal items and related entities.
    """

    def __init__(
        self,
        item_repo: MealItemRepository,
        recipe_repo: RecipeRepository,
        ingredient_repo: IngredientMasterRepository,
        category_repo: ItemCategoryRepository,
        allergen_repo: ItemAllergenRepository,
        popularity_repo: ItemPopularityRepository,
    ) -> None:
        self.item_repo = item_repo
        self.recipe_repo = recipe_repo
        self.ingredient_repo = ingredient_repo
        self.category_repo = category_repo
        self.allergen_repo = allergen_repo
        self.popularity_repo = popularity_repo

    # -------------------------------------------------------------------------
    # Meal items
    # -------------------------------------------------------------------------

    def create_item(
        self,
        db: Session,
        hostel_id: UUID,
        data: MenuItem,
    ) -> MenuItem:
        payload = data.model_dump(exclude_none=True)
        payload["hostel_id"] = hostel_id
        obj = self.item_repo.create(db, payload)
        return MenuItem.model_validate(obj)

    def update_item(
        self,
        db: Session,
        item_id: UUID,
        data: MenuItem,
    ) -> MenuItem:
        item = self.item_repo.get_by_id(db, item_id)
        if not item:
            raise ValidationException("Menu item not found")

        obj = self.item_repo.update(
            db,
            item,
            data=data.model_dump(exclude_none=True),
        )
        return MenuItem.model_validate(obj)

    def delete_item(
        self,
        db: Session,
        item_id: UUID,
    ) -> None:
        item = self.item_repo.get_by_id(db, item_id)
        if not item:
            return
        self.item_repo.delete(db, item)

    def list_items_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[MenuItem]:
        objs = self.item_repo.get_by_hostel_id(db, hostel_id)
        return [MenuItem.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Categories
    # -------------------------------------------------------------------------

    def list_categories(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[ItemCategory]:
        objs = self.category_repo.get_by_hostel_id(db, hostel_id)
        return [ItemCategory.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Allergens
    # -------------------------------------------------------------------------

    def list_allergens_for_item(
        self,
        db: Session,
        item_id: UUID,
    ) -> List[AllergenInfo]:
        objs = self.allergen_repo.get_by_item_id(db, item_id)
        return [AllergenInfo.model_validate(o) for o in objs]