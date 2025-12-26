"""
Saved Search Service

Manages visitor saved searches and their execution metadata.

This service orchestrates:
- CRUD operations for saved searches
- Search execution with result tracking
- Match recording and notification management
- Search performance analytics
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any, Callable
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

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
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
)
from app.core.logging import LoggingContext

logger = logging.getLogger(__name__)


class SavedSearchService:
    """
    High-level orchestration for visitor saved searches.

    Responsibilities:
    - Create/update/delete saved searches with validation
    - List saved searches for a visitor with filtering
    - Execute saved searches and persist execution metadata
    - Record matches and manage notifications
    - Track search performance metrics
    """

    def __init__(
        self,
        saved_search_repo: SavedSearchRepository,
        saved_search_exec_repo: SavedSearchExecutionRepository,
        saved_search_match_repo: SavedSearchMatchRepository,
        saved_search_notification_repo: SavedSearchNotificationRepository,
    ) -> None:
        """
        Initialize the saved search service.

        Args:
            saved_search_repo: Repository for saved search operations
            saved_search_exec_repo: Repository for execution tracking
            saved_search_match_repo: Repository for match recording
            saved_search_notification_repo: Repository for notification management
        """
        self.saved_search_repo = saved_search_repo
        self.saved_search_exec_repo = saved_search_exec_repo
        self.saved_search_match_repo = saved_search_match_repo
        self.saved_search_notification_repo = saved_search_notification_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_saved_search(
        self,
        db: Session,
        visitor_id: UUID,
        preferences: SearchPreferences,
    ) -> SavedSearch:
        """
        Create a new saved search for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            preferences: Search preferences and criteria

        Returns:
            SavedSearch: The created saved search

        Raises:
            ValidationException: If preferences are invalid
            ServiceException: If creation fails
        """
        try:
            # Validate search name
            if not preferences.search_name or not preferences.search_name.strip():
                raise ValidationException("Search name is required and cannot be empty")

            # Extract and validate criteria
            criteria: Dict[str, Any] = preferences.model_dump(
                exclude_none=True,
                exclude={'search_name', 'notify_on_new_matches', 'notification_frequency'}
            )

            if not criteria:
                raise ValidationException("Search criteria cannot be empty")

            # Prepare data for creation
            search_data = {
                "visitor_id": visitor_id,
                "search_name": preferences.search_name.strip(),
                "criteria": criteria,
                "notify_on_new_matches": preferences.notify_on_new_matches or False,
                "notification_frequency": preferences.notification_frequency,
            }

            saved_search = self.saved_search_repo.create(db, data=search_data)
            
            logger.info(
                f"Created saved search '{saved_search.search_name}' "
                f"for visitor {visitor_id}"
            )
            
            return SavedSearch.model_validate(saved_search)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to create saved search for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to create saved search: {str(e)}")

    def update_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        preferences: SearchPreferences,
        visitor_id: Optional[UUID] = None,
    ) -> SavedSearch:
        """
        Update an existing saved search.

        Args:
            db: Database session
            saved_search_id: UUID of the saved search to update
            preferences: Updated search preferences
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            SavedSearch: The updated saved search

        Raises:
            NotFoundException: If saved search doesn't exist
            ValidationException: If update data is invalid or ownership check fails
            ServiceException: If update fails
        """
        try:
            existing = self.saved_search_repo.get_by_id(db, saved_search_id)
            if not existing:
                raise NotFoundException(
                    f"Saved search {saved_search_id} not found"
                )

            # Verify ownership if visitor_id provided
            if visitor_id and existing.visitor_id != visitor_id:
                raise ValidationException(
                    "Cannot update saved search belonging to another visitor"
                )

            # Prepare update data
            update_data: Dict[str, Any] = {}
            
            if preferences.search_name:
                update_data["search_name"] = preferences.search_name.strip()

            # Extract criteria, excluding meta fields
            criteria: Dict[str, Any] = preferences.model_dump(
                exclude_none=True,
                exclude={'search_name', 'notify_on_new_matches', 'notification_frequency'}
            )
            
            if criteria:
                update_data["criteria"] = criteria

            if preferences.notify_on_new_matches is not None:
                update_data["notify_on_new_matches"] = preferences.notify_on_new_matches

            if preferences.notification_frequency is not None:
                update_data["notification_frequency"] = preferences.notification_frequency

            updated = self.saved_search_repo.update(db, obj=existing, data=update_data)
            
            logger.info(f"Updated saved search {saved_search_id}")
            
            return SavedSearch.model_validate(updated)

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to update saved search {saved_search_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to update saved search: {str(e)}")

    def delete_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        visitor_id: Optional[UUID] = None,
    ) -> None:
        """
        Delete a saved search.

        Args:
            db: Database session
            saved_search_id: UUID of the saved search to delete
            visitor_id: Optional visitor ID for ownership validation

        Raises:
            ValidationException: If ownership check fails
            ServiceException: If deletion fails
        """
        try:
            existing = self.saved_search_repo.get_by_id(db, saved_search_id)
            if not existing:
                logger.warning(f"Attempt to delete non-existent saved search {saved_search_id}")
                return

            # Verify ownership if visitor_id provided
            if visitor_id and existing.visitor_id != visitor_id:
                raise ValidationException(
                    "Cannot delete saved search belonging to another visitor"
                )

            self.saved_search_repo.delete(db, existing)
            
            logger.info(
                f"Deleted saved search {saved_search_id} "
                f"for visitor {existing.visitor_id}"
            )

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to delete saved search {saved_search_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to delete saved search: {str(e)}")

    def list_saved_searches(
        self,
        db: Session,
        visitor_id: UUID,
        active_only: bool = True,
    ) -> List[SavedSearch]:
        """
        List all saved searches for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            active_only: If True, only return non-deleted searches

        Returns:
            List[SavedSearch]: List of saved searches

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            searches = self.saved_search_repo.get_by_visitor_id(
                db, 
                visitor_id,
                active_only=active_only
            )
            
            return [SavedSearch.model_validate(s) for s in searches]

        except Exception as e:
            logger.error(
                f"Failed to list saved searches for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve saved searches: {str(e)}")

    def get_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        visitor_id: Optional[UUID] = None,
    ) -> SavedSearch:
        """
        Get a specific saved search by ID.

        Args:
            db: Database session
            saved_search_id: UUID of the saved search
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            SavedSearch: The saved search

        Raises:
            NotFoundException: If saved search doesn't exist
            ValidationException: If ownership check fails
        """
        saved_search = self.saved_search_repo.get_by_id(db, saved_search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {saved_search_id} not found")

        if visitor_id and saved_search.visitor_id != visitor_id:
            raise ValidationException(
                "Cannot access saved search belonging to another visitor"
            )

        return SavedSearch.model_validate(saved_search)

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def execute_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        search_function: Callable[[AdvancedSearchRequest], FacetedSearchResponse],
        visitor_id: Optional[UUID] = None,
    ) -> FacetedSearchResponse:
        """
        Execute a saved search by delegating to a provided search function.

        This method:
        1. Validates the saved search exists and belongs to the visitor
        2. Reconstructs the search request from stored criteria
        3. Executes the search via the provided function
        4. Records execution metadata and matches
        5. Updates search statistics

        Args:
            db: Database session
            saved_search_id: UUID of the saved search
            search_function: Callable that executes the search
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            FacetedSearchResponse: Search results with facets

        Raises:
            NotFoundException: If saved search doesn't exist
            ValidationException: If saved search is invalid or ownership fails
            ServiceException: If execution fails
        """
        try:
            saved_search = self.saved_search_repo.get_by_id(db, saved_search_id)
            if not saved_search:
                raise NotFoundException(f"Saved search {saved_search_id} not found")

            # Verify ownership if visitor_id provided
            if visitor_id and saved_search.visitor_id != visitor_id:
                raise ValidationException(
                    "Cannot execute saved search belonging to another visitor"
                )

            # Rebuild AdvancedSearchRequest from stored criteria
            criteria: Dict[str, Any] = saved_search.criteria or {}
            if not criteria:
                raise ValidationException("Saved search has no criteria")

            try:
                request = AdvancedSearchRequest(**criteria)
            except Exception as e:
                logger.error(f"Invalid search criteria in saved search {saved_search_id}: {e}")
                raise ValidationException(f"Invalid search criteria: {str(e)}")

            execution_start = datetime.utcnow()

            with LoggingContext(
                saved_search_id=str(saved_search_id),
                visitor_id=str(saved_search.visitor_id),
                search_name=saved_search.search_name,
            ):
                # Execute the search
                try:
                    result: FacetedSearchResponse = search_function(request)
                except Exception as e:
                    logger.error(f"Search function failed: {str(e)}", exc_info=True)
                    raise ServiceException(f"Search execution failed: {str(e)}")

                execution_end = datetime.utcnow()
                execution_time_ms = int((execution_end - execution_start).total_seconds() * 1000)

                # Record execution metadata
                execution = self.saved_search_exec_repo.create(
                    db,
                    data={
                        "saved_search_id": saved_search.id,
                        "executed_at": execution_end,
                        "result_count": len(result.results),
                        "criteria_snapshot": criteria,
                        "execution_time_ms": execution_time_ms,
                    },
                )

                # Record matches (hostel IDs) as a snapshot
                if result.results:
                    hostel_ids = [r.id for r in result.results]
                    self.saved_search_match_repo.record_matches_for_execution(
                        db,
                        execution_id=execution.id,
                        hostel_ids=hostel_ids,
                    )

                # Update saved search execution statistics
                self.saved_search_repo.update_execution_stats(
                    db,
                    saved_search=saved_search,
                    result_count=len(result.results),
                    executed_at=execution.executed_at,
                )

                logger.info(
                    f"Executed saved search {saved_search_id}: "
                    f"{len(result.results)} results in {execution_time_ms}ms"
                )

            return result

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to execute saved search {saved_search_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to execute saved search: {str(e)}")

    def get_execution_history(
        self,
        db: Session,
        saved_search_id: UUID,
        limit: int = 10,
        visitor_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for a saved search.

        Args:
            db: Database session
            saved_search_id: UUID of the saved search
            limit: Maximum number of executions to return
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            List of execution records with metadata

        Raises:
            NotFoundException: If saved search doesn't exist
            ValidationException: If ownership check fails
        """
        saved_search = self.saved_search_repo.get_by_id(db, saved_search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {saved_search_id} not found")

        if visitor_id and saved_search.visitor_id != visitor_id:
            raise ValidationException(
                "Cannot access execution history for another visitor's search"
            )

        executions = self.saved_search_exec_repo.get_by_saved_search_id(
            db,
            saved_search_id,
            limit=limit
        )

        return [
            {
                "id": str(exec.id),
                "executed_at": exec.executed_at,
                "result_count": exec.result_count,
                "execution_time_ms": getattr(exec, 'execution_time_ms', None),
            }
            for exec in executions
        ]

    # -------------------------------------------------------------------------
    # Notification Management
    # -------------------------------------------------------------------------

    def record_notification_for_saved_search(
        self,
        db: Session,
        saved_search_id: UUID,
        notification_id: UUID,
        match_ids: List[UUID],
        visitor_id: Optional[UUID] = None,
    ) -> None:
        """
        Record that a notification was sent for a saved search execution.

        Args:
            db: Database session
            saved_search_id: UUID of the saved search
            notification_id: UUID of the notification sent
            match_ids: List of hostel IDs that matched
            visitor_id: Optional visitor ID for ownership validation

        Raises:
            NotFoundException: If saved search doesn't exist
            ValidationException: If ownership check fails or data is invalid
            ServiceException: If recording fails
        """
        try:
            saved_search = self.saved_search_repo.get_by_id(db, saved_search_id)
            if not saved_search:
                raise NotFoundException(f"Saved search {saved_search_id} not found")

            # Verify ownership if visitor_id provided
            if visitor_id and saved_search.visitor_id != visitor_id:
                raise ValidationException(
                    "Cannot record notification for another visitor's search"
                )

            if not match_ids:
                logger.warning(
                    f"Recording notification for saved search {saved_search_id} "
                    f"with no matches"
                )

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

            logger.info(
                f"Recorded notification {notification_id} for saved search "
                f"{saved_search_id} with {len(match_ids)} matches"
            )

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to record notification for saved search {saved_search_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to record notification: {str(e)}")

    def get_searches_pending_notification(
        self,
        db: Session,
        frequency: Optional[str] = None,
    ) -> List[SavedSearch]:
        """
        Get saved searches that are pending notification.

        Args:
            db: Database session
            frequency: Optional filter by notification frequency

        Returns:
            List of saved searches eligible for notification

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            searches = self.saved_search_repo.get_pending_notifications(
                db,
                frequency=frequency
            )
            return [SavedSearch.model_validate(s) for s in searches]

        except Exception as e:
            logger.error(
                f"Failed to get searches pending notification: {str(e)}",
                exc_info=True
            )
            raise ServiceException(
                f"Failed to retrieve searches pending notification: {str(e)}"
            )