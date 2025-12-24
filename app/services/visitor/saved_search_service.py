"""
Saved Search Service

Manages visitor saved searches and their execution metadata.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    SavedSearchRepository,
    SavedSearchExecutionRepository,
    SavedSearchMatchRepository,
    SavedSearchNotificationRepository,
)
from app.schemas.visitor import SearchPreferences, SavedSearch
from app.schemas.search import (
    AdvancedSearchRequest,
    SearchResultItem,
    SearchMetadata,
    FacetedSearchResponse,
)
from app.core.exceptions import ValidationException
from app.core.logging import LoggingContext


class SavedSearchService:
    """
    High-level orchestration for visitor saved searches.

    Responsibilities:
    - Create/update/delete saved searches
    - List saved searches for a visitor
    - Execute a saved search and persist execution metadata
    - Record matches and notifications
    """

    def __init__(
        self,
        saved_search_repo: SavedSearchRepository,
        saved_search_exec_repo: SavedSearchExecutionRepository,
        saved_search_match_repo: SavedSearchMatchRepository,
        saved_search_notification_repo: SavedSearchNotificationRepository,
    ) -> None:
        self.saved_search_repo = saved_search_repo
        self.saved_search_exec_repo = saved_search_exec_repo
        self.saved_search_match_repo = saved_search_match_repo
        self.saved_search_notification_repo = saved_search_notification_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_saved_search(
        self,
        db: Session,
        visitor_id: UUID,
        preferences: SearchPreferences,
    ) -> SavedSearch:
        """
        Create a new saved search for a visitor.
        """
        criteria: Dict[str, Any] = preferences.model_dump(exclude_none=True)

        saved_search = self.saved_search_repo.create(
            db,
            data={
                "visitor_id": visitor_id,
                "search_name": preferences.search_name,
                "criteria": criteria,
                "notify_on_new_matches": preferences.notify_on_new_matches,
                "notification_frequency": preferences.notification_frequency,
            },
        )
        return SavedSearch.model_validate(saved_search)

    def update_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        preferences: SearchPreferences,
    ) -> SavedSearch:
        """
        Update an existing saved search.
        """
        existing = self.saved_search_repo.get_by_id(db, saved_search_id)
        if not existing:
            raise ValidationException("Saved search not found")

        criteria: Dict[str, Any] = preferences.model_dump(exclude_none=True)

        updated = self.saved_search_repo.update(
            db,
            obj=existing,
            data={
                "search_name": preferences.search_name or existing.search_name,
                "criteria": criteria,
                "notify_on_new_matches": preferences.notify_on_new_matches,
                "notification_frequency": preferences.notification_frequency,
            },
        )
        return SavedSearch.model_validate(updated)

    def delete_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
    ) -> None:
        """
        Delete a saved search.
        """
        existing = self.saved_search_repo.get_by_id(db, saved_search_id)
        if not existing:
            return
        self.saved_search_repo.delete(db, existing)

    def list_saved_searches(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> List[SavedSearch]:
        """
        List all saved searches for a visitor.
        """
        searches = self.saved_search_repo.get_by_visitor_id(db, visitor_id)
        return [SavedSearch.model_validate(s) for s in searches]

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def execute_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        search_function: callable,
    ) -> FacetedSearchResponse:
        """
        Execute a saved search by delegating to a provided search function.

        Args:
            db: DB session
            saved_search_id: ID of visitor.SavedSearch
            search_function: Callable taking AdvancedSearchRequest and returning FacetedSearchResponse

        Returns:
            FacetedSearchResponse with results
        """
        saved_search = self.saved_search_repo.get_by_id(db, saved_search_id)
        if not saved_search:
            raise ValidationException("Saved search not found")

        # Rebuild AdvancedSearchRequest from stored criteria
        criteria: Dict[str, Any] = saved_search.criteria or {}
        request = AdvancedSearchRequest(**criteria)

        with LoggingContext(
            saved_search_id=str(saved_search_id),
            visitor_id=str(saved_search.visitor_id),
        ):
            result: FacetedSearchResponse = search_function(request)

            # Record execution
            execution = self.saved_search_exec_repo.create(
                db,
                data={
                    "saved_search_id": saved_search.id,
                    "executed_at": datetime.utcnow(),
                    "result_count": len(result.results),
                    "criteria_snapshot": criteria,
                },
            )

            # Record matches (hostels) as a snapshot
            hostel_ids = [r.id for r in result.results]
            self.saved_search_match_repo.record_matches_for_execution(
                db,
                execution_id=execution.id,
                hostel_ids=hostel_ids,
            )

            # Update saved search metadata
            self.saved_search_repo.update_execution_stats(
                db,
                saved_search=saved_search,
                result_count=len(result.results),
                executed_at=execution.executed_at,
            )

        return result

    # -------------------------------------------------------------------------
    # Notification helpers
    # -------------------------------------------------------------------------

    def record_notification_for_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        notification_id: UUID,
        match_ids: List[UUID],
    ) -> None:
        """
        Record that a notification was sent for a saved search execution.
        """
        saved_search = self.saved_search_repo.get_by_id(db, saved_search_id)
        if not saved_search:
            raise ValidationException("Saved search not found")

        self.saved_search_notification_repo.create(
            db,
            data={
                "saved_search_id": saved_search.id,
                "notification_id": notification_id,
                "match_ids": match_ids,
                "sent_at": datetime.utcnow(),
            },
        )

        self.saved_search_repo.increment_notification_count(db, saved_search)