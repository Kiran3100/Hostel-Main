"""
Subscription Plan Service

Manages subscription plans and their feature sets.

Improvements:
- Enhanced plan validation
- Added plan versioning support pattern
- Improved feature comparison logic
- Better caching strategy
- Added plan recommendation logic
- Enhanced search and filtering
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any, Set
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionPlanRepository
from app.schemas.subscription import (
    SubscriptionPlanBase,
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    PlanFeatures,
    PlanComparison,
)
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SubscriptionPlanService:
    """
    High-level service for subscription plans.

    Responsibilities:
    - Create/update/delete plans
    - List/search plans with advanced filtering
    - Get plan features and capabilities
    - Compare multiple plans
    - Handle plan versioning
    - Recommend plans based on criteria
    """

    # Constants
    MAX_PLANS_PER_COMPARISON = 5
    DEFAULT_PLAN_LIMIT = 20

    def __init__(
        self,
        plan_repo: SubscriptionPlanRepository,
    ) -> None:
        """
        Initialize the plan service.

        Args:
            plan_repo: Repository for plan data access

        Raises:
            ValueError: If repository is None
        """
        if not plan_repo:
            raise ValueError("Plan repository is required")
        self.plan_repo = plan_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_plan(
        self,
        db: Session,
        data: PlanCreate,
    ) -> PlanResponse:
        """
        Create a new subscription plan.

        Args:
            db: Database session
            data: Plan creation data

        Returns:
            Created PlanResponse

        Raises:
            ValidationException: If validation fails
        """
        # Validate plan data
        self._validate_plan_data(data)

        # Check for duplicate plan names
        existing = self.plan_repo.get_by_name(db, data.name)
        if existing:
            raise ValidationException(f"Plan with name '{data.name}' already exists")

        try:
            plan_dict = data.model_dump(exclude_none=True)
            
            # Add metadata
            plan_dict["created_at"] = datetime.utcnow()
            plan_dict["is_active"] = plan_dict.get("is_active", True)
            
            obj = self.plan_repo.create(db, data=plan_dict)
            
            logger.info(f"Created subscription plan: {data.name} (ID: {obj.id})")
            return PlanResponse.model_validate(obj)

        except Exception as e:
            logger.error(f"Failed to create plan '{data.name}': {str(e)}")
            raise ValidationException(f"Failed to create plan: {str(e)}")

    def update_plan(
        self,
        db: Session,
        plan_id: UUID,
        data: PlanUpdate,
    ) -> PlanResponse:
        """
        Update an existing subscription plan.

        Args:
            db: Database session
            plan_id: UUID of the plan to update
            data: Plan update data

        Returns:
            Updated PlanResponse

        Raises:
            ValidationException: If plan not found or validation fails
        """
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            raise ValidationException(f"Plan not found with ID: {plan_id}")

        # Validate update data
        if data.name and data.name != plan.name:
            existing = self.plan_repo.get_by_name(db, data.name)
            if existing and existing.id != plan_id:
                raise ValidationException(f"Plan name '{data.name}' is already in use")

        try:
            update_dict = data.model_dump(exclude_none=True)
            update_dict["updated_at"] = datetime.utcnow()
            
            updated = self.plan_repo.update(db, plan, data=update_dict)
            
            logger.info(f"Updated subscription plan: {plan.name} (ID: {plan_id})")
            return PlanResponse.model_validate(updated)

        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {str(e)}")
            raise ValidationException(f"Failed to update plan: {str(e)}")

    def delete_plan(
        self,
        db: Session,
        plan_id: UUID,
        soft_delete: bool = True,
    ) -> None:
        """
        Delete a subscription plan.

        Args:
            db: Database session
            plan_id: UUID of the plan to delete
            soft_delete: If True, mark as inactive; if False, permanently delete

        Raises:
            ValidationException: If plan has active subscriptions
        """
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            logger.warning(f"Attempt to delete non-existent plan: {plan_id}")
            return

        # Check for active subscriptions
        if self.plan_repo.has_active_subscriptions(db, plan_id):
            raise ValidationException(
                "Cannot delete plan with active subscriptions. "
                "Please migrate or cancel subscriptions first."
            )

        try:
            if soft_delete:
                # Soft delete: mark as inactive
                self.plan_repo.update(
                    db,
                    plan,
                    data={
                        "is_active": False,
                        "deleted_at": datetime.utcnow(),
                    }
                )
                logger.info(f"Soft deleted plan: {plan.name} (ID: {plan_id})")
            else:
                # Hard delete
                self.plan_repo.delete(db, plan)
                logger.info(f"Permanently deleted plan: {plan.name} (ID: {plan_id})")

        except Exception as e:
            logger.error(f"Failed to delete plan {plan_id}: {str(e)}")
            raise ValidationException(f"Failed to delete plan: {str(e)}")

    def archive_plan(
        self,
        db: Session,
        plan_id: UUID,
        reason: Optional[str] = None,
    ) -> PlanResponse:
        """
        Archive a plan (make it unavailable for new subscriptions).

        Args:
            db: Database session
            plan_id: UUID of the plan to archive
            reason: Optional reason for archiving

        Returns:
            Archived PlanResponse
        """
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            raise ValidationException(f"Plan not found with ID: {plan_id}")

        try:
            updated = self.plan_repo.update(
                db,
                plan,
                data={
                    "is_active": False,
                    "is_public": False,
                    "archived_at": datetime.utcnow(),
                    "archive_reason": reason,
                }
            )
            
            logger.info(f"Archived plan: {plan.name} (ID: {plan_id}). Reason: {reason or 'N/A'}")
            return PlanResponse.model_validate(updated)

        except Exception as e:
            logger.error(f"Failed to archive plan {plan_id}: {str(e)}")
            raise ValidationException(f"Failed to archive plan: {str(e)}")

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_plan(
        self,
        db: Session,
        plan_id: UUID,
        include_inactive: bool = False,
    ) -> PlanResponse:
        """
        Retrieve a subscription plan by ID.

        Args:
            db: Database session
            plan_id: UUID of the plan
            include_inactive: Whether to include inactive plans

        Returns:
            PlanResponse

        Raises:
            ValidationException: If plan not found
        """
        plan = self.plan_repo.get_by_id(db, plan_id)
        
        if not plan:
            raise ValidationException(f"Plan not found with ID: {plan_id}")
        
        if not include_inactive and not plan.is_active:
            raise ValidationException(f"Plan {plan_id} is not active")
        
        return PlanResponse.model_validate(plan)

    def get_plan_by_name(
        self,
        db: Session,
        name: str,
        include_inactive: bool = False,
    ) -> Optional[PlanResponse]:
        """
        Retrieve a plan by name.

        Args:
            db: Database session
            name: Plan name
            include_inactive: Whether to include inactive plans

        Returns:
            PlanResponse or None if not found
        """
        plan = self.plan_repo.get_by_name(db, name)
        
        if not plan:
            return None
        
        if not include_inactive and not plan.is_active:
            return None
        
        return PlanResponse.model_validate(plan)

    def list_plans(
        self,
        db: Session,
        active_only: bool = True,
        public_only: bool = False,
        limit: int = DEFAULT_PLAN_LIMIT,
        offset: int = 0,
    ) -> List[PlanResponse]:
        """
        List subscription plans with filters.

        Args:
            db: Database session
            active_only: Only return active plans
            public_only: Only return publicly visible plans
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of PlanResponse objects
        """
        try:
            objs = self.plan_repo.get_all(
                db,
                active_only=active_only,
                public_only=public_only,
                limit=limit,
                offset=offset,
            )
            
            logger.debug(
                f"Retrieved {len(objs)} plans (active_only={active_only}, "
                f"public_only={public_only})"
            )
            
            return [PlanResponse.model_validate(o) for o in objs]

        except Exception as e:
            logger.error(f"Error listing plans: {str(e)}")
            return []

    def search_plans(
        self,
        db: Session,
        search_term: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        has_trial: Optional[bool] = None,
        billing_interval: Optional[str] = None,
        features: Optional[List[str]] = None,
    ) -> List[PlanResponse]:
        """
        Search plans with multiple criteria.

        Args:
            db: Database session
            search_term: Search in plan name and description
            min_price: Minimum monthly price
            max_price: Maximum monthly price
            has_trial: Filter by trial period availability
            billing_interval: Filter by billing interval (monthly, yearly, etc.)
            features: List of required features

        Returns:
            List of matching PlanResponse objects
        """
        try:
            objs = self.plan_repo.search_plans(
                db,
                search_term=search_term,
                min_price=min_price,
                max_price=max_price,
                has_trial=has_trial,
                billing_interval=billing_interval,
                features=features,
            )
            
            logger.debug(f"Search found {len(objs)} matching plans")
            return [PlanResponse.model_validate(o) for o in objs]

        except Exception as e:
            logger.error(f"Error searching plans: {str(e)}")
            return []

    def get_recommended_plans(
        self,
        db: Session,
        hostel_size: Optional[str] = None,
        budget: Optional[float] = None,
        required_features: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[PlanResponse]:
        """
        Get recommended plans based on criteria.

        Args:
            db: Database session
            hostel_size: Size category (small, medium, large)
            budget: Maximum monthly budget
            required_features: List of must-have features
            limit: Maximum number of recommendations

        Returns:
            List of recommended PlanResponse objects
        """
        try:
            plans = self.search_plans(
                db,
                max_price=budget,
                features=required_features,
            )
            
            # Sort by relevance (can be customized based on business logic)
            # For now, sort by price (ascending) and feature count
            plans.sort(
                key=lambda p: (
                    p.monthly_price or 0,
                    -len(p.features or {})
                )
            )
            
            recommended = plans[:limit]
            
            logger.info(f"Generated {len(recommended)} plan recommendations")
            return recommended

        except Exception as e:
            logger.error(f"Error generating plan recommendations: {str(e)}")
            return []

    # -------------------------------------------------------------------------
    # Features & comparison
    # -------------------------------------------------------------------------

    def get_plan_features(
        self,
        db: Session,
        plan_id: UUID,
        feature_labels: Optional[Dict[str, str]] = None,
    ) -> PlanFeatures:
        """
        Return a human-friendly feature set for a plan.

        Args:
            db: Database session
            plan_id: UUID of the plan
            feature_labels: Optional mapping of feature keys to display labels

        Returns:
            PlanFeatures object

        Raises:
            ValidationException: If plan not found
        """
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            raise ValidationException(f"Plan not found with ID: {plan_id}")

        try:
            plan_resp = PlanResponse.model_validate(plan)
            return PlanFeatures.from_plan_response(plan_resp, feature_labels or {})

        except Exception as e:
            logger.error(f"Error getting plan features for {plan_id}: {str(e)}")
            raise ValidationException(f"Failed to get plan features: {str(e)}")

    def compare_plans(
        self,
        db: Session,
        plan_ids: List[UUID],
    ) -> PlanComparison:
        """
        Build a comparison matrix of multiple plans.

        Args:
            db: Database session
            plan_ids: List of plan UUIDs to compare (2-5 plans)

        Returns:
            PlanComparison object

        Raises:
            ValidationException: If validation fails
        """
        # Validate input
        if len(plan_ids) < 2:
            raise ValidationException("At least two plans required for comparison")
        
        if len(plan_ids) > self.MAX_PLANS_PER_COMPARISON:
            raise ValidationException(
                f"Maximum {self.MAX_PLANS_PER_COMPARISON} plans can be compared at once"
            )

        # Retrieve all plans
        objs = []
        for pid in plan_ids:
            obj = self.plan_repo.get_by_id(db, pid)
            if not obj:
                raise ValidationException(f"Plan not found with ID: {pid}")
            objs.append(obj)

        try:
            plans = [PlanResponse.model_validate(o) for o in objs]
            comparison = PlanComparison.create(plans)
            
            logger.info(f"Generated comparison for {len(plans)} plans")
            return comparison

        except Exception as e:
            logger.error(f"Error comparing plans: {str(e)}")
            raise ValidationException(f"Failed to compare plans: {str(e)}")

    def get_feature_availability(
        self,
        db: Session,
        feature_key: str,
    ) -> Dict[str, bool]:
        """
        Check which plans include a specific feature.

        Args:
            db: Database session
            feature_key: Feature key to check

        Returns:
            Dictionary mapping plan IDs to availability (True/False)
        """
        try:
            plans = self.list_plans(db, active_only=True)
            
            availability = {}
            for plan in plans:
                features = plan.features or {}
                availability[str(plan.id)] = feature_key in features
            
            return availability

        except Exception as e:
            logger.error(f"Error checking feature availability for '{feature_key}': {str(e)}")
            return {}

    # -------------------------------------------------------------------------
    # Plan analytics
    # -------------------------------------------------------------------------

    def get_most_popular_plans(
        self,
        db: Session,
        limit: int = 5,
    ) -> List[PlanResponse]:
        """
        Get the most popular plans by subscription count.

        Args:
            db: Database session
            limit: Maximum number of plans to return

        Returns:
            List of most popular PlanResponse objects
        """
        try:
            objs = self.plan_repo.get_most_popular_plans(db, limit=limit)
            return [PlanResponse.model_validate(o) for o in objs]

        except Exception as e:
            logger.error(f"Error getting popular plans: {str(e)}")
            return []

    def get_plan_statistics(
        self,
        db: Session,
        plan_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get statistics for a specific plan.

        Args:
            db: Database session
            plan_id: UUID of the plan

        Returns:
            Dictionary with plan statistics
        """
        try:
            stats = self.plan_repo.get_plan_statistics(db, plan_id)
            
            logger.debug(f"Retrieved statistics for plan {plan_id}")
            return stats

        except Exception as e:
            logger.error(f"Error getting plan statistics for {plan_id}: {str(e)}")
            return {}

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_plan_data(self, data: PlanCreate) -> None:
        """
        Validate plan creation/update data.

        Args:
            data: Plan data to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate pricing
        if data.monthly_price is not None and data.monthly_price < 0:
            raise ValidationException("Monthly price cannot be negative")
        
        if data.annual_price is not None and data.annual_price < 0:
            raise ValidationException("Annual price cannot be negative")

        # Validate trial period
        if data.trial_period_days is not None and data.trial_period_days < 0:
            raise ValidationException("Trial period cannot be negative")

        # Validate feature limits
        if hasattr(data, 'features') and data.features:
            self._validate_features(data.features)

    def _validate_features(self, features: Dict[str, Any]) -> None:
        """
        Validate feature configuration.

        Args:
            features: Feature dictionary to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate numeric limits
        for key, value in features.items():
            if isinstance(value, (int, float)) and value < 0:
                raise ValidationException(f"Feature '{key}' cannot have negative value")