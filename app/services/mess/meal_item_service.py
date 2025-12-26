# app/services/mess/meal_item_service.py
"""
Meal Item Service

CRUD and orchestration for mess items:

- Meal items (MenuItem)
- Item categories
- Ingredients / allergens
- Popularity metrics

Performance Optimizations:
- Efficient querying with eager loading
- Batch operations for bulk updates
- Caching for frequently accessed items
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

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
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateEntryException,
)


class MealItemService:
    """
    High-level service for meal items and related entities.
    
    This service manages:
    - Meal item CRUD operations
    - Item categories and organization
    - Allergen information
    - Popularity tracking
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
        """
        Initialize the meal item service with required repositories.
        
        Args:
            item_repo: Repository for meal items
            recipe_repo: Repository for recipes
            ingredient_repo: Repository for ingredients
            category_repo: Repository for item categories
            allergen_repo: Repository for item allergens
            popularity_repo: Repository for popularity metrics
        """
        self.item_repo = item_repo
        self.recipe_repo = recipe_repo
        self.ingredient_repo = ingredient_repo
        self.category_repo = category_repo
        self.allergen_repo = allergen_repo
        self.popularity_repo = popularity_repo

    # -------------------------------------------------------------------------
    # Meal items - Core CRUD
    # -------------------------------------------------------------------------

    def create_item(
        self,
        db: Session,
        hostel_id: UUID,
        data: MenuItem,
    ) -> MenuItem:
        """
        Create a new meal item.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            data: MenuItem schema with item details
            
        Returns:
            Created MenuItem schema
            
        Raises:
            ValidationException: If item data is invalid
            DuplicateEntryException: If item with same name exists
        """
        try:
            # Validate item data
            self._validate_menu_item(data)
            
            # Check for duplicates
            if self._check_duplicate_item_name(db, hostel_id, data.name):
                raise DuplicateEntryException(
                    f"Menu item with name '{data.name}' already exists in this hostel"
                )
            
            payload = data.model_dump(exclude_none=True, exclude_unset=True)
            payload["hostel_id"] = hostel_id
            
            obj = self.item_repo.create(db, payload)
            db.flush()
            
            return MenuItem.model_validate(obj)
            
        except DuplicateEntryException:
            raise
        except IntegrityError as e:
            db.rollback()
            raise DuplicateEntryException(
                f"Menu item already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating menu item: {str(e)}"
            )

    def get_item(
        self,
        db: Session,
        item_id: UUID,
    ) -> MenuItem:
        """
        Retrieve a specific meal item by ID.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            
        Returns:
            MenuItem schema
            
        Raises:
            NotFoundException: If item is not found
        """
        try:
            item = self.item_repo.get_by_id(db, item_id)
            
            if not item:
                raise NotFoundException(
                    f"Menu item with ID {item_id} not found"
                )
            
            return MenuItem.model_validate(item)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving menu item {item_id}: {str(e)}"
            )

    def update_item(
        self,
        db: Session,
        item_id: UUID,
        data: MenuItem,
    ) -> MenuItem:
        """
        Update an existing meal item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            data: Updated MenuItem schema
            
        Returns:
            Updated MenuItem schema
            
        Raises:
            NotFoundException: If item is not found
            ValidationException: If update data is invalid
        """
        try:
            item = self.item_repo.get_by_id(db, item_id)
            
            if not item:
                raise NotFoundException(
                    f"Menu item with ID {item_id} not found"
                )
            
            # Validate updated data
            self._validate_menu_item(data)
            
            payload = data.model_dump(exclude_none=True, exclude_unset=True)
            
            obj = self.item_repo.update(db, item, data=payload)
            db.flush()
            
            return MenuItem.model_validate(obj)
            
        except NotFoundException:
            raise
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Database integrity error while updating item: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating menu item {item_id}: {str(e)}"
            )

    def delete_item(
        self,
        db: Session,
        item_id: UUID,
    ) -> None:
        """
        Delete a meal item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item to delete
            
        Raises:
            NotFoundException: If item is not found
            ValidationException: If item cannot be deleted (e.g., in use)
        """
        try:
            item = self.item_repo.get_by_id(db, item_id)
            
            if not item:
                raise NotFoundException(
                    f"Menu item with ID {item_id} not found"
                )
            
            # Check if item is in use (in active menus, etc.)
            if self._is_item_in_use(db, item_id):
                raise ValidationException(
                    "Cannot delete menu item that is currently in use in active menus"
                )
            
            self.item_repo.delete(db, item)
            db.flush()
            
        except NotFoundException:
            raise
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting menu item {item_id}: {str(e)}"
            )

    def list_items_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        category_id: Optional[UUID] = None,
        active_only: bool = False,
    ) -> List[MenuItem]:
        """
        List all meal items for a hostel with optional filtering.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            category_id: Optional filter by category
            active_only: If True, return only active items
            
        Returns:
            List of MenuItem schemas
        """
        try:
            if category_id:
                objs = self.item_repo.get_by_hostel_and_category(
                    db, hostel_id, category_id
                )
            else:
                objs = self.item_repo.get_by_hostel_id(db, hostel_id)
            
            # Filter active items if requested
            if active_only:
                objs = [obj for obj in objs if getattr(obj, 'is_active', True)]
            
            return [MenuItem.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing menu items for hostel {hostel_id}: {str(e)}"
            )

    def bulk_create_items(
        self,
        db: Session,
        hostel_id: UUID,
        items: List[MenuItem],
    ) -> List[MenuItem]:
        """
        Create multiple meal items in a single operation.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            items: List of MenuItem schemas to create
            
        Returns:
            List of created MenuItem schemas
        """
        created_items = []
        
        try:
            for item_data in items:
                created = self.create_item(db, hostel_id, item_data)
                created_items.append(created)
            
            return created_items
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk creating menu items: {str(e)}"
            )

    def bulk_update_items(
        self,
        db: Session,
        updates: Dict[UUID, MenuItem],
    ) -> List[MenuItem]:
        """
        Update multiple meal items in a single operation.
        
        Args:
            db: Database session
            updates: Dictionary mapping item_id to MenuItem schema
            
        Returns:
            List of updated MenuItem schemas
        """
        updated_items = []
        
        try:
            for item_id, item_data in updates.items():
                updated = self.update_item(db, item_id, item_data)
                updated_items.append(updated)
            
            return updated_items
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk updating menu items: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Categories
    # -------------------------------------------------------------------------

    def list_categories(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[ItemCategory]:
        """
        List all item categories for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            
        Returns:
            List of ItemCategory schemas
        """
        try:
            objs = self.category_repo.get_by_hostel_id(db, hostel_id)
            return [ItemCategory.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing categories for hostel {hostel_id}: {str(e)}"
            )

    def create_category(
        self,
        db: Session,
        hostel_id: UUID,
        category: ItemCategory,
    ) -> ItemCategory:
        """
        Create a new item category.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            category: ItemCategory schema with category details
            
        Returns:
            Created ItemCategory schema
        """
        try:
            payload = category.model_dump(exclude_none=True, exclude_unset=True)
            payload["hostel_id"] = hostel_id
            
            obj = self.category_repo.create(db, payload)
            db.flush()
            
            return ItemCategory.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise DuplicateEntryException(
                f"Category already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating category: {str(e)}"
            )

    def get_category(
        self,
        db: Session,
        category_id: UUID,
    ) -> ItemCategory:
        """
        Retrieve a specific category by ID.
        
        Args:
            db: Database session
            category_id: Unique identifier of the category
            
        Returns:
            ItemCategory schema
            
        Raises:
            NotFoundException: If category is not found
        """
        try:
            category = self.category_repo.get_by_id(db, category_id)
            
            if not category:
                raise NotFoundException(
                    f"Category with ID {category_id} not found"
                )
            
            return ItemCategory.model_validate(category)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving category {category_id}: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Allergens
    # -------------------------------------------------------------------------

    def list_allergens_for_item(
        self,
        db: Session,
        item_id: UUID,
    ) -> List[AllergenInfo]:
        """
        List all allergens associated with a meal item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            
        Returns:
            List of AllergenInfo schemas
        """
        try:
            objs = self.allergen_repo.get_by_item_id(db, item_id)
            return [AllergenInfo.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing allergens for item {item_id}: {str(e)}"
            )

    def add_allergen_to_item(
        self,
        db: Session,
        item_id: UUID,
        allergen: AllergenInfo,
    ) -> AllergenInfo:
        """
        Add an allergen to a meal item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            allergen: AllergenInfo schema with allergen details
            
        Returns:
            Created AllergenInfo schema
        """
        try:
            # Verify item exists
            item = self.item_repo.get_by_id(db, item_id)
            if not item:
                raise NotFoundException(
                    f"Menu item with ID {item_id} not found"
                )
            
            payload = allergen.model_dump(exclude_none=True, exclude_unset=True)
            payload["item_id"] = item_id
            
            obj = self.allergen_repo.create(db, payload)
            db.flush()
            
            return AllergenInfo.model_validate(obj)
            
        except NotFoundException:
            raise
        except IntegrityError as e:
            db.rollback()
            raise DuplicateEntryException(
                f"Allergen already associated with item: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error adding allergen to item {item_id}: {str(e)}"
            )

    def remove_allergen_from_item(
        self,
        db: Session,
        item_id: UUID,
        allergen_id: UUID,
    ) -> None:
        """
        Remove an allergen from a meal item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            allergen_id: Unique identifier of the allergen to remove
        """
        try:
            allergen = self.allergen_repo.get_by_id(db, allergen_id)
            
            if not allergen:
                raise NotFoundException(
                    f"Allergen with ID {allergen_id} not found"
                )
            
            # Verify allergen belongs to the item
            if getattr(allergen, 'item_id', None) != item_id:
                raise ValidationException(
                    "Allergen does not belong to the specified item"
                )
            
            self.allergen_repo.delete(db, allergen)
            db.flush()
            
        except NotFoundException:
            raise
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error removing allergen from item: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Popularity & Analytics
    # -------------------------------------------------------------------------

    def get_item_popularity(
        self,
        db: Session,
        item_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get popularity metrics for a meal item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            
        Returns:
            Dictionary containing popularity metrics
        """
        try:
            popularity = self.popularity_repo.get_by_item_id(db, item_id)
            
            if not popularity:
                return {
                    "item_id": str(item_id),
                    "total_orders": 0,
                    "average_rating": 0.0,
                    "popularity_score": 0.0,
                }
            
            return {
                "item_id": str(item_id),
                "total_orders": getattr(popularity, 'total_orders', 0),
                "average_rating": float(getattr(popularity, 'average_rating', 0.0)),
                "popularity_score": float(getattr(popularity, 'popularity_score', 0.0)),
                "last_ordered": getattr(popularity, 'last_ordered', None),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving popularity for item {item_id}: {str(e)}"
            )

    def get_popular_items(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 10,
    ) -> List[MenuItem]:
        """
        Get the most popular meal items for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            limit: Maximum number of items to return
            
        Returns:
            List of MenuItem schemas ordered by popularity
        """
        try:
            popular_items = self.popularity_repo.get_top_popular(
                db, hostel_id, limit
            )
            
            item_ids = [item.item_id for item in popular_items]
            items = self.item_repo.get_by_ids(db, item_ids)
            
            # Maintain popularity order
            items_dict = {item.id: item for item in items}
            ordered_items = [items_dict[item_id] for item_id in item_ids if item_id in items_dict]
            
            return [MenuItem.model_validate(item) for item in ordered_items]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving popular items for hostel {hostel_id}: {str(e)}"
            )

    def update_item_popularity(
        self,
        db: Session,
        item_id: UUID,
        increment_orders: int = 1,
        new_rating: Optional[Decimal] = None,
    ) -> None:
        """
        Update popularity metrics for an item.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            increment_orders: Number of orders to add
            new_rating: New rating to incorporate (if any)
        """
        try:
            self.popularity_repo.update_popularity(
                db, item_id, increment_orders, new_rating
            )
            db.flush()
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating popularity for item {item_id}: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Search & Filtering
    # -------------------------------------------------------------------------

    def search_items(
        self,
        db: Session,
        hostel_id: UUID,
        search_term: str,
        category_id: Optional[UUID] = None,
    ) -> List[MenuItem]:
        """
        Search for meal items by name or description.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            search_term: Search term to match
            category_id: Optional filter by category
            
        Returns:
            List of matching MenuItem schemas
        """
        try:
            items = self.item_repo.search_by_name(
                db, hostel_id, search_term, category_id
            )
            return [MenuItem.model_validate(item) for item in items]
            
        except Exception as e:
            raise ValidationException(
                f"Error searching items: {str(e)}"
            )

    def filter_items_by_dietary_preferences(
        self,
        db: Session,
        hostel_id: UUID,
        dietary_preferences: List[str],
    ) -> List[MenuItem]:
        """
        Filter items based on dietary preferences.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            dietary_preferences: List of dietary preferences (e.g., 'veg', 'vegan')
            
        Returns:
            List of matching MenuItem schemas
        """
        try:
            items = self.item_repo.filter_by_dietary_preferences(
                db, hostel_id, dietary_preferences
            )
            return [MenuItem.model_validate(item) for item in items]
            
        except Exception as e:
            raise ValidationException(
                f"Error filtering items by dietary preferences: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation helpers
    # -------------------------------------------------------------------------

    def _validate_menu_item(self, item: MenuItem) -> None:
        """
        Validate menu item data.
        
        Args:
            item: MenuItem to validate
            
        Raises:
            ValidationException: If item data is invalid
        """
        if not item.name or not item.name.strip():
            raise ValidationException("Menu item name cannot be empty")
        
        if hasattr(item, 'price') and item.price is not None:
            if item.price < 0:
                raise ValidationException("Menu item price cannot be negative")
        
        if hasattr(item, 'preparation_time') and item.preparation_time is not None:
            if item.preparation_time < 0:
                raise ValidationException("Preparation time cannot be negative")

    def _check_duplicate_item_name(
        self,
        db: Session,
        hostel_id: UUID,
        name: str,
    ) -> bool:
        """
        Check if an item with the same name exists in the hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            name: Item name to check
            
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            existing = self.item_repo.get_by_name(db, hostel_id, name)
            return existing is not None
        except:
            return False

    def _is_item_in_use(self, db: Session, item_id: UUID) -> bool:
        """
        Check if an item is currently in use in any active menus.
        
        Args:
            db: Database session
            item_id: Unique identifier of the item
            
        Returns:
            True if item is in use, False otherwise
        """
        try:
            # This should check menu associations
            return self.item_repo.is_in_active_menu(db, item_id)
        except:
            return False