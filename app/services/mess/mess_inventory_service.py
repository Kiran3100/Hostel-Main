# app/services/mess/mess_inventory_service.py
"""
Mess Inventory Service

High-level inventory operations for mess:
- Ingredient stock management
- Consumption tracking
- Purchase logging
"""

from __future__ import annotations

from typing import List
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.mess import IngredientMasterRepository
from app.core.exceptions import ValidationException


class MessInventoryService:
    """
    High-level service for mess inventory.

    Uses IngredientMaster as the central representation of stock.
    """

    def __init__(
        self,
        ingredient_repo: IngredientMasterRepository,
    ) -> None:
        self.ingredient_repo = ingredient_repo

    def list_ingredients_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[dict]:
        """
        Return list of ingredient rows (as raw dicts) for simplicity;
        you can add a dedicated schema if needed.
        """
        return self.ingredient_repo.get_by_hostel_id(db, hostel_id)

    def adjust_stock(
        self,
        db: Session,
        ingredient_id: UUID,
        delta_quantity: Decimal,
        reason: str,
    ) -> None:
        """
        Increase or decrease stock for an ingredient.
        """
        ingredient = self.ingredient_repo.get_by_id(db, ingredient_id)
        if not ingredient:
            raise ValidationException("Ingredient not found")

        self.ingredient_repo.adjust_stock(
            db=db,
            ingredient=ingredient,
            delta_quantity=delta_quantity,
            reason=reason,
        )