"""
Supervisor Activity Service

Logs and queries supervisor activity and metrics.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorActivityRepository
from app.schemas.supervisor import (
    SupervisorActivityLog,
    ActivitySummary,
    ActivityDetail,
    ActivityFilterParams,
)
from app.core.exceptions import ValidationException


class SupervisorActivityService:
    """
    High-level service for supervisor activities.

    Responsibilities:
    - Log activity entries
    - Query activities with filters
    - Build activity summaries and timelines
    """

    def __init__(
        self,
        activity_repo: SupervisorActivityRepository,
    ) -> None:
        self.activity_repo = activity_repo

    # -------------------------------------------------------------------------
    # Logging
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
        metadata: Optional[dict] = None,
    ) -> SupervisorActivityLog:
        """
        Log a single supervisor activity entry.
        """
        obj = self.activity_repo.log_activity(
            db=db,
            supervisor_id=supervisor_id,
            action_type=action_type,
            action_category=action_category,
            entity_type=entity_type,
            entity_id=entity_id,
            success=success,
            metadata=metadata or {},
        )
        return SupervisorActivityLog.model_validate(obj)

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    def get_activity_summary(
        self,
        db: Session,
        supervisor_id: UUID,
        filters: ActivityFilterParams,
    ) -> ActivitySummary:
        """
        Get aggregated activity summary for a supervisor given filters.
        """
        summary_dict = self.activity_repo.get_summary(
            db=db,
            supervisor_id=supervisor_id,
            filters=filters,
        )
        if not summary_dict:
            # Summary may be empty but still valid; in that case, repo should
            # return a default dict. We only error if None.
            raise ValidationException("No activity summary available")
        return ActivitySummary.model_validate(summary_dict)

    def list_activities(
        self,
        db: Session,
        supervisor_id: UUID,
        filters: ActivityFilterParams,
    ) -> List[ActivityDetail]:
        """
        List activity entries matching filters (detailed view).
        """
        entries = self.activity_repo.get_activities(
            db=db,
            supervisor_id=supervisor_id,
            filters=filters,
        )
        return [ActivityDetail.model_validate(e) for e in entries]