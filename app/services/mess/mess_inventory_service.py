# app/services/mess/mess_inventory_service.py
"""
Mess Inventory Service

High-level inventory operations for mess:
- Ingredient stock management
- Consumption tracking
- Purchase logging and forecasting
- Stock alerts and notifications

Performance Optimizations:
- Batch stock updates
- Efficient stock tracking
- Automated reorder point calculations
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.mess import IngredientMasterRepository
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessLogicException,
)


class MessInventoryService:
    """
    High-level service for mess inventory management.

    This service manages:
    - Ingredient stock levels
    - Stock adjustments (purchases, consumption, waste)
    - Low stock alerts
    - Inventory forecasting
    - Stock valuation
    """

    # Constants
    LOW_STOCK_THRESHOLD = Decimal('0.2')  # 20% of max stock
    CRITICAL_STOCK_THRESHOLD = Decimal('0.1')  # 10% of max stock

    def __init__(
        self,
        ingredient_repo: IngredientMasterRepository,
    ) -> None:
        """
        Initialize the mess inventory service.
        
        Args:
            ingredient_repo: Repository for ingredient operations
        """
        self.ingredient_repo = ingredient_repo

    # -------------------------------------------------------------------------
    # Ingredient Management
    # -------------------------------------------------------------------------

    def list_ingredients_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        category: Optional[str] = None,
        low_stock_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List all ingredients for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            category: Optional filter by category
            low_stock_only: If True, return only low stock items
            
        Returns:
            List of ingredient dictionaries with stock information
        """
        try:
            ingredients = self.ingredient_repo.get_by_hostel_id(db, hostel_id)
            
            # Apply filters
            if category:
                ingredients = [
                    ing for ing in ingredients
                    if getattr(ing, 'category', None) == category
                ]
            
            if low_stock_only:
                ingredients = [
                    ing for ing in ingredients
                    if self._is_low_stock(ing)
                ]
            
            return [self._format_ingredient_data(ing) for ing in ingredients]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing ingredients for hostel {hostel_id}: {str(e)}"
            )

    def get_ingredient(
        self,
        db: Session,
        ingredient_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific ingredient.
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            
        Returns:
            Dictionary with ingredient details
            
        Raises:
            NotFoundException: If ingredient not found
        """
        try:
            ingredient = self.ingredient_repo.get_by_id(db, ingredient_id)
            
            if not ingredient:
                raise NotFoundException(
                    f"Ingredient with ID {ingredient_id} not found"
                )
            
            return self._format_ingredient_data(ingredient)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving ingredient: {str(e)}"
            )

    def create_ingredient(
        self,
        db: Session,
        hostel_id: UUID,
        ingredient_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new ingredient entry.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            ingredient_data: Ingredient details
            
        Returns:
            Created ingredient data
        """
        try:
            # Validate ingredient data
            self._validate_ingredient_data(ingredient_data)
            
            ingredient_data["hostel_id"] = hostel_id
            ingredient_data["created_at"] = datetime.utcnow()
            
            obj = self.ingredient_repo.create(db, ingredient_data)
            db.flush()
            
            return self._format_ingredient_data(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Ingredient already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating ingredient: {str(e)}"
            )

    def update_ingredient(
        self,
        db: Session,
        ingredient_id: UUID,
        ingredient_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing ingredient.
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            ingredient_data: Updated ingredient details
            
        Returns:
            Updated ingredient data
        """
        try:
            ingredient = self.ingredient_repo.get_by_id(db, ingredient_id)
            
            if not ingredient:
                raise NotFoundException(
                    f"Ingredient with ID {ingredient_id} not found"
                )
            
            self._validate_ingredient_data(ingredient_data)
            
            ingredient_data["updated_at"] = datetime.utcnow()
            
            obj = self.ingredient_repo.update(db, ingredient, ingredient_data)
            db.flush()
            
            return self._format_ingredient_data(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating ingredient: {str(e)}"
            )

    def delete_ingredient(
        self,
        db: Session,
        ingredient_id: UUID,
    ) -> None:
        """
        Delete an ingredient (soft delete).
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
        """
        try:
            ingredient = self.ingredient_repo.get_by_id(db, ingredient_id)
            
            if not ingredient:
                raise NotFoundException(
                    f"Ingredient with ID {ingredient_id} not found"
                )
            
            # Check if ingredient is in use
            if self._is_ingredient_in_use(db, ingredient_id):
                raise BusinessLogicException(
                    "Cannot delete ingredient that is currently in use"
                )
            
            self.ingredient_repo.delete(db, ingredient)
            db.flush()
            
        except (NotFoundException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting ingredient: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Stock Management
    # -------------------------------------------------------------------------

    def adjust_stock(
        self,
        db: Session,
        ingredient_id: UUID,
        delta_quantity: Decimal,
        reason: str,
        reference_id: Optional[UUID] = None,
        performed_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Adjust stock for an ingredient.
        
        This method handles both increases (purchases) and decreases (consumption, waste).
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            delta_quantity: Quantity to add (positive) or subtract (negative)
            reason: Reason for adjustment (e.g., 'purchase', 'consumption', 'waste')
            reference_id: Optional reference to related entity (e.g., purchase order)
            performed_by: Optional user ID who performed the adjustment
            
        Returns:
            Updated ingredient data
            
        Raises:
            NotFoundException: If ingredient not found
            ValidationException: If adjustment would result in negative stock
        """
        try:
            ingredient = self.ingredient_repo.get_by_id(db, ingredient_id)
            
            if not ingredient:
                raise NotFoundException(
                    f"Ingredient with ID {ingredient_id} not found"
                )
            
            # Validate adjustment
            self._validate_stock_adjustment(ingredient, delta_quantity)
            
            # Perform adjustment
            obj = self.ingredient_repo.adjust_stock(
                db=db,
                ingredient=ingredient,
                delta_quantity=delta_quantity,
                reason=reason,
            )
            
            # Log the transaction
            self._log_stock_transaction(
                db,
                ingredient_id,
                delta_quantity,
                reason,
                reference_id,
                performed_by,
            )
            
            db.flush()
            
            # Check for low stock and trigger alerts if needed
            self._check_and_trigger_stock_alerts(db, obj)
            
            return self._format_ingredient_data(obj)
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error adjusting stock for ingredient {ingredient_id}: {str(e)}"
            )

    def bulk_adjust_stock(
        self,
        db: Session,
        adjustments: List[Dict[str, Any]],
        reason: str,
        performed_by: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Adjust stock for multiple ingredients in a single transaction.
        
        Args:
            db: Database session
            adjustments: List of adjustment dictionaries with ingredient_id and delta_quantity
            reason: Common reason for all adjustments
            performed_by: Optional user ID who performed the adjustments
            
        Returns:
            List of updated ingredient data
        """
        results = []
        
        try:
            for adjustment in adjustments:
                ingredient_id = adjustment.get('ingredient_id')
                delta_quantity = Decimal(str(adjustment.get('delta_quantity', 0)))
                
                result = self.adjust_stock(
                    db,
                    ingredient_id,
                    delta_quantity,
                    reason,
                    performed_by=performed_by,
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk stock adjustment: {str(e)}"
            )

    def record_purchase(
        self,
        db: Session,
        ingredient_id: UUID,
        quantity: Decimal,
        unit_price: Decimal,
        supplier: Optional[str] = None,
        invoice_number: Optional[str] = None,
        performed_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Record a purchase of ingredient stock.
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            quantity: Quantity purchased
            unit_price: Price per unit
            supplier: Optional supplier name
            invoice_number: Optional invoice reference
            performed_by: Optional user ID who recorded the purchase
            
        Returns:
            Updated ingredient data with purchase details
        """
        try:
            if quantity <= 0:
                raise ValidationException("Purchase quantity must be positive")
            
            if unit_price < 0:
                raise ValidationException("Unit price cannot be negative")
            
            # Adjust stock
            result = self.adjust_stock(
                db,
                ingredient_id,
                quantity,
                "purchase",
                performed_by=performed_by,
            )
            
            # Record purchase details
            purchase_data = {
                "ingredient_id": ingredient_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_cost": quantity * unit_price,
                "supplier": supplier,
                "invoice_number": invoice_number,
                "purchase_date": date.today(),
                "recorded_by": performed_by,
            }
            
            self.ingredient_repo.record_purchase(db, purchase_data)
            db.flush()
            
            result["last_purchase"] = purchase_data
            
            return result
            
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error recording purchase: {str(e)}"
            )

    def record_consumption(
        self,
        db: Session,
        ingredient_id: UUID,
        quantity: Decimal,
        menu_id: Optional[UUID] = None,
        recorded_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Record consumption of ingredient stock.
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            quantity: Quantity consumed
            menu_id: Optional menu reference
            recorded_by: Optional user ID who recorded the consumption
            
        Returns:
            Updated ingredient data
        """
        try:
            if quantity <= 0:
                raise ValidationException("Consumption quantity must be positive")
            
            # Adjust stock (negative delta for consumption)
            result = self.adjust_stock(
                db,
                ingredient_id,
                -quantity,
                "consumption",
                reference_id=menu_id,
                performed_by=recorded_by,
            )
            
            return result
            
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error recording consumption: {str(e)}"
            )

    def record_waste(
        self,
        db: Session,
        ingredient_id: UUID,
        quantity: Decimal,
        waste_reason: str,
        recorded_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Record waste/spoilage of ingredient stock.
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            quantity: Quantity wasted
            waste_reason: Reason for waste (e.g., 'spoilage', 'expiry')
            recorded_by: Optional user ID who recorded the waste
            
        Returns:
            Updated ingredient data
        """
        try:
            if quantity <= 0:
                raise ValidationException("Waste quantity must be positive")
            
            if not waste_reason or not waste_reason.strip():
                raise ValidationException("Waste reason is required")
            
            # Adjust stock (negative delta for waste)
            result = self.adjust_stock(
                db,
                ingredient_id,
                -quantity,
                f"waste: {waste_reason}",
                performed_by=recorded_by,
            )
            
            # Log waste for analytics
            self._log_waste_event(db, ingredient_id, quantity, waste_reason)
            
            return result
            
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error recording waste: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Stock Alerts & Monitoring
    # -------------------------------------------------------------------------

    def get_low_stock_items(
        self,
        db: Session,
        hostel_id: UUID,
        threshold: Optional[Decimal] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all ingredients with low stock levels.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            threshold: Optional custom threshold (percentage)
            
        Returns:
            List of low stock ingredients
        """
        try:
            threshold = threshold or self.LOW_STOCK_THRESHOLD
            ingredients = self.ingredient_repo.get_low_stock(db, hostel_id, threshold)
            
            return [self._format_ingredient_data(ing) for ing in ingredients]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving low stock items: {str(e)}"
            )

    def get_critical_stock_items(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get ingredients with critically low stock levels.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            
        Returns:
            List of critical stock ingredients
        """
        try:
            ingredients = self.ingredient_repo.get_low_stock(
                db, hostel_id, self.CRITICAL_STOCK_THRESHOLD
            )
            
            return [self._format_ingredient_data(ing) for ing in ingredients]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving critical stock items: {str(e)}"
            )

    def get_expiring_items(
        self,
        db: Session,
        hostel_id: UUID,
        days_ahead: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Get ingredients that are expiring soon.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring ingredients
        """
        try:
            expiry_date = date.today() + timedelta(days=days_ahead)
            ingredients = self.ingredient_repo.get_expiring(db, hostel_id, expiry_date)
            
            return [self._format_ingredient_data(ing) for ing in ingredients]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving expiring items: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Analytics & Reporting
    # -------------------------------------------------------------------------

    def get_stock_valuation(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get total stock valuation for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            
        Returns:
            Dictionary with valuation details
        """
        try:
            valuation = self.ingredient_repo.calculate_stock_valuation(db, hostel_id)
            
            return {
                "hostel_id": str(hostel_id),
                "total_value": float(valuation.get("total_value", 0.0)),
                "item_count": valuation.get("item_count", 0),
                "valuation_date": date.today().isoformat(),
                "category_breakdown": valuation.get("by_category", {}),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error calculating stock valuation: {str(e)}"
            )

    def get_consumption_report(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get consumption report for a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the report
            end_date: End date of the report
            
        Returns:
            Dictionary with consumption statistics
        """
        try:
            report = self.ingredient_repo.get_consumption_report(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "hostel_id": str(hostel_id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_items_consumed": report.get("total_items", 0),
                "total_quantity": float(report.get("total_quantity", 0.0)),
                "total_value": float(report.get("total_value", 0.0)),
                "top_consumed_items": report.get("top_items", []),
                "consumption_by_category": report.get("by_category", {}),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error generating consumption report: {str(e)}"
            )

    def get_waste_report(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get waste report for a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the report
            end_date: End date of the report
            
        Returns:
            Dictionary with waste statistics
        """
        try:
            report = self.ingredient_repo.get_waste_report(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "hostel_id": str(hostel_id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_waste_events": report.get("total_events", 0),
                "total_waste_quantity": float(report.get("total_quantity", 0.0)),
                "total_waste_value": float(report.get("total_value", 0.0)),
                "waste_by_reason": report.get("by_reason", {}),
                "top_wasted_items": report.get("top_items", []),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error generating waste report: {str(e)}"
            )

    def get_purchase_history(
        self,
        db: Session,
        ingredient_id: UUID,
        limit: Optional[int] = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get purchase history for an ingredient.
        
        Args:
            db: Database session
            ingredient_id: Unique identifier of the ingredient
            limit: Maximum number of records to return
            
        Returns:
            List of purchase records
        """
        try:
            purchases = self.ingredient_repo.get_purchase_history(
                db, ingredient_id, limit
            )
            
            return [
                {
                    "purchase_date": p.get("purchase_date"),
                    "quantity": float(p.get("quantity", 0.0)),
                    "unit_price": float(p.get("unit_price", 0.0)),
                    "total_cost": float(p.get("total_cost", 0.0)),
                    "supplier": p.get("supplier"),
                    "invoice_number": p.get("invoice_number"),
                }
                for p in purchases
            ]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving purchase history: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Forecasting & Predictions
    # -------------------------------------------------------------------------

    def forecast_stock_requirements(
        self,
        db: Session,
        hostel_id: UUID,
        days_ahead: int = 7,
    ) -> Dict[str, Any]:
        """
        Forecast stock requirements for upcoming days.
        
        This uses historical consumption patterns to predict future needs.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            days_ahead: Number of days to forecast
            
        Returns:
            Dictionary with forecast data
        """
        try:
            forecast = self.ingredient_repo.forecast_requirements(
                db, hostel_id, days_ahead
            )
            
            return {
                "hostel_id": str(hostel_id),
                "forecast_days": days_ahead,
                "forecast_date": date.today().isoformat(),
                "predicted_requirements": forecast.get("requirements", []),
                "reorder_recommendations": forecast.get("reorder", []),
                "confidence_level": forecast.get("confidence", 0.0),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error forecasting stock requirements: {str(e)}"
            )

    def get_reorder_suggestions(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get suggestions for items that need to be reordered.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            
        Returns:
            List of reorder suggestions
        """
        try:
            suggestions = self.ingredient_repo.get_reorder_suggestions(db, hostel_id)
            
            return [
                {
                    "ingredient_id": str(s.get("ingredient_id")),
                    "ingredient_name": s.get("name"),
                    "current_stock": float(s.get("current_stock", 0.0)),
                    "reorder_point": float(s.get("reorder_point", 0.0)),
                    "suggested_order_quantity": float(s.get("suggested_quantity", 0.0)),
                    "estimated_cost": float(s.get("estimated_cost", 0.0)),
                    "urgency": s.get("urgency", "normal"),
                }
                for s in suggestions
            ]
            
        except Exception as e:
            raise ValidationException(
                f"Error generating reorder suggestions: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _format_ingredient_data(self, ingredient: Any) -> Dict[str, Any]:
        """Format ingredient object as dictionary."""
        return {
            "id": str(getattr(ingredient, 'id', '')),
            "name": getattr(ingredient, 'name', ''),
            "category": getattr(ingredient, 'category', ''),
            "current_stock": float(getattr(ingredient, 'current_stock', 0.0)),
            "unit": getattr(ingredient, 'unit', ''),
            "min_stock_level": float(getattr(ingredient, 'min_stock_level', 0.0)),
            "max_stock_level": float(getattr(ingredient, 'max_stock_level', 0.0)),
            "reorder_point": float(getattr(ingredient, 'reorder_point', 0.0)),
            "unit_price": float(getattr(ingredient, 'unit_price', 0.0)),
            "expiry_date": getattr(ingredient, 'expiry_date', None),
            "stock_status": self._get_stock_status(ingredient),
            "last_updated": getattr(ingredient, 'updated_at', None),
        }

    def _validate_ingredient_data(self, data: Dict[str, Any]) -> None:
        """Validate ingredient data."""
        if not data.get('name') or not data.get('name').strip():
            raise ValidationException("Ingredient name is required")
        
        if 'current_stock' in data and data['current_stock'] < 0:
            raise ValidationException("Stock quantity cannot be negative")
        
        if 'unit_price' in data and data['unit_price'] < 0:
            raise ValidationException("Unit price cannot be negative")

    def _validate_stock_adjustment(
        self,
        ingredient: Any,
        delta_quantity: Decimal,
    ) -> None:
        """Validate stock adjustment."""
        current_stock = Decimal(str(getattr(ingredient, 'current_stock', 0)))
        new_stock = current_stock + delta_quantity
        
        if new_stock < 0:
            raise ValidationException(
                f"Insufficient stock. Current: {current_stock}, "
                f"Requested: {abs(delta_quantity)}"
            )

    def _is_low_stock(self, ingredient: Any) -> bool:
        """Check if ingredient stock is low."""
        current = Decimal(str(getattr(ingredient, 'current_stock', 0)))
        max_level = Decimal(str(getattr(ingredient, 'max_stock_level', 0)))
        
        if max_level == 0:
            return False
        
        ratio = current / max_level
        return ratio <= self.LOW_STOCK_THRESHOLD

    def _get_stock_status(self, ingredient: Any) -> str:
        """Get stock status label."""
        current = Decimal(str(getattr(ingredient, 'current_stock', 0)))
        max_level = Decimal(str(getattr(ingredient, 'max_stock_level', 0)))
        
        if max_level == 0:
            return "unknown"
        
        ratio = current / max_level
        
        if ratio <= self.CRITICAL_STOCK_THRESHOLD:
            return "critical"
        elif ratio <= self.LOW_STOCK_THRESHOLD:
            return "low"
        elif ratio >= Decimal('0.8'):
            return "optimal"
        else:
            return "adequate"

    def _is_ingredient_in_use(self, db: Session, ingredient_id: UUID) -> bool:
        """Check if ingredient is used in any recipes or menus."""
        try:
            return self.ingredient_repo.is_in_use(db, ingredient_id)
        except:
            return False

    def _log_stock_transaction(
        self,
        db: Session,
        ingredient_id: UUID,
        delta_quantity: Decimal,
        reason: str,
        reference_id: Optional[UUID] = None,
        performed_by: Optional[UUID] = None,
    ) -> None:
        """Log stock transaction for audit trail."""
        try:
            self.ingredient_repo.log_transaction(
                db,
                ingredient_id,
                delta_quantity,
                reason,
                reference_id,
                performed_by,
            )
        except:
            # Log error but don't fail the main operation
            pass

    def _log_waste_event(
        self,
        db: Session,
        ingredient_id: UUID,
        quantity: Decimal,
        reason: str,
    ) -> None:
        """Log waste event for analytics."""
        try:
            self.ingredient_repo.log_waste(
                db,
                ingredient_id,
                quantity,
                reason,
                date.today(),
            )
        except:
            pass

    def _check_and_trigger_stock_alerts(
        self,
        db: Session,
        ingredient: Any,
    ) -> None:
        """Check stock levels and trigger alerts if needed."""
        try:
            if self._is_low_stock(ingredient):
                self.ingredient_repo.trigger_low_stock_alert(db, ingredient)
        except:
            pass