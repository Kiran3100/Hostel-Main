"""
Subscription Plan Repository.

Manages subscription plan data access with pricing optimization,
feature management, and plan comparison capabilities.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.subscription.subscription_plan import PlanFeature, SubscriptionPlan
from app.schemas.common.enums import SubscriptionPlan as SubscriptionPlanEnum


class SubscriptionPlanRepository:
    """
    Repository for subscription plan operations.

    Provides methods for plan management, feature configuration,
    pricing optimization, and plan comparison.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== CREATE OPERATIONS ====================

    def create_plan(
        self,
        plan_data: Dict[str, Any],
        created_by: Optional[UUID] = None,
    ) -> SubscriptionPlan:
        """
        Create new subscription plan.

        Args:
            plan_data: Plan configuration data
            created_by: User ID who created the plan

        Returns:
            Created subscription plan
        """
        plan = SubscriptionPlan(**plan_data)
        if created_by:
            plan.created_by = created_by

        self.db.add(plan)
        self.db.flush()
        return plan

    def create_plan_feature(
        self,
        plan_id: UUID,
        feature_data: Dict[str, Any],
    ) -> PlanFeature:
        """
        Create plan feature.

        Args:
            plan_id: Subscription plan ID
            feature_data: Feature configuration data

        Returns:
            Created plan feature
        """
        feature = PlanFeature(plan_id=plan_id, **feature_data)
        self.db.add(feature)
        self.db.flush()
        return feature

    def bulk_create_features(
        self,
        plan_id: UUID,
        features: List[Dict[str, Any]],
    ) -> List[PlanFeature]:
        """
        Bulk create plan features.

        Args:
            plan_id: Subscription plan ID
            features: List of feature configurations

        Returns:
            List of created features
        """
        feature_objects = [
            PlanFeature(plan_id=plan_id, **feature_data) for feature_data in features
        ]
        self.db.bulk_save_objects(feature_objects, return_defaults=True)
        self.db.flush()
        return feature_objects

    # ==================== READ OPERATIONS ====================

    def get_by_id(
        self,
        plan_id: UUID,
        include_features: bool = True,
    ) -> Optional[SubscriptionPlan]:
        """
        Get subscription plan by ID.

        Args:
            plan_id: Plan ID
            include_features: Include plan features

        Returns:
            Subscription plan if found
        """
        query = select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)

        if include_features:
            query = query.options(joinedload(SubscriptionPlan.plan_features))

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_name(self, plan_name: str) -> Optional[SubscriptionPlan]:
        """
        Get subscription plan by name.

        Args:
            plan_name: Plan name

        Returns:
            Subscription plan if found
        """
        query = select(SubscriptionPlan).where(SubscriptionPlan.plan_name == plan_name)
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_type(self, plan_type: SubscriptionPlanEnum) -> Optional[SubscriptionPlan]:
        """
        Get subscription plan by type.

        Args:
            plan_type: Plan type enum

        Returns:
            Subscription plan if found
        """
        query = (
            select(SubscriptionPlan)
            .where(SubscriptionPlan.plan_type == plan_type)
            .options(joinedload(SubscriptionPlan.plan_features))
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_all_active_plans(
        self,
        public_only: bool = False,
    ) -> List[SubscriptionPlan]:
        """
        Get all active subscription plans.

        Args:
            public_only: Return only public plans

        Returns:
            List of active plans
        """
        query = (
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active == True)
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(SubscriptionPlan.sort_order)
        )

        if public_only:
            query = query.where(SubscriptionPlan.is_public == True)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_public_plans(self) -> List[SubscriptionPlan]:
        """
        Get all public subscription plans for display.

        Returns:
            List of public plans ordered by sort_order
        """
        query = (
            select(SubscriptionPlan)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    SubscriptionPlan.is_public == True,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(SubscriptionPlan.sort_order)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_featured_plan(self) -> Optional[SubscriptionPlan]:
        """
        Get featured/recommended plan.

        Returns:
            Featured subscription plan if exists
        """
        query = (
            select(SubscriptionPlan)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    SubscriptionPlan.is_featured == True,
                    SubscriptionPlan.is_public == True,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(SubscriptionPlan.sort_order)
            .limit(1)
        )

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_plans_by_price_range(
        self,
        min_price: Decimal,
        max_price: Decimal,
        billing_cycle: str = "monthly",
    ) -> List[SubscriptionPlan]:
        """
        Get plans within price range.

        Args:
            min_price: Minimum price
            max_price: Maximum price
            billing_cycle: Billing cycle (monthly/yearly)

        Returns:
            List of plans in price range
        """
        price_column = (
            SubscriptionPlan.price_monthly
            if billing_cycle == "monthly"
            else SubscriptionPlan.price_yearly
        )

        query = (
            select(SubscriptionPlan)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    price_column >= min_price,
                    price_column <= max_price,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(price_column)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_plan_features(self, plan_id: UUID) -> List[PlanFeature]:
        """
        Get all features for a plan.

        Args:
            plan_id: Plan ID

        Returns:
            List of plan features
        """
        query = (
            select(PlanFeature)
            .where(PlanFeature.plan_id == plan_id)
            .order_by(PlanFeature.sort_order)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_feature_by_key(
        self,
        plan_id: UUID,
        feature_key: str,
    ) -> Optional[PlanFeature]:
        """
        Get specific plan feature by key.

        Args:
            plan_id: Plan ID
            feature_key: Feature key

        Returns:
            Plan feature if found
        """
        query = select(PlanFeature).where(
            and_(
                PlanFeature.plan_id == plan_id,
                PlanFeature.feature_key == feature_key,
            )
        )

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_plans_with_feature(
        self,
        feature_key: str,
        enabled_only: bool = True,
    ) -> List[SubscriptionPlan]:
        """
        Get plans that have specific feature.

        Args:
            feature_key: Feature key to search for
            enabled_only: Only return plans where feature is enabled

        Returns:
            List of plans with the feature
        """
        query = (
            select(SubscriptionPlan)
            .join(PlanFeature, PlanFeature.plan_id == SubscriptionPlan.id)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    PlanFeature.feature_key == feature_key,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
        )

        if enabled_only:
            query = query.where(PlanFeature.enabled == True)

        result = self.db.execute(query)
        return list(result.scalars().unique().all())

    def get_plans_with_trial(self) -> List[SubscriptionPlan]:
        """
        Get all plans offering trial period.

        Returns:
            List of plans with trial
        """
        query = (
            select(SubscriptionPlan)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    SubscriptionPlan.trial_days > 0,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(SubscriptionPlan.sort_order)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    # ==================== UPDATE OPERATIONS ====================

    def update_plan(
        self,
        plan_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Update subscription plan.

        Args:
            plan_id: Plan ID
            update_data: Updated plan data
            updated_by: User ID who updated the plan

        Returns:
            Updated plan
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        for key, value in update_data.items():
            if hasattr(plan, key):
                setattr(plan, key, value)

        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def update_plan_pricing(
        self,
        plan_id: UUID,
        price_monthly: Optional[Decimal] = None,
        price_yearly: Optional[Decimal] = None,
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Update plan pricing.

        Args:
            plan_id: Plan ID
            price_monthly: New monthly price
            price_yearly: New yearly price
            updated_by: User ID who updated pricing

        Returns:
            Updated plan
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        if price_monthly is not None:
            plan.price_monthly = price_monthly
        if price_yearly is not None:
            plan.price_yearly = price_yearly

        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def update_plan_limits(
        self,
        plan_id: UUID,
        limits: Dict[str, Optional[int]],
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Update plan usage limits.

        Args:
            plan_id: Plan ID
            limits: Dictionary of limit updates
            updated_by: User ID who updated limits

        Returns:
            Updated plan
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        limit_fields = {
            "max_hostels",
            "max_rooms_per_hostel",
            "max_students",
            "max_admins",
        }

        for key, value in limits.items():
            if key in limit_fields and hasattr(plan, key):
                setattr(plan, key, value)

        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def update_plan_feature(
        self,
        feature_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[PlanFeature]:
        """
        Update plan feature.

        Args:
            feature_id: Feature ID
            update_data: Updated feature data

        Returns:
            Updated feature
        """
        query = select(PlanFeature).where(PlanFeature.id == feature_id)
        result = self.db.execute(query)
        feature = result.scalar_one_or_none()

        if not feature:
            return None

        for key, value in update_data.items():
            if hasattr(feature, key):
                setattr(feature, key, value)

        feature.updated_at = datetime.utcnow()
        self.db.flush()
        return feature

    def toggle_plan_status(
        self,
        plan_id: UUID,
        is_active: bool,
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Activate or deactivate plan.

        Args:
            plan_id: Plan ID
            is_active: Active status
            updated_by: User ID who changed status

        Returns:
            Updated plan
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        plan.is_active = is_active
        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def toggle_plan_visibility(
        self,
        plan_id: UUID,
        is_public: bool,
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Change plan public visibility.

        Args:
            plan_id: Plan ID
            is_public: Public visibility status
            updated_by: User ID who changed visibility

        Returns:
            Updated plan
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        plan.is_public = is_public
        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def set_featured_plan(
        self,
        plan_id: UUID,
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Set plan as featured (unsets other featured plans).

        Args:
            plan_id: Plan ID to set as featured
            updated_by: User ID who set featured status

        Returns:
            Updated plan
        """
        # Unset all other featured plans
        self.db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_featured == True)
            .execution_options(synchronize_session=False)
        )
        self.db.query(SubscriptionPlan).filter(
            SubscriptionPlan.is_featured == True
        ).update({"is_featured": False}, synchronize_session=False)

        # Set new featured plan
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        plan.is_featured = True
        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def update_sort_order(
        self,
        plan_id: UUID,
        sort_order: int,
        updated_by: Optional[UUID] = None,
    ) -> Optional[SubscriptionPlan]:
        """
        Update plan display sort order.

        Args:
            plan_id: Plan ID
            sort_order: New sort order
            updated_by: User ID who updated order

        Returns:
            Updated plan
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return None

        plan.sort_order = sort_order
        if updated_by:
            plan.updated_by = updated_by
        plan.updated_at = datetime.utcnow()

        self.db.flush()
        return plan

    def bulk_update_sort_orders(
        self,
        plan_orders: Dict[UUID, int],
        updated_by: Optional[UUID] = None,
    ) -> int:
        """
        Bulk update plan sort orders.

        Args:
            plan_orders: Dictionary of plan_id: sort_order
            updated_by: User ID who updated orders

        Returns:
            Number of plans updated
        """
        count = 0
        for plan_id, sort_order in plan_orders.items():
            plan = self.get_by_id(plan_id, include_features=False)
            if plan:
                plan.sort_order = sort_order
                if updated_by:
                    plan.updated_by = updated_by
                plan.updated_at = datetime.utcnow()
                count += 1

        self.db.flush()
        return count

    # ==================== DELETE OPERATIONS ====================

    def delete_plan(self, plan_id: UUID) -> bool:
        """
        Delete subscription plan (hard delete).

        Args:
            plan_id: Plan ID

        Returns:
            True if deleted, False if not found
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return False

        self.db.delete(plan)
        self.db.flush()
        return True

    def delete_plan_feature(self, feature_id: UUID) -> bool:
        """
        Delete plan feature.

        Args:
            feature_id: Feature ID

        Returns:
            True if deleted, False if not found
        """
        query = select(PlanFeature).where(PlanFeature.id == feature_id)
        result = self.db.execute(query)
        feature = result.scalar_one_or_none()

        if not feature:
            return False

        self.db.delete(feature)
        self.db.flush()
        return True

    # ==================== ANALYTICS & REPORTING ====================

    def get_plan_statistics(self) -> Dict[str, Any]:
        """
        Get subscription plan statistics.

        Returns:
            Dictionary with plan statistics
        """
        total_plans = self.db.query(func.count(SubscriptionPlan.id)).scalar()
        active_plans = (
            self.db.query(func.count(SubscriptionPlan.id))
            .filter(SubscriptionPlan.is_active == True)
            .scalar()
        )
        public_plans = (
            self.db.query(func.count(SubscriptionPlan.id))
            .filter(
                and_(
                    SubscriptionPlan.is_active == True,
                    SubscriptionPlan.is_public == True,
                )
            )
            .scalar()
        )
        plans_with_trial = (
            self.db.query(func.count(SubscriptionPlan.id))
            .filter(SubscriptionPlan.trial_days > 0)
            .scalar()
        )

        return {
            "total_plans": total_plans,
            "active_plans": active_plans,
            "public_plans": public_plans,
            "plans_with_trial": plans_with_trial,
            "inactive_plans": total_plans - active_plans,
        }

    def get_pricing_summary(self) -> Dict[str, Any]:
        """
        Get pricing summary across all plans.

        Returns:
            Dictionary with pricing statistics
        """
        query = select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
        result = self.db.execute(query)
        plans = list(result.scalars().all())

        if not plans:
            return {
                "monthly": {"min": 0, "max": 0, "avg": 0},
                "yearly": {"min": 0, "max": 0, "avg": 0},
            }

        monthly_prices = [plan.price_monthly for plan in plans]
        yearly_prices = [plan.price_yearly for plan in plans]

        return {
            "monthly": {
                "min": min(monthly_prices),
                "max": max(monthly_prices),
                "avg": sum(monthly_prices) / len(monthly_prices),
            },
            "yearly": {
                "min": min(yearly_prices),
                "max": max(yearly_prices),
                "avg": sum(yearly_prices) / len(yearly_prices),
            },
        }

    def compare_plans(
        self,
        plan_ids: List[UUID],
    ) -> Dict[str, Any]:
        """
        Compare multiple subscription plans.

        Args:
            plan_ids: List of plan IDs to compare

        Returns:
            Comparison data structure
        """
        query = (
            select(SubscriptionPlan)
            .where(SubscriptionPlan.id.in_(plan_ids))
            .options(joinedload(SubscriptionPlan.plan_features))
        )

        result = self.db.execute(query)
        plans = list(result.scalars().unique().all())

        comparison = {
            "plans": [],
            "features": {},
            "pricing": {},
            "limits": {},
        }

        # Collect all unique features across plans
        all_features = set()
        for plan in plans:
            for feature in plan.plan_features:
                all_features.add(feature.feature_key)

        # Build comparison structure
        for plan in plans:
            plan_data = {
                "id": str(plan.id),
                "name": plan.display_name,
                "type": plan.plan_type.value,
                "price_monthly": float(plan.price_monthly),
                "price_yearly": float(plan.price_yearly),
                "features": {},
                "limits": {
                    "hostels": plan.max_hostels,
                    "rooms": plan.max_rooms_per_hostel,
                    "students": plan.max_students,
                    "admins": plan.max_admins,
                },
            }

            # Add feature comparison
            for feature_key in all_features:
                feature = next(
                    (f for f in plan.plan_features if f.feature_key == feature_key),
                    None,
                )
                plan_data["features"][feature_key] = (
                    {
                        "enabled": feature.enabled,
                        "value": feature.feature_value,
                        "label": feature.feature_label,
                    }
                    if feature
                    else None
                )

            comparison["plans"].append(plan_data)

        return comparison

    def get_upgrade_options(
        self,
        current_plan_id: UUID,
    ) -> List[SubscriptionPlan]:
        """
        Get available upgrade options from current plan.

        Args:
            current_plan_id: Current plan ID

        Returns:
            List of higher-tier plans
        """
        current_plan = self.get_by_id(current_plan_id, include_features=False)
        if not current_plan:
            return []

        query = (
            select(SubscriptionPlan)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    SubscriptionPlan.price_monthly > current_plan.price_monthly,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(SubscriptionPlan.price_monthly)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_downgrade_options(
        self,
        current_plan_id: UUID,
    ) -> List[SubscriptionPlan]:
        """
        Get available downgrade options from current plan.

        Args:
            current_plan_id: Current plan ID

        Returns:
            List of lower-tier plans
        """
        current_plan = self.get_by_id(current_plan_id, include_features=False)
        if not current_plan:
            return []

        query = (
            select(SubscriptionPlan)
            .where(
                and_(
                    SubscriptionPlan.is_active == True,
                    SubscriptionPlan.price_monthly < current_plan.price_monthly,
                )
            )
            .options(joinedload(SubscriptionPlan.plan_features))
            .order_by(SubscriptionPlan.price_monthly.desc())
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    # ==================== SEARCH & FILTERING ====================

    def search_plans(
        self,
        search_term: Optional[str] = None,
        plan_type: Optional[SubscriptionPlanEnum] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        has_trial: Optional[bool] = None,
        is_active: Optional[bool] = True,
        is_public: Optional[bool] = None,
    ) -> List[SubscriptionPlan]:
        """
        Search subscription plans with multiple filters.

        Args:
            search_term: Search in name and description
            plan_type: Filter by plan type
            min_price: Minimum monthly price
            max_price: Maximum monthly price
            has_trial: Filter by trial availability
            is_active: Filter by active status
            is_public: Filter by public visibility

        Returns:
            List of matching plans
        """
        query = select(SubscriptionPlan).options(
            joinedload(SubscriptionPlan.plan_features)
        )

        conditions = []

        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(
                or_(
                    SubscriptionPlan.plan_name.ilike(search_pattern),
                    SubscriptionPlan.display_name.ilike(search_pattern),
                    SubscriptionPlan.description.ilike(search_pattern),
                )
            )

        if plan_type:
            conditions.append(SubscriptionPlan.plan_type == plan_type)

        if min_price is not None:
            conditions.append(SubscriptionPlan.price_monthly >= min_price)

        if max_price is not None:
            conditions.append(SubscriptionPlan.price_monthly <= max_price)

        if has_trial is not None:
            if has_trial:
                conditions.append(SubscriptionPlan.trial_days > 0)
            else:
                conditions.append(SubscriptionPlan.trial_days == 0)

        if is_active is not None:
            conditions.append(SubscriptionPlan.is_active == is_active)

        if is_public is not None:
            conditions.append(SubscriptionPlan.is_public == is_public)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(SubscriptionPlan.sort_order)

        result = self.db.execute(query)
        return list(result.scalars().unique().all())

    # ==================== VALIDATION ====================

    def validate_plan_limits(
        self,
        plan_id: UUID,
        hostels: int = 0,
        rooms: int = 0,
        students: int = 0,
        admins: int = 0,
    ) -> Dict[str, Any]:
        """
        Validate if usage is within plan limits.

        Args:
            plan_id: Plan ID
            hostels: Number of hostels
            rooms: Number of rooms
            students: Number of students
            admins: Number of admins

        Returns:
            Validation result with details
        """
        plan = self.get_by_id(plan_id, include_features=False)
        if not plan:
            return {"valid": False, "error": "Plan not found"}

        violations = []

        if plan.max_hostels is not None and hostels > plan.max_hostels:
            violations.append(
                {
                    "limit": "hostels",
                    "current": hostels,
                    "max": plan.max_hostels,
                }
            )

        if plan.max_rooms_per_hostel is not None and rooms > plan.max_rooms_per_hostel:
            violations.append(
                {
                    "limit": "rooms",
                    "current": rooms,
                    "max": plan.max_rooms_per_hostel,
                }
            )

        if plan.max_students is not None and students > plan.max_students:
            violations.append(
                {
                    "limit": "students",
                    "current": students,
                    "max": plan.max_students,
                }
            )

        if plan.max_admins is not None and admins > plan.max_admins:
            violations.append(
                {
                    "limit": "admins",
                    "current": admins,
                    "max": plan.max_admins,
                }
            )

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "plan_name": plan.display_name,
        }

    def check_plan_availability(self, plan_id: UUID) -> bool:
        """
        Check if plan is available for new subscriptions.

        Args:
            plan_id: Plan ID

        Returns:
            True if available
        """
        plan = self.get_by_id(plan_id, include_features=False)
        return plan is not None and plan.is_active

    # ==================== BULK OPERATIONS ====================

    def bulk_activate_plans(
        self,
        plan_ids: List[UUID],
        updated_by: Optional[UUID] = None,
    ) -> int:
        """
        Bulk activate subscription plans.

        Args:
            plan_ids: List of plan IDs
            updated_by: User ID who activated plans

        Returns:
            Number of plans activated
        """
        count = 0
        for plan_id in plan_ids:
            if self.toggle_plan_status(plan_id, True, updated_by):
                count += 1
        return count

    def bulk_deactivate_plans(
        self,
        plan_ids: List[UUID],
        updated_by: Optional[UUID] = None,
    ) -> int:
        """
        Bulk deactivate subscription plans.

        Args:
            plan_ids: List of plan IDs
            updated_by: User ID who deactivated plans

        Returns:
            Number of plans deactivated
        """
        count = 0
        for plan_id in plan_ids:
            if self.toggle_plan_status(plan_id, False, updated_by):
                count += 1
        return count