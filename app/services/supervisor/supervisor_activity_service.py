"""
Supervisor Activity Service

Logs and queries supervisor activity and metrics with enhanced filtering and validation.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorActivityRepository
from app.schemas.supervisor import (
    SupervisorActivityLog,
    ActivitySummary,
    ActivityDetail,
    ActivityFilterParams,
)
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorActivityService:
    """
    High-level service for supervisor activities.

    Responsibilities:
    - Log activity entries with validation
    - Query activities with flexible filters
    - Build activity summaries and timelines
    - Generate activity reports

    Example:
        >>> service = SupervisorActivityService(activity_repo)
        >>> log = service.log_activity(db, supervisor_id, "complaint_resolved", ...)
        >>> summary = service.get_activity_summary(db, supervisor_id, filters)
    """

    def __init__(
        self,
        activity_repo: SupervisorActivityRepository,
    ) -> None:
        """
        Initialize the supervisor activity service.

        Args:
            activity_repo: Repository for activity operations
        """
        if not activity_repo:
            raise ValueError("activity_repo cannot be None")
            
        self.activity_repo = activity_repo

    # -------------------------------------------------------------------------
    # Logging Operations
    # -------------------------------------------------------------------------

    def log_activity(
        self,
        db: Session,
        supervisor_id: UUID,
        action_type: str,
        action_category: str,
        entity_type: str,
        entity_id: UUID,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SupervisorActivityLog:
        """
        Log a single supervisor activity entry.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            action_type: Type of action performed (e.g., "complaint_resolved")
            action_category: Category of action (e.g., "complaint_management")
            entity_type: Type of entity affected (e.g., "complaint")
            entity_id: UUID of the affected entity
            success: Whether the action was successful
            metadata: Optional additional data about the activity

        Returns:
            SupervisorActivityLog: Created activity log entry

        Raises:
            ValidationException: If validation fails

        Example:
            >>> log = service.log_activity(
            ...     db, supervisor_id,
            ...     action_type="complaint_resolved",
            ...     action_category="complaint_management",
            ...     entity_type="complaint",
            ...     entity_id=complaint_id,
            ...     success=True,
            ...     metadata={"resolution_time_minutes": 45}
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not action_type or not action_type.strip():
            raise ValidationException("Action type is required")
        
        if not action_category or not action_category.strip():
            raise ValidationException("Action category is required")
        
        if not entity_type or not entity_type.strip():
            raise ValidationException("Entity type is required")
        
        if not entity_id:
            raise ValidationException("Entity ID is required")

        try:
            logger.debug(
                f"Logging activity - supervisor: {supervisor_id}, "
                f"action: {action_type}, entity: {entity_type}:{entity_id}"
            )
            
            obj = self.activity_repo.log_activity(
                db=db,
                supervisor_id=supervisor_id,
                action_type=action_type.strip(),
                action_category=action_category.strip(),
                entity_type=entity_type.strip(),
                entity_id=entity_id,
                success=success,
                metadata=metadata or {},
            )
            
            logger.info(
                f"Successfully logged activity for supervisor {supervisor_id}: "
                f"{action_type}"
            )
            return SupervisorActivityLog.model_validate(obj)
            
        except Exception as e:
            logger.error(
                f"Failed to log activity for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to log activity: {str(e)}")

    def bulk_log_activities(
        self,
        db: Session,
        activities: List[Dict[str, Any]],
    ) -> List[SupervisorActivityLog]:
        """
        Log multiple activity entries in bulk.

        Args:
            db: Database session
            activities: List of activity data dictionaries

        Returns:
            List[SupervisorActivityLog]: List of created activity logs

        Raises:
            ValidationException: If validation fails

        Example:
            >>> activities = [
            ...     {"supervisor_id": id1, "action_type": "login", ...},
            ...     {"supervisor_id": id2, "action_type": "complaint_resolved", ...}
            ... ]
            >>> logs = service.bulk_log_activities(db, activities)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not activities:
            raise ValidationException("Activities list cannot be empty")

        try:
            logger.info(f"Bulk logging {len(activities)} activities")
            
            logged = []
            for activity_data in activities:
                log = self.log_activity(
                    db=db,
                    supervisor_id=activity_data.get("supervisor_id"),
                    action_type=activity_data.get("action_type"),
                    action_category=activity_data.get("action_category"),
                    entity_type=activity_data.get("entity_type"),
                    entity_id=activity_data.get("entity_id"),
                    success=activity_data.get("success", True),
                    metadata=activity_data.get("metadata"),
                )
                logged.append(log)
            
            logger.info(f"Successfully logged {len(logged)} activities")
            return logged
            
        except Exception as e:
            logger.error(f"Failed to bulk log activities: {str(e)}")
            raise ValidationException(f"Failed to bulk log activities: {str(e)}")

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_activity_summary(
        self,
        db: Session,
        supervisor_id: UUID,
        filters: ActivityFilterParams,
    ) -> ActivitySummary:
        """
        Get aggregated activity summary for a supervisor given filters.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            filters: Filter parameters (date range, categories, etc.)

        Returns:
            ActivitySummary: Aggregated activity metrics

        Raises:
            ValidationException: If validation fails or no data available

        Example:
            >>> filters = ActivityFilterParams(
            ...     start_date=start_date,
            ...     end_date=end_date,
            ...     action_categories=["complaint_management"]
            ... )
            >>> summary = service.get_activity_summary(db, supervisor_id, filters)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not filters:
            raise ValidationException("Filter parameters are required")

        try:
            logger.debug(
                f"Getting activity summary for supervisor: {supervisor_id}"
            )
            
            summary_dict = self.activity_repo.get_summary(
                db=db,
                supervisor_id=supervisor_id,
                filters=filters,
            )
            
            if summary_dict is None:
                logger.warning(
                    f"No activity summary available for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"No activity summary available for supervisor {supervisor_id}"
                )
            
            # Provide default empty summary if repo returns empty dict
            if not summary_dict:
                logger.info(
                    f"Empty activity summary for supervisor: {supervisor_id}"
                )
                summary_dict = {
                    "supervisor_id": str(supervisor_id),
                    "total_activities": 0,
                    "successful_activities": 0,
                    "failed_activities": 0,
                    "categories": {},
                }
            
            return ActivitySummary.model_validate(summary_dict)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get activity summary for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve activity summary: {str(e)}")

    def list_activities(
        self,
        db: Session,
        supervisor_id: UUID,
        filters: ActivityFilterParams,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ActivityDetail]:
        """
        List activity entries matching filters (detailed view) with pagination.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            filters: Filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ActivityDetail]: List of detailed activity entries

        Raises:
            ValidationException: If validation fails

        Example:
            >>> activities = service.list_activities(
            ...     db, supervisor_id, filters, skip=0, limit=50
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not filters:
            raise ValidationException("Filter parameters are required")
        
        if skip < 0:
            raise ValidationException("Skip parameter cannot be negative")
        
        if limit <= 0 or limit > 1000:
            raise ValidationException("Limit must be between 1 and 1000")

        try:
            logger.debug(
                f"Listing activities for supervisor: {supervisor_id}, "
                f"skip: {skip}, limit: {limit}"
            )
            
            entries = self.activity_repo.get_activities(
                db=db,
                supervisor_id=supervisor_id,
                filters=filters,
                skip=skip,
                limit=limit,
            )
            
            logger.debug(f"Found {len(entries)} activities for supervisor: {supervisor_id}")
            return [ActivityDetail.model_validate(e) for e in entries]
            
        except Exception as e:
            logger.error(
                f"Failed to list activities for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to list activities: {str(e)}")

    # -------------------------------------------------------------------------
    # Analytics Operations
    # -------------------------------------------------------------------------

    def get_activity_timeline(
        self,
        db: Session,
        supervisor_id: UUID,
        filters: ActivityFilterParams,
        group_by: str = "day",
    ) -> Dict[str, Any]:
        """
        Get activity timeline grouped by time period.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            filters: Filter parameters
            group_by: Grouping period ("hour", "day", "week", "month")

        Returns:
            Dict[str, Any]: Timeline data with activity counts per period

        Raises:
            ValidationException: If validation fails

        Example:
            >>> timeline = service.get_activity_timeline(
            ...     db, supervisor_id, filters, group_by="day"
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if group_by not in ["hour", "day", "week", "month"]:
            raise ValidationException(
                "group_by must be one of: hour, day, week, month"
            )

        try:
            logger.debug(
                f"Getting activity timeline for supervisor: {supervisor_id}, "
                f"group_by: {group_by}"
            )
            
            timeline_data = self.activity_repo.get_activity_timeline(
                db=db,
                supervisor_id=supervisor_id,
                filters=filters,
                group_by=group_by,
            )
            
            return timeline_data or {}
            
        except Exception as e:
            logger.error(
                f"Failed to get activity timeline for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve activity timeline: {str(e)}")

    def get_activity_count(
        self,
        db: Session,
        supervisor_id: UUID,
        filters: ActivityFilterParams,
    ) -> int:
        """
        Get total count of activities matching filters.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            filters: Filter parameters

        Returns:
            int: Total count of matching activities

        Example:
            >>> count = service.get_activity_count(db, supervisor_id, filters)
        """
        if not db or not supervisor_id or not filters:
            return 0
        
        try:
            return self.activity_repo.count_activities(
                db=db,
                supervisor_id=supervisor_id,
                filters=filters,
            )
        except Exception as e:
            logger.error(f"Failed to get activity count: {str(e)}")
            return 0