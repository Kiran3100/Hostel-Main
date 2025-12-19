# --- File: C:\Hostel-Main\app\repositories\mess\meal_item_repository.py ---

"""
Meal Item Repository Module.

Manages meal items, recipes, ingredients, categories, allergens,
and popularity tracking with advanced search and analytics.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.mess.meal_item import (
    IngredientMaster,
    ItemAllergen,
    ItemCategory,
    ItemPopularity,
    MealItem,
    Recipe,
)
from app.repositories.base.base_repository import BaseRepository


class MealItemRepository(BaseRepository[MealItem]):
    """
    Repository for managing meal items.
    
    Provides operations for meal item CRUD, search, filtering,
    and popularity tracking with dietary classification.
    """

    def __init__(self, db_session):
        """Initialize repository with MealItem model."""
        super().__init__(MealItem, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        active_only: bool = True,
        include_deleted: bool = False
    ) -> List[MealItem]:
        """
        Get meal items for a specific hostel.
        
        Args:
            hostel_id: Hostel identifier
            active_only: Only active items
            include_deleted: Include soft-deleted items
            
        Returns:
            List of meal items
        """
        query = select(MealItem).where(MealItem.hostel_id == hostel_id)
        
        if active_only:
            query = query.where(MealItem.is_active == True)
            
        if not include_deleted:
            query = query.where(MealItem.deleted_at.is_(None))
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def search_items(
        self,
        hostel_id: Optional[UUID] = None,
        search_term: Optional[str] = None,
        category: Optional[str] = None,
        dietary_flags: Optional[List[str]] = None,
        cuisine_type: Optional[str] = None,
        is_popular: Optional[bool] = None,
        is_seasonal: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True
    ) -> List[MealItem]:
        """
        Advanced search for meal items.
        
        Args:
            hostel_id: Hostel identifier (optional for global search)
            search_term: Text search in name/description
            category: Item category filter
            dietary_flags: List of dietary requirements
            cuisine_type: Cuisine type filter
            is_popular: Popular items filter
            is_seasonal: Seasonal items filter
            tags: Tag-based filtering
            active_only: Only active items
            
        Returns:
            List of matching meal items
        """
        query = select(MealItem)
        
        conditions = []
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
        
        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(
                or_(
                    MealItem.item_name.ilike(search_pattern),
                    MealItem.item_name_local.ilike(search_pattern),
                    MealItem.item_description.ilike(search_pattern)
                )
            )
        
        if category:
            conditions.append(MealItem.category == category)
            
        if cuisine_type:
            conditions.append(MealItem.cuisine_type == cuisine_type)
            
        if is_popular is not None:
            conditions.append(MealItem.is_popular == is_popular)
            
        if is_seasonal is not None:
            conditions.append(MealItem.is_seasonal == is_seasonal)
        
        # Dietary flags filtering
        if dietary_flags:
            for flag in dietary_flags:
                if flag == 'vegetarian':
                    conditions.append(MealItem.is_vegetarian == True)
                elif flag == 'vegan':
                    conditions.append(MealItem.is_vegan == True)
                elif flag == 'jain':
                    conditions.append(MealItem.is_jain == True)
                elif flag == 'gluten_free':
                    conditions.append(MealItem.is_gluten_free == True)
                elif flag == 'lactose_free':
                    conditions.append(MealItem.is_lactose_free == True)
        
        # Tags filtering
        if tags:
            conditions.append(MealItem.tags.overlap(tags))
        
        if active_only:
            conditions.append(MealItem.is_active == True)
            
        conditions.append(MealItem.deleted_at.is_(None))
        
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_dietary_requirements(
        self,
        hostel_id: Optional[UUID],
        is_vegetarian: bool = False,
        is_vegan: bool = False,
        is_jain: bool = False,
        is_gluten_free: bool = False,
        is_lactose_free: bool = False,
        exclude_allergens: Optional[List[str]] = None
    ) -> List[MealItem]:
        """
        Find items matching specific dietary requirements.
        
        Args:
            hostel_id: Hostel identifier
            is_vegetarian: Vegetarian requirement
            is_vegan: Vegan requirement
            is_jain: Jain requirement
            is_gluten_free: Gluten-free requirement
            is_lactose_free: Lactose-free requirement
            exclude_allergens: List of allergens to exclude
            
        Returns:
            List of suitable meal items
        """
        conditions = [
            MealItem.is_active == True,
            MealItem.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
        
        if is_vegetarian:
            conditions.append(MealItem.is_vegetarian == True)
        if is_vegan:
            conditions.append(MealItem.is_vegan == True)
        if is_jain:
            conditions.append(MealItem.is_jain == True)
        if is_gluten_free:
            conditions.append(MealItem.is_gluten_free == True)
        if is_lactose_free:
            conditions.append(MealItem.is_lactose_free == True)
            
        # Exclude allergens
        if exclude_allergens:
            allergen_map = {
                'dairy': MealItem.contains_dairy,
                'nuts': MealItem.contains_nuts,
                'soy': MealItem.contains_soy,
                'gluten': MealItem.contains_gluten,
                'eggs': MealItem.contains_eggs,
                'shellfish': MealItem.contains_shellfish,
            }
            
            for allergen in exclude_allergens:
                if allergen.lower() in allergen_map:
                    conditions.append(allergen_map[allergen.lower()] == False)
        
        query = select(MealItem).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_category(
        self,
        category: str,
        hostel_id: Optional[UUID] = None,
        active_only: bool = True
    ) -> List[MealItem]:
        """
        Find items by category.
        
        Args:
            category: Item category
            hostel_id: Hostel identifier (optional)
            active_only: Only active items
            
        Returns:
            List of items in category
        """
        conditions = [
            MealItem.category == category,
            MealItem.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
            
        if active_only:
            conditions.append(MealItem.is_active == True)
            
        query = select(MealItem).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_popular_items(
        self,
        hostel_id: Optional[UUID] = None,
        category: Optional[str] = None,
        limit: int = 10,
        min_rating: Optional[Decimal] = None
    ) -> List[MealItem]:
        """
        Get popular meal items.
        
        Args:
            hostel_id: Hostel identifier (optional)
            category: Category filter (optional)
            limit: Maximum number of results
            min_rating: Minimum average rating
            
        Returns:
            List of popular items sorted by popularity
        """
        conditions = [
            MealItem.is_active == True,
            MealItem.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
            
        if category:
            conditions.append(MealItem.category == category)
            
        if min_rating:
            conditions.append(MealItem.average_rating >= min_rating)
        
        query = (
            select(MealItem)
            .where(and_(*conditions))
            .order_by(desc(MealItem.popularity_score), desc(MealItem.average_rating))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_seasonal_items(
        self,
        hostel_id: Optional[UUID] = None,
        current_month: Optional[str] = None
    ) -> List[MealItem]:
        """
        Get seasonal items available for current month.
        
        Args:
            hostel_id: Hostel identifier (optional)
            current_month: Month name (optional, defaults to current)
            
        Returns:
            List of seasonal items
        """
        if not current_month:
            current_month = datetime.now().strftime('%B')
            
        conditions = [
            MealItem.is_seasonal == True,
            MealItem.is_active == True,
            MealItem.deleted_at.is_(None),
            MealItem.seasonal_months.any(current_month)
        ]
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
            
        query = select(MealItem).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_item_with_details(
        self,
        item_id: UUID
    ) -> Optional[MealItem]:
        """
        Get item with all related data loaded.
        
        Args:
            item_id: Item identifier
            
        Returns:
            MealItem with relationships loaded
        """
        query = (
            select(MealItem)
            .where(MealItem.id == item_id)
            .options(
                joinedload(MealItem.nutritional_info),
                selectinload(MealItem.allergens),
                selectinload(MealItem.recipes),
                joinedload(MealItem.popularity_data)
            )
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()

    async def find_items_with_allergen(
        self,
        allergen_type: str,
        hostel_id: Optional[UUID] = None,
        severity: Optional[str] = None
    ) -> List[MealItem]:
        """
        Find items containing specific allergen.
        
        Args:
            allergen_type: Type of allergen
            hostel_id: Hostel identifier (optional)
            severity: Allergen severity level (optional)
            
        Returns:
            List of items with allergen
        """
        conditions = [
            MealItem.is_active == True,
            MealItem.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
        
        # Check direct allergen flags
        allergen_flag_map = {
            'dairy': MealItem.contains_dairy,
            'nuts': MealItem.contains_nuts,
            'soy': MealItem.contains_soy,
            'gluten': MealItem.contains_gluten,
            'eggs': MealItem.contains_eggs,
            'shellfish': MealItem.contains_shellfish,
        }
        
        if allergen_type.lower() in allergen_flag_map:
            conditions.append(allergen_flag_map[allergen_type.lower()] == True)
        
        query = select(MealItem).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_items_by_spice_level(
        self,
        max_spice_level: int,
        hostel_id: Optional[UUID] = None
    ) -> List[MealItem]:
        """
        Get items within spice level range.
        
        Args:
            max_spice_level: Maximum spice level (0-5)
            hostel_id: Hostel identifier (optional)
            
        Returns:
            List of items within spice range
        """
        conditions = [
            MealItem.is_active == True,
            MealItem.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(MealItem.hostel_id == hostel_id)
            
        conditions.append(
            or_(
                MealItem.spice_level.is_(None),
                MealItem.spice_level <= max_spice_level
            )
        )
        
        query = select(MealItem).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_low_rated_items(
        self,
        hostel_id: UUID,
        max_rating: Decimal = Decimal('3.0'),
        min_ratings: int = 5
    ) -> List[MealItem]:
        """
        Get items with low ratings for review.
        
        Args:
            hostel_id: Hostel identifier
            max_rating: Maximum average rating threshold
            min_ratings: Minimum number of ratings required
            
        Returns:
            List of low-rated items
        """
        query = (
            select(MealItem)
            .where(MealItem.hostel_id == hostel_id)
            .where(MealItem.is_active == True)
            .where(MealItem.deleted_at.is_(None))
            .where(MealItem.average_rating.isnot(None))
            .where(MealItem.average_rating <= max_rating)
            .where(MealItem.total_ratings >= min_ratings)
            .order_by(MealItem.average_rating)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def update_item_statistics(
        self,
        item_id: UUID,
        new_rating: Optional[Decimal] = None
    ) -> Optional[MealItem]:
        """
        Update item statistics after rating/serving.
        
        Args:
            item_id: Item identifier
            new_rating: New rating to incorporate (optional)
            
        Returns:
            Updated MealItem
        """
        item = await self.get_by_id(item_id)
        if not item:
            return None
            
        if new_rating is not None:
            # Update average rating
            total_ratings = item.total_ratings
            current_avg = item.average_rating or Decimal('0.0')
            
            new_total = total_ratings + 1
            new_avg = ((current_avg * total_ratings) + new_rating) / new_total
            
            item.average_rating = new_avg
            item.total_ratings = new_total
            
        await self.db_session.commit()
        await self.db_session.refresh(item)
        
        return item

    async def bulk_update_availability(
        self,
        item_ids: List[UUID],
        is_available: bool,
        reason: Optional[str] = None
    ) -> int:
        """
        Bulk update item availability.
        
        Args:
            item_ids: List of item identifiers
            is_available: Availability status
            reason: Reason for change (optional)
            
        Returns:
            Number of items updated
        """
        from sqlalchemy import update
        
        stmt = (
            update(MealItem)
            .where(MealItem.id.in_(item_ids))
            .values(
                is_available=is_available,
                availability_reason=reason,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db_session.execute(stmt)
        await self.db_session.commit()
        
        return result.rowcount


class RecipeRepository(BaseRepository[Recipe]):
    """
    Repository for managing recipes.
    
    Handles recipe CRUD, version management, and ingredient tracking
    for meal items.
    """

    def __init__(self, db_session):
        """Initialize repository with Recipe model."""
        super().__init__(Recipe, db_session)

    async def find_by_meal_item(
        self,
        meal_item_id: UUID,
        active_only: bool = True
    ) -> List[Recipe]:
        """
        Get recipes for a meal item.
        
        Args:
            meal_item_id: MealItem identifier
            active_only: Only active recipes
            
        Returns:
            List of recipes
        """
        query = select(Recipe).where(Recipe.meal_item_id == meal_item_id)
        
        if active_only:
            query = query.where(Recipe.is_active == True)
            
        query = query.order_by(desc(Recipe.recipe_version))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_latest_version(
        self,
        meal_item_id: UUID
    ) -> Optional[Recipe]:
        """
        Get latest active recipe version.
        
        Args:
            meal_item_id: MealItem identifier
            
        Returns:
            Latest recipe version
        """
        query = (
            select(Recipe)
            .where(Recipe.meal_item_id == meal_item_id)
            .where(Recipe.is_active == True)
            .order_by(desc(Recipe.recipe_version))
            .limit(1)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_new_version(
        self,
        meal_item_id: UUID,
        recipe_data: Dict
    ) -> Recipe:
        """
        Create new recipe version.
        
        Args:
            meal_item_id: MealItem identifier
            recipe_data: Recipe data
            
        Returns:
            Newly created recipe
        """
        # Get current max version
        query = (
            select(func.max(Recipe.recipe_version))
            .where(Recipe.meal_item_id == meal_item_id)
        )
        
        result = await self.db_session.execute(query)
        max_version = result.scalar() or 0
        
        # Create new version
        new_recipe = Recipe(
            meal_item_id=meal_item_id,
            recipe_version=max_version + 1,
            **recipe_data
        )
        
        self.db_session.add(new_recipe)
        await self.db_session.commit()
        await self.db_session.refresh(new_recipe)
        
        return new_recipe

    async def find_by_difficulty(
        self,
        difficulty_level: str
    ) -> List[Recipe]:
        """
        Find recipes by difficulty level.
        
        Args:
            difficulty_level: Difficulty level
            
        Returns:
            List of matching recipes
        """
        query = (
            select(Recipe)
            .where(Recipe.difficulty_level == difficulty_level)
            .where(Recipe.is_active == True)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_preparation_time(
        self,
        max_minutes: int
    ) -> List[Recipe]:
        """
        Find quick recipes within time limit.
        
        Args:
            max_minutes: Maximum preparation time
            
        Returns:
            List of quick recipes
        """
        query = (
            select(Recipe)
            .where(Recipe.is_active == True)
            .where(Recipe.total_time_minutes.isnot(None))
            .where(Recipe.total_time_minutes <= max_minutes)
            .order_by(Recipe.total_time_minutes)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class IngredientMasterRepository(BaseRepository[IngredientMaster]):
    """
    Repository for managing master ingredient database.
    
    Handles ingredient CRUD, categorization, and seasonal
    availability tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with IngredientMaster model."""
        super().__init__(IngredientMaster, db_session)

    async def find_by_category(
        self,
        category: str,
        active_only: bool = True
    ) -> List[IngredientMaster]:
        """
        Find ingredients by category.
        
        Args:
            category: Ingredient category
            active_only: Only active ingredients
            
        Returns:
            List of ingredients
        """
        conditions = [IngredientMaster.category == category]
        
        if active_only:
            conditions.append(IngredientMaster.is_active == True)
            
        query = select(IngredientMaster).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def search_ingredients(
        self,
        search_term: str,
        category: Optional[str] = None,
        is_vegetarian: Optional[bool] = None,
        is_seasonal: Optional[bool] = None
    ) -> List[IngredientMaster]:
        """
        Search ingredients with filters.
        
        Args:
            search_term: Text search term
            category: Category filter (optional)
            is_vegetarian: Vegetarian filter (optional)
            is_seasonal: Seasonal filter (optional)
            
        Returns:
            List of matching ingredients
        """
        conditions = [IngredientMaster.is_active == True]
        
        # Text search
        search_pattern = f"%{search_term}%"
        conditions.append(
            or_(
                IngredientMaster.ingredient_name.ilike(search_pattern),
                IngredientMaster.ingredient_name_local.ilike(search_pattern)
            )
        )
        
        if category:
            conditions.append(IngredientMaster.category == category)
            
        if is_vegetarian is not None:
            conditions.append(IngredientMaster.is_vegetarian == is_vegetarian)
            
        if is_seasonal is not None:
            conditions.append(IngredientMaster.is_seasonal == is_seasonal)
            
        query = select(IngredientMaster).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_seasonal_ingredients(
        self,
        month: Optional[str] = None
    ) -> List[IngredientMaster]:
        """
        Get seasonally available ingredients.
        
        Args:
            month: Month name (optional, defaults to current)
            
        Returns:
            List of seasonal ingredients
        """
        if not month:
            month = datetime.now().strftime('%B')
            
        query = (
            select(IngredientMaster)
            .where(IngredientMaster.is_seasonal == True)
            .where(IngredientMaster.is_active == True)
            .where(IngredientMaster.available_months.any(month))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_with_allergens(
        self,
        allergen_types: List[str]
    ) -> List[IngredientMaster]:
        """
        Find ingredients containing allergens.
        
        Args:
            allergen_types: List of allergen types
            
        Returns:
            List of ingredients with allergens
        """
        query = (
            select(IngredientMaster)
            .where(IngredientMaster.is_active == True)
            .where(IngredientMaster.allergens.overlap(allergen_types))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class ItemCategoryRepository(BaseRepository[ItemCategory]):
    """
    Repository for managing item categories.
    
    Handles hierarchical category structure with parent-child
    relationships.
    """

    def __init__(self, db_session):
        """Initialize repository with ItemCategory model."""
        super().__init__(ItemCategory, db_session)

    async def get_root_categories(
        self,
        active_only: bool = True
    ) -> List[ItemCategory]:
        """
        Get top-level categories.
        
        Args:
            active_only: Only active categories
            
        Returns:
            List of root categories
        """
        conditions = [ItemCategory.parent_category_id.is_(None)]
        
        if active_only:
            conditions.append(ItemCategory.is_active == True)
            
        query = (
            select(ItemCategory)
            .where(and_(*conditions))
            .order_by(ItemCategory.display_order)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_subcategories(
        self,
        parent_id: UUID,
        active_only: bool = True
    ) -> List[ItemCategory]:
        """
        Get subcategories of a category.
        
        Args:
            parent_id: Parent category identifier
            active_only: Only active categories
            
        Returns:
            List of subcategories
        """
        conditions = [ItemCategory.parent_category_id == parent_id]
        
        if active_only:
            conditions.append(ItemCategory.is_active == True)
            
        query = (
            select(ItemCategory)
            .where(and_(*conditions))
            .order_by(ItemCategory.display_order)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_category_tree(
        self,
        active_only: bool = True
    ) -> List[ItemCategory]:
        """
        Get complete category hierarchy.
        
        Args:
            active_only: Only active categories
            
        Returns:
            List of all categories with relationships loaded
        """
        conditions = []
        
        if active_only:
            conditions.append(ItemCategory.is_active == True)
            
        query = (
            select(ItemCategory)
            .options(
                selectinload(ItemCategory.subcategories)
            )
            .order_by(ItemCategory.level, ItemCategory.display_order)
        )
        
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db_session.execute(query)
        return list(result.unique().scalars().all())


class ItemAllergenRepository(BaseRepository[ItemAllergen]):
    """
    Repository for managing item allergen information.
    
    Tracks detailed allergen data for meal items with
    severity and cross-contamination warnings.
    """

    def __init__(self, db_session):
        """Initialize repository with ItemAllergen model."""
        super().__init__(ItemAllergen, db_session)

    async def find_by_item(
        self,
        meal_item_id: UUID
    ) -> List[ItemAllergen]:
        """
        Get allergens for a meal item.
        
        Args:
            meal_item_id: MealItem identifier
            
        Returns:
            List of allergens
        """
        query = select(ItemAllergen).where(
            ItemAllergen.meal_item_id == meal_item_id
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_allergen_type(
        self,
        allergen_type: str,
        severity: Optional[str] = None
    ) -> List[ItemAllergen]:
        """
        Find items with specific allergen.
        
        Args:
            allergen_type: Type of allergen
            severity: Severity level filter (optional)
            
        Returns:
            List of allergen records
        """
        conditions = [ItemAllergen.allergen_type == allergen_type]
        
        if severity:
            conditions.append(ItemAllergen.severity == severity)
            
        query = select(ItemAllergen).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_cross_contamination_risks(
        self,
        allergen_type: str
    ) -> List[ItemAllergen]:
        """
        Find items with cross-contamination risk.
        
        Args:
            allergen_type: Type of allergen
            
        Returns:
            List of items with contamination risk
        """
        query = (
            select(ItemAllergen)
            .where(ItemAllergen.allergen_type == allergen_type)
            .where(ItemAllergen.is_cross_contamination_risk == True)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class ItemPopularityRepository(BaseRepository[ItemPopularity]):
    """
    Repository for tracking item popularity.
    
    Manages popularity metrics, ratings distribution, and
    trend analysis for meal items.
    """

    def __init__(self, db_session):
        """Initialize repository with ItemPopularity model."""
        super().__init__(ItemPopularity, db_session)

    async def get_by_item(
        self,
        meal_item_id: UUID
    ) -> Optional[ItemPopularity]:
        """
        Get popularity data for item.
        
        Args:
            meal_item_id: MealItem identifier
            
        Returns:
            ItemPopularity if found
        """
        query = select(ItemPopularity).where(
            ItemPopularity.meal_item_id == meal_item_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_top_rated_items(
        self,
        limit: int = 10,
        min_ratings: int = 5
    ) -> List[ItemPopularity]:
        """
        Get highest rated items.
        
        Args:
            limit: Maximum number of results
            min_ratings: Minimum number of ratings required
            
        Returns:
            List of top-rated items
        """
        query = (
            select(ItemPopularity)
            .where(ItemPopularity.total_ratings >= min_ratings)
            .order_by(desc(ItemPopularity.average_rating))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_most_popular_items(
        self,
        limit: int = 10
    ) -> List[ItemPopularity]:
        """
        Get most popular items by popularity score.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of most popular items
        """
        query = (
            select(ItemPopularity)
            .order_by(desc(ItemPopularity.popularity_score))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_trending_items(
        self,
        trend_direction: str = 'rising',
        limit: int = 10
    ) -> List[ItemPopularity]:
        """
        Get trending items.
        
        Args:
            trend_direction: Trend direction (rising/declining)
            limit: Maximum number of results
            
        Returns:
            List of trending items
        """
        query = (
            select(ItemPopularity)
            .where(ItemPopularity.trend_direction == trend_direction)
            .order_by(desc(ItemPopularity.trend_percentage))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def update_item_rating(
        self,
        meal_item_id: UUID,
        new_rating: int
    ) -> Optional[ItemPopularity]:
        """
        Update popularity with new rating.
        
        Args:
            meal_item_id: MealItem identifier
            new_rating: New rating value (1-5)
            
        Returns:
            Updated ItemPopularity
        """
        popularity = await self.get_by_item(meal_item_id)
        
        if not popularity:
            # Create new popularity record
            popularity = ItemPopularity(
                meal_item_id=meal_item_id,
                total_ratings=1,
                average_rating=Decimal(str(new_rating))
            )
            # Update rating counts
            setattr(popularity, f'rating_{new_rating}_count', 1)
            
            self.db_session.add(popularity)
        else:
            # Update existing
            total = popularity.total_ratings
            current_avg = popularity.average_rating
            
            new_total = total + 1
            new_avg = ((current_avg * total) + new_rating) / new_total
            
            popularity.average_rating = new_avg
            popularity.total_ratings = new_total
            
            # Update rating distribution
            rating_count_field = f'rating_{new_rating}_count'
            current_count = getattr(popularity, rating_count_field, 0)
            setattr(popularity, rating_count_field, current_count + 1)
            
            # Recalculate popularity score
            popularity.calculate_popularity_score()
            
        await self.db_session.commit()
        await self.db_session.refresh(popularity)
        
        return popularity

    async def record_serving(
        self,
        meal_item_id: UUID
    ) -> Optional[ItemPopularity]:
        """
        Record item being served.
        
        Args:
            meal_item_id: MealItem identifier
            
        Returns:
            Updated ItemPopularity
        """
        popularity = await self.get_by_item(meal_item_id)
        
        if not popularity:
            popularity = ItemPopularity(
                meal_item_id=meal_item_id,
                total_times_served=1,
                last_served_date=datetime.utcnow()
            )
            self.db_session.add(popularity)
        else:
            popularity.total_times_served += 1
            popularity.last_served_date = datetime.utcnow()
            
        await self.db_session.commit()
        await self.db_session.refresh(popularity)
        
        return popularity