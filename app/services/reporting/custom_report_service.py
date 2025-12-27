# app/services/reporting/custom_report_service.py
"""
Custom Report Service

Handles definition, execution, caching, and history for custom reports
with enhanced validation, error handling, and performance optimization.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.analytics import (
    CustomReportRequest,
    CustomReportDefinition,
    CustomReportResult,
)
from app.repositories.analytics import CustomReportsRepository
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    AuthorizationException,
)
from app.utils.metrics import track_performance
from app.utils.cache_utils import invalidate_cache

logger = logging.getLogger(__name__)


class CustomReportService:
    """
    High-level orchestration for the custom reporting system.

    Responsibilities:
    - Create/update/delete saved report definitions with validation
    - Execute ad-hoc or saved reports with caching
    - Manage cached results & execution history
    - Enforce access control and rate limiting

    Attributes:
        custom_reports_repo: Repository for custom report operations
        max_cache_age_hours: Maximum age for cached results (default: 24)
        max_report_rows: Maximum rows per report (default: 100000)
    """

    def __init__(
        self,
        custom_reports_repo: CustomReportsRepository,
        max_cache_age_hours: int = 24,
        max_report_rows: int = 100000,
    ) -> None:
        """
        Initialize the custom report service.

        Args:
            custom_reports_repo: Repository for custom reports
            max_cache_age_hours: Maximum cache age in hours
            max_report_rows: Maximum rows allowed per report
        """
        if not custom_reports_repo:
            raise ValueError("CustomReportsRepository cannot be None")
        
        self.custom_reports_repo = custom_reports_repo
        self.max_cache_age_hours = max_cache_age_hours
        self.max_report_rows = max_report_rows
        
        logger.info(
            f"CustomReportService initialized with max_cache_age={max_cache_age_hours}h, "
            f"max_rows={max_report_rows}"
        )

    # -------------------------------------------------------------------------
    # Definition Management
    # -------------------------------------------------------------------------

    def _validate_report_request(self, request: CustomReportRequest) -> None:
        """
        Validate custom report request.

        Args:
            request: Report request to validate

        Raises:
            ValidationException: If validation fails
        """
        if not request.name or not request.name.strip():
            raise ValidationException("Report name is required")
        
        if len(request.name) > 255:
            raise ValidationException("Report name cannot exceed 255 characters")
        
        if not request.data_source:
            raise ValidationException("Data source is required")
        
        # Validate metric and dimension limits
        if hasattr(request, 'metrics') and request.metrics:
            if len(request.metrics) > 50:
                raise ValidationException("Cannot exceed 50 metrics per report")
        
        if hasattr(request, 'dimensions') and request.dimensions:
            if len(request.dimensions) > 20:
                raise ValidationException("Cannot exceed 20 dimensions per report")

    @track_performance("create_report_definition")
    def create_definition(
        self,
        db: Session,
        owner_id: UUID,
        request: CustomReportRequest,
    ) -> CustomReportDefinition:
        """
        Create a new custom report definition with validation.

        Args:
            db: Database session
            owner_id: ID of the report owner
            request: Custom report request

        Returns:
            CustomReportDefinition: Created report definition

        Raises:
            ValidationException: If validation fails
            SQLAlchemyError: If database operation fails
        """
        logger.info(f"Creating report definition '{request.name}' for owner {owner_id}")
        
        try:
            # Validate request
            self._validate_report_request(request)
            
            # Check for duplicate names for this owner
            existing = self.custom_reports_repo.get_definition_by_name(
                db, owner_id, request.name
            )
            if existing:
                raise ValidationException(
                    f"Report definition with name '{request.name}' already exists"
                )
            
            # Prepare payload
            payload = request.model_dump(exclude_none=True)
            payload["owner_id"] = owner_id
            payload["created_at"] = datetime.utcnow()
            payload["updated_at"] = datetime.utcnow()
            
            # Create definition
            obj = self.custom_reports_repo.create_definition(db, payload)
            
            logger.info(
                f"Successfully created report definition {obj.id} for owner {owner_id}"
            )
            
            return CustomReportDefinition.model_validate(obj)
            
        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating report definition: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to create report definition: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating report definition: {str(e)}")
            db.rollback()
            raise

    @track_performance("update_report_definition")
    def update_definition(
        self,
        db: Session,
        definition_id: UUID,
        request: CustomReportRequest,
        owner_id: Optional[UUID] = None,
    ) -> CustomReportDefinition:
        """
        Update an existing custom report definition.

        Args:
            db: Database session
            definition_id: ID of definition to update
            request: Updated report request
            owner_id: Optional owner ID for authorization check

        Returns:
            CustomReportDefinition: Updated definition

        Raises:
            NotFoundException: If definition not found
            AuthorizationException: If owner_id doesn't match
            ValidationException: If validation fails
        """
        logger.info(f"Updating report definition {definition_id}")
        
        try:
            # Fetch existing definition
            definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
            if not definition:
                raise NotFoundException(f"Report definition {definition_id} not found")
            
            # Check authorization
            if owner_id and definition.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to update this report definition"
                )
            
            # Validate request
            self._validate_report_request(request)
            
            # Check for name conflicts (excluding current definition)
            if request.name != definition.name:
                existing = self.custom_reports_repo.get_definition_by_name(
                    db, definition.owner_id, request.name
                )
                if existing and existing.id != definition_id:
                    raise ValidationException(
                        f"Report definition with name '{request.name}' already exists"
                    )
            
            # Update definition
            update_data = request.model_dump(exclude_none=True)
            update_data["updated_at"] = datetime.utcnow()
            
            updated = self.custom_reports_repo.update_definition(
                db=db,
                definition=definition,
                data=update_data,
            )
            
            # Invalidate related caches
            invalidate_cache(f"report_def_{definition_id}")
            
            logger.info(f"Successfully updated report definition {definition_id}")
            
            return CustomReportDefinition.model_validate(updated)
            
        except (NotFoundException, AuthorizationException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating report definition: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to update report definition: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error updating report definition: {str(e)}")
            db.rollback()
            raise

    @track_performance("delete_report_definition")
    def delete_definition(
        self,
        db: Session,
        definition_id: UUID,
        owner_id: UUID,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete a custom report definition (soft delete by default).

        Args:
            db: Database session
            definition_id: ID of definition to delete
            owner_id: Owner ID for authorization
            hard_delete: If True, permanently delete; otherwise soft delete

        Raises:
            NotFoundException: If definition not found
            AuthorizationException: If owner_id doesn't match
        """
        logger.info(
            f"Deleting report definition {definition_id} "
            f"(hard_delete={hard_delete})"
        )
        
        try:
            definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
            
            if not definition:
                logger.warning(f"Report definition {definition_id} not found")
                return
            
            if definition.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to delete this report definition"
                )
            
            self.custom_reports_repo.delete_definition(
                db, definition, hard_delete=hard_delete
            )
            
            # Invalidate caches
            invalidate_cache(f"report_def_{definition_id}")
            invalidate_cache(f"report_owner_{owner_id}")
            
            logger.info(f"Successfully deleted report definition {definition_id}")
            
        except AuthorizationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting report definition: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to delete report definition: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting report definition: {str(e)}")
            db.rollback()
            raise

    def list_definitions_for_owner(
        self,
        db: Session,
        owner_id: UUID,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CustomReportDefinition]:
        """
        List all report definitions for an owner with pagination.

        Args:
            db: Database session
            owner_id: Owner ID
            include_archived: Whether to include soft-deleted definitions
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of CustomReportDefinition objects
        """
        logger.info(
            f"Listing report definitions for owner {owner_id} "
            f"(limit={limit}, offset={offset})"
        )
        
        try:
            objs = self.custom_reports_repo.get_definitions_by_owner(
                db=db,
                owner_id=owner_id,
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            )
            
            definitions = [CustomReportDefinition.model_validate(o) for o in objs]
            
            logger.info(f"Found {len(definitions)} report definitions")
            
            return definitions
            
        except Exception as e:
            logger.error(f"Error listing report definitions: {str(e)}")
            raise ValidationException(f"Failed to list report definitions: {str(e)}")

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def _validate_cache_freshness(
        self,
        cached_result: Any,
        max_age_hours: Optional[int] = None,
    ) -> bool:
        """
        Check if cached result is still fresh.

        Args:
            cached_result: Cached result object
            max_age_hours: Maximum age in hours (uses default if None)

        Returns:
            True if cache is fresh, False otherwise
        """
        if not cached_result or not hasattr(cached_result, 'generated_at'):
            return False
        
        max_age = max_age_hours or self.max_cache_age_hours
        age = datetime.utcnow() - cached_result.generated_at
        
        return age <= timedelta(hours=max_age)

    @track_performance("run_custom_report")
    def run_report(
        self,
        db: Session,
        request: CustomReportRequest,
        owner_id: Optional[UUID] = None,
        use_cache: bool = True,
        max_cache_age_hours: Optional[int] = None,
    ) -> CustomReportResult:
        """
        Execute a custom report from a request (without saving definition).

        Args:
            db: Database session
            request: Custom report request
            owner_id: Optional owner ID to attribute execution
            use_cache: Whether to use cached results if available
            max_cache_age_hours: Override default cache age

        Returns:
            CustomReportResult: Report execution result

        Raises:
            ValidationException: If validation or execution fails
        """
        logger.info(
            f"Executing custom report '{request.name}' "
            f"(use_cache={use_cache}, owner={owner_id})"
        )
        
        try:
            # Validate request
            self._validate_report_request(request)
            
            payload = request.model_dump(exclude_none=True)
            
            # Execute report
            result_data = self.custom_reports_repo.execute_report_from_request(
                db=db,
                request_data=payload,
                owner_id=owner_id,
                use_cache=use_cache,
            )
            
            if not result_data:
                raise ValidationException("Report execution returned no data")
            
            # Validate result
            result = CustomReportResult.model_validate(result_data)
            
            # Check row limit
            if result.rows and len(result.rows) > self.max_report_rows:
                logger.warning(
                    f"Report exceeded max rows ({len(result.rows)} > {self.max_report_rows})"
                )
                raise ValidationException(
                    f"Report result exceeds maximum row limit of {self.max_report_rows}"
                )
            
            logger.info(
                f"Successfully executed report with {len(result.rows) if result.rows else 0} rows"
            )
            
            return result
            
        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error executing report: {str(e)}")
            raise ValidationException(f"Failed to execute report: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error executing report: {str(e)}")
            raise ValidationException(f"Report execution failed: {str(e)}")

    @track_performance("run_saved_report")
    def run_saved_report(
        self,
        db: Session,
        definition_id: UUID,
        parameters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        owner_id: Optional[UUID] = None,
    ) -> CustomReportResult:
        """
        Execute a saved report definition with optional parameters.

        Args:
            db: Database session
            definition_id: ID of saved report definition
            parameters: Optional runtime parameters
            use_cache: Whether to use cached results
            owner_id: Optional owner ID for authorization

        Returns:
            CustomReportResult: Report execution result

        Raises:
            NotFoundException: If definition not found
            AuthorizationException: If not authorized
            ValidationException: If execution fails
        """
        logger.info(
            f"Executing saved report {definition_id} "
            f"(use_cache={use_cache})"
        )
        
        try:
            # Fetch definition
            definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
            if not definition:
                raise NotFoundException(f"Report definition {definition_id} not found")
            
            # Check authorization if owner_id provided
            if owner_id and definition.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to execute this report"
                )
            
            # Execute report
            result_data = self.custom_reports_repo.execute_saved_report(
                db=db,
                definition=definition,
                parameters=parameters or {},
                use_cache=use_cache,
            )
            
            if not result_data:
                raise ValidationException("Report execution returned no data")
            
            result = CustomReportResult.model_validate(result_data)
            
            # Check row limit
            if result.rows and len(result.rows) > self.max_report_rows:
                logger.warning(
                    f"Report exceeded max rows ({len(result.rows)} > {self.max_report_rows})"
                )
                raise ValidationException(
                    f"Report result exceeds maximum row limit of {self.max_report_rows}"
                )
            
            logger.info(
                f"Successfully executed saved report {definition_id} "
                f"with {len(result.rows) if result.rows else 0} rows"
            )
            
            return result
            
        except (NotFoundException, AuthorizationException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error executing saved report: {str(e)}")
            raise ValidationException(f"Failed to execute saved report: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error executing saved report: {str(e)}")
            raise ValidationException(f"Saved report execution failed: {str(e)}")

    def get_cached_result(
        self,
        db: Session,
        result_id: UUID,
        owner_id: Optional[UUID] = None,
        validate_freshness: bool = True,
    ) -> Optional[CustomReportResult]:
        """
        Retrieve a cached report result by ID with optional freshness check.

        Args:
            db: Database session
            result_id: ID of cached result
            owner_id: Optional owner ID for authorization
            validate_freshness: Whether to validate cache freshness

        Returns:
            CustomReportResult if found and valid, None otherwise

        Raises:
            AuthorizationException: If not authorized to access result
        """
        logger.info(f"Retrieving cached result {result_id}")
        
        try:
            cached = self.custom_reports_repo.get_cached_result_by_id(db, result_id)
            
            if not cached:
                logger.info(f"Cached result {result_id} not found")
                return None
            
            # Check authorization
            if owner_id and hasattr(cached, 'owner_id') and cached.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to access this cached result"
                )
            
            # Validate freshness if requested
            if validate_freshness and not self._validate_cache_freshness(cached):
                logger.info(f"Cached result {result_id} is stale")
                return None
            
            result = CustomReportResult.model_validate(cached)
            
            logger.info(f"Successfully retrieved cached result {result_id}")
            
            return result
            
        except AuthorizationException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving cached result: {str(e)}")
            return None

    def invalidate_cached_results(
        self,
        db: Session,
        definition_id: Optional[UUID] = None,
        owner_id: Optional[UUID] = None,
    ) -> int:
        """
        Invalidate cached results for a definition or owner.

        Args:
            db: Database session
            definition_id: Optional definition ID to target
            owner_id: Optional owner ID to target

        Returns:
            Number of cache entries invalidated
        """
        logger.info(
            f"Invalidating cached results "
            f"(definition_id={definition_id}, owner_id={owner_id})"
        )
        
        try:
            count = self.custom_reports_repo.invalidate_cached_results(
                db=db,
                definition_id=definition_id,
                owner_id=owner_id,
            )
            
            logger.info(f"Invalidated {count} cached results")
            
            return count
            
        except Exception as e:
            logger.error(f"Error invalidating cached results: {str(e)}")
            return 0