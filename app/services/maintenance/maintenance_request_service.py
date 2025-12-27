"""
Maintenance Request Service

Handles the complete lifecycle of maintenance requests with enhanced error handling,
validation, and performance optimizations.

Features:
- Resident/supervisor/emergency submission with validation
- Advanced filtering and sorting with pagination
- Comprehensive request retrieval with caching support
- Performance metrics and logging
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceRequestRepository
from app.schemas.maintenance import (
    MaintenanceRequest as MaintenanceRequestSchema,
    RequestSubmission,
    EmergencyRequest,
    MaintenanceResponse,
    MaintenanceDetail,
    RequestListItem,
    MaintenanceSummary,
    MaintenanceFilterParams,
    MaintenanceSortOptions,
)
from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import LoggingContext, logger


class MaintenanceRequestService:
    """
    High-level orchestration for maintenance requests.

    This service provides a clean interface for managing maintenance requests
    while delegating persistence and complex queries to the repository layer.
    """

    def __init__(self, request_repo: MaintenanceRequestRepository) -> None:
        """
        Initialize the service with required repository.

        Args:
            request_repo: Repository for maintenance request persistence
        """
        if not request_repo:
            raise ValueError("MaintenanceRequestRepository is required")
        self.request_repo = request_repo

    # -------------------------------------------------------------------------
    # Request Creation Methods
    # -------------------------------------------------------------------------

    def create_resident_request(
        self,
        db: Session,
        request: MaintenanceRequestSchema,
    ) -> MaintenanceResponse:
        """
        Create a maintenance request submitted by a resident/student.

        Args:
            db: Database session
            request: Maintenance request data from resident

        Returns:
            MaintenanceResponse with created request details

        Raises:
            ValidationException: If request data is invalid
            BusinessLogicException: If business rules are violated
        """
        self._validate_request_data(request)
        
        payload = request.model_dump(exclude_none=True)
        hostel_id = payload.get("hostel_id")
        
        with LoggingContext(
            source="resident",
            hostel_id=str(hostel_id) if hostel_id else "unknown"
        ):
            try:
                logger.info(
                    f"Creating resident maintenance request for hostel {hostel_id}"
                )
                obj = self.request_repo.create_request(db, payload)
                logger.info(f"Successfully created request with ID: {obj.id}")
                return MaintenanceResponse.model_validate(obj)
            except Exception as e:
                logger.error(
                    f"Failed to create resident request: {str(e)}",
                    exc_info=True
                )
                raise

    def create_supervisor_submission(
        self,
        db: Session,
        request: RequestSubmission,
    ) -> MaintenanceResponse:
        """
        Create a maintenance request submitted by a supervisor/staff member.

        Supervisor requests typically include additional details such as
        estimated costs, priority adjustments, and assignment preferences.

        Args:
            db: Database session
            request: Request submission data from supervisor

        Returns:
            MaintenanceResponse with created request details

        Raises:
            ValidationException: If request data is invalid
            BusinessLogicException: If business rules are violated
        """
        self._validate_supervisor_request(request)
        
        payload = request.model_dump(exclude_none=True)
        hostel_id = payload.get("hostel_id")
        
        with LoggingContext(
            source="supervisor",
            hostel_id=str(hostel_id) if hostel_id else "unknown"
        ):
            try:
                logger.info(
                    f"Creating supervisor maintenance request for hostel {hostel_id}"
                )
                obj = self.request_repo.create_request(db, payload)
                logger.info(f"Successfully created supervisor request ID: {obj.id}")
                return MaintenanceResponse.model_validate(obj)
            except Exception as e:
                logger.error(
                    f"Failed to create supervisor request: {str(e)}",
                    exc_info=True
                )
                raise

    def create_emergency_request(
        self,
        db: Session,
        request: EmergencyRequest,
    ) -> MaintenanceResponse:
        """
        Create a high-priority emergency maintenance request.

        Emergency requests bypass standard approval workflows and are
        immediately escalated for assignment.

        Args:
            db: Database session
            request: Emergency request data

        Returns:
            MaintenanceResponse with created emergency request details

        Raises:
            ValidationException: If request data is invalid
        """
        self._validate_emergency_request(request)
        
        payload = request.model_dump(exclude_none=True)
        payload["is_emergency"] = True
        payload["priority"] = "critical"  # Override priority for emergencies
        
        hostel_id = payload.get("hostel_id")
        
        with LoggingContext(
            source="emergency",
            hostel_id=str(hostel_id) if hostel_id else "unknown"
        ):
            try:
                logger.warning(
                    f"Creating EMERGENCY maintenance request for hostel {hostel_id}"
                )
                obj = self.request_repo.create_request(db, payload)
                logger.warning(f"Emergency request created with ID: {obj.id}")
                
                # TODO: Trigger emergency notification workflow
                # self._notify_emergency_contacts(obj)
                
                return MaintenanceResponse.model_validate(obj)
            except Exception as e:
                logger.error(
                    f"Failed to create emergency request: {str(e)}",
                    exc_info=True
                )
                raise

    # -------------------------------------------------------------------------
    # Request Retrieval Methods
    # -------------------------------------------------------------------------

    def get_request(
        self,
        db: Session,
        request_id: UUID,
        include_history: bool = True,
    ) -> MaintenanceDetail:
        """
        Retrieve detailed information for a specific maintenance request.

        Args:
            db: Database session
            request_id: UUID of the request to retrieve
            include_history: Whether to include assignment/status history

        Returns:
            MaintenanceDetail with complete request information

        Raises:
            ValidationException: If request is not found
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        try:
            obj = self.request_repo.get_full_request(
                db,
                request_id,
                include_history=include_history
            )
            
            if not obj:
                raise ValidationException(
                    f"Maintenance request {request_id} not found"
                )
            
            return MaintenanceDetail.model_validate(obj)
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving request {request_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve maintenance request: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Listing and Search Methods
    # -------------------------------------------------------------------------

    def list_requests_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        filters: Optional[MaintenanceFilterParams] = None,
        sort: Optional[MaintenanceSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[RequestListItem], int, MaintenanceSummary]:
        """
        List maintenance requests for a hostel with filtering, sorting, and pagination.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            filters: Optional filtering parameters
            sort: Optional sorting parameters
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of requests, total count, summary statistics)

        Raises:
            ValidationException: If parameters are invalid
        """
        # Validate pagination parameters
        if page < 1:
            raise ValidationException("Page number must be >= 1")
        if page_size < 1 or page_size > 1000:
            raise ValidationException("Page size must be between 1 and 1000")

        # Prepare filter and sort dictionaries
        filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump(exclude_none=True) if sort else {}

        try:
            logger.debug(
                f"Listing requests for hostel {hostel_id} "
                f"(page={page}, size={page_size})"
            )
            
            result = self.request_repo.search_requests(
                db=db,
                hostel_id=hostel_id,
                filters=filters_dict,
                sort=sort_dict,
                page=page,
                page_size=page_size,
            )

            items = [
                RequestListItem.model_validate(item)
                for item in result.get("items", [])
            ]
            total = result.get("total", 0)
            summary = MaintenanceSummary.model_validate(
                result.get("summary", {})
            )

            logger.debug(
                f"Retrieved {len(items)} requests out of {total} total"
            )
            
            return items, total, summary

        except Exception as e:
            logger.error(
                f"Error listing requests for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve maintenance requests: {str(e)}"
            )

    def get_requests_by_status(
        self,
        db: Session,
        hostel_id: UUID,
        status: str,
        limit: int = 100,
    ) -> List[RequestListItem]:
        """
        Get maintenance requests filtered by status.

        Convenience method for common status-based queries.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status: Request status to filter by
            limit: Maximum number of results

        Returns:
            List of matching requests
        """
        filters = MaintenanceFilterParams(status=status)
        items, _, _ = self.list_requests_for_hostel(
            db=db,
            hostel_id=hostel_id,
            filters=filters,
            page=1,
            page_size=min(limit, 1000),
        )
        return items

    def get_overdue_requests(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 100,
    ) -> List[RequestListItem]:
        """
        Get overdue maintenance requests for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            limit: Maximum number of results

        Returns:
            List of overdue requests
        """
        filters = MaintenanceFilterParams(is_overdue=True)
        items, _, _ = self.list_requests_for_hostel(
            db=db,
            hostel_id=hostel_id,
            filters=filters,
            sort=MaintenanceSortOptions(sort_by="due_date", sort_order="asc"),
            page=1,
            page_size=min(limit, 1000),
        )
        return items

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_request_data(
        self,
        request: MaintenanceRequestSchema
    ) -> None:
        """
        Validate basic maintenance request data.

        Args:
            request: Request to validate

        Raises:
            ValidationException: If validation fails
        """
        if not request.hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if not request.description or len(request.description.strip()) < 10:
            raise ValidationException(
                "Description must be at least 10 characters"
            )
        
        if request.category and not self._is_valid_category(request.category):
            raise ValidationException(f"Invalid category: {request.category}")

    def _validate_supervisor_request(
        self,
        request: RequestSubmission
    ) -> None:
        """
        Validate supervisor request with additional business rules.

        Args:
            request: Supervisor request to validate

        Raises:
            ValidationException: If validation fails
        """
        self._validate_request_data(request)
        
        if request.estimated_cost and request.estimated_cost < 0:
            raise ValidationException("Estimated cost cannot be negative")
        
        if request.priority and request.priority not in [
            "low", "medium", "high", "critical"
        ]:
            raise ValidationException(f"Invalid priority: {request.priority}")

    def _validate_emergency_request(
        self,
        request: EmergencyRequest
    ) -> None:
        """
        Validate emergency request data.

        Args:
            request: Emergency request to validate

        Raises:
            ValidationException: If validation fails
        """
        self._validate_request_data(request)
        
        if not request.emergency_contact:
            raise ValidationException(
                "Emergency contact is required for emergency requests"
            )
        
        if not request.severity:
            raise ValidationException(
                "Severity level is required for emergency requests"
            )

    def _is_valid_category(self, category: str) -> bool:
        """
        Check if a category is valid.

        Args:
            category: Category to validate

        Returns:
            True if valid, False otherwise
        """
        valid_categories = {
            "plumbing",
            "electrical",
            "carpentry",
            "painting",
            "cleaning",
            "hvac",
            "pest_control",
            "appliance_repair",
            "structural",
            "other",
        }
        return category.lower() in valid_categories