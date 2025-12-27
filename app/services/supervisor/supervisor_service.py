"""
Supervisor Service

Core supervisor CRUD and retrieval operations with enhanced validation and error handling.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import (
    SupervisorRepository,
    SupervisorAggregateRepository,
)
from app.schemas.supervisor import (
    SupervisorCreate,
    SupervisorUpdate,
    SupervisorResponse,
    SupervisorDetail,
    SupervisorListItem,
    SupervisorProfile,
)
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorService:
    """
    High-level service for Supervisor entity operations.

    Responsibilities:
    - Create/update supervisors with validation
    - Get supervisor by id with full details
    - List supervisors (optionally by hostel) with pagination
    - Retrieve full profile (SupervisorProfile)
    - Handle supervisor lifecycle management

    Example:
        >>> service = SupervisorService(supervisor_repo, aggregate_repo)
        >>> supervisor = service.create_supervisor(db, SupervisorCreate(...))
        >>> profile = service.get_supervisor_profile(db, supervisor.id)
    """

    def __init__(
        self,
        supervisor_repo: SupervisorRepository,
        aggregate_repo: SupervisorAggregateRepository,
    ) -> None:
        """
        Initialize the supervisor service.

        Args:
            supervisor_repo: Repository for basic supervisor operations
            aggregate_repo: Repository for complex aggregated queries
        """
        if not supervisor_repo:
            raise ValueError("supervisor_repo cannot be None")
        if not aggregate_repo:
            raise ValueError("aggregate_repo cannot be None")
            
        self.supervisor_repo = supervisor_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_supervisor(
        self,
        db: Session,
        data: SupervisorCreate,
    ) -> SupervisorResponse:
        """
        Create a new supervisor record with initial assignment and employment info.

        The SupervisorCreate schema encapsulates employment & assignment details.

        Args:
            db: Database session
            data: Supervisor creation data including employment and assignment details

        Returns:
            SupervisorResponse: Created supervisor object

        Raises:
            ValidationException: If validation fails or supervisor creation is invalid

        Example:
            >>> data = SupervisorCreate(
            ...     user_id=user_id,
            ...     hostel_id=hostel_id,
            ...     employment_type="FULL_TIME"
            ... )
            >>> supervisor = service.create_supervisor(db, data)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not data:
            raise ValidationException("Supervisor data is required")

        try:
            logger.info(f"Creating new supervisor for user_id: {data.user_id}")
            
            obj = self.supervisor_repo.create(
                db,
                data=data.model_dump(exclude_none=True),
            )
            
            logger.info(f"Successfully created supervisor with ID: {obj.id}")
            return SupervisorResponse.model_validate(obj)
            
        except Exception as e:
            logger.error(f"Failed to create supervisor: {str(e)}")
            raise ValidationException(f"Failed to create supervisor: {str(e)}")

    def update_supervisor(
        self,
        db: Session,
        supervisor_id: UUID,
        data: SupervisorUpdate,
    ) -> SupervisorResponse:
        """
        Update supervisor information (employment, status, notes, etc.).

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor to update
            data: Partial update data

        Returns:
            SupervisorResponse: Updated supervisor object

        Raises:
            ValidationException: If supervisor not found or update fails

        Example:
            >>> update_data = SupervisorUpdate(employment_status="ACTIVE")
            >>> updated = service.update_supervisor(db, supervisor_id, update_data)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not data:
            raise ValidationException("Update data is required")

        try:
            logger.info(f"Updating supervisor: {supervisor_id}")
            
            supervisor = self.supervisor_repo.get_by_id(db, supervisor_id)
            if not supervisor:
                logger.warning(f"Supervisor not found: {supervisor_id}")
                raise ValidationException(
                    f"Supervisor not found with ID: {supervisor_id}"
                )

            update_dict = data.model_dump(exclude_none=True)
            if not update_dict:
                logger.warning(f"No update data provided for supervisor: {supervisor_id}")
                raise ValidationException("No update data provided")

            updated = self.supervisor_repo.update(db, supervisor, update_dict)
            
            logger.info(f"Successfully updated supervisor: {supervisor_id}")
            return SupervisorResponse.model_validate(updated)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to update supervisor {supervisor_id}: {str(e)}")
            raise ValidationException(f"Failed to update supervisor: {str(e)}")

    # -------------------------------------------------------------------------
    # Retrieval Operations
    # -------------------------------------------------------------------------

    def get_supervisor(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorDetail:
        """
        Retrieve full detail of a supervisor (including relationships).

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor

        Returns:
            SupervisorDetail: Complete supervisor details with relationships

        Raises:
            ValidationException: If supervisor not found

        Example:
            >>> detail = service.get_supervisor(db, supervisor_id)
            >>> print(detail.employment_type, detail.assignments)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")

        try:
            logger.debug(f"Fetching supervisor details: {supervisor_id}")
            
            full = self.supervisor_repo.get_full_supervisor(db, supervisor_id)
            if not full:
                logger.warning(f"Supervisor not found: {supervisor_id}")
                raise ValidationException(
                    f"Supervisor not found with ID: {supervisor_id}"
                )
            
            return SupervisorDetail.model_validate(full)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch supervisor {supervisor_id}: {str(e)}")
            raise ValidationException(f"Failed to retrieve supervisor: {str(e)}")

    def get_supervisor_profile(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorProfile:
        """
        Retrieve full profile data for a supervisor.

        Includes employment history, permissions, performance summary, and preferences.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor

        Returns:
            SupervisorProfile: Complete profile with aggregated data

        Raises:
            ValidationException: If supervisor not found or profile cannot be built

        Example:
            >>> profile = service.get_supervisor_profile(db, supervisor_id)
            >>> print(profile.performance_summary, profile.permissions)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")

        try:
            logger.debug(f"Fetching supervisor profile: {supervisor_id}")
            
            profile_dict = self.aggregate_repo.get_supervisor_profile(db, supervisor_id)
            if not profile_dict:
                logger.warning(f"Supervisor profile not found: {supervisor_id}")
                raise ValidationException(
                    f"Supervisor profile not found with ID: {supervisor_id}"
                )
            
            return SupervisorProfile.model_validate(profile_dict)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch profile for {supervisor_id}: {str(e)}")
            raise ValidationException(f"Failed to retrieve supervisor profile: {str(e)}")

    def list_supervisors(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SupervisorListItem]:
        """
        List supervisors globally or filtered by hostel with pagination.

        Args:
            db: Database session
            hostel_id: Optional hostel ID to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List[SupervisorListItem]: List of supervisor summary items

        Raises:
            ValidationException: If parameters are invalid

        Example:
            >>> supervisors = service.list_supervisors(db, hostel_id=hostel_id, skip=0, limit=20)
            >>> for sup in supervisors:
            ...     print(sup.name, sup.employment_status)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if skip < 0:
            raise ValidationException("Skip parameter cannot be negative")
        
        if limit <= 0 or limit > 1000:
            raise ValidationException("Limit must be between 1 and 1000")

        try:
            logger.debug(
                f"Listing supervisors - hostel_id: {hostel_id}, skip: {skip}, limit: {limit}"
            )
            
            if hostel_id:
                objs = self.supervisor_repo.get_by_hostel(db, hostel_id, skip, limit)
                logger.debug(f"Found {len(objs)} supervisors for hostel: {hostel_id}")
            else:
                objs = self.supervisor_repo.get_list(db, skip, limit)
                logger.debug(f"Found {len(objs)} supervisors globally")

            return [SupervisorListItem.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(f"Failed to list supervisors: {str(e)}")
            raise ValidationException(f"Failed to list supervisors: {str(e)}")

    # -------------------------------------------------------------------------
    # Additional Utility Methods
    # -------------------------------------------------------------------------

    def supervisor_exists(self, db: Session, supervisor_id: UUID) -> bool:
        """
        Check if a supervisor exists in the system.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor

        Returns:
            bool: True if supervisor exists, False otherwise

        Example:
            >>> exists = service.supervisor_exists(db, supervisor_id)
        """
        if not db or not supervisor_id:
            return False
        
        try:
            supervisor = self.supervisor_repo.get_by_id(db, supervisor_id)
            return supervisor is not None
        except Exception:
            return False

    def get_supervisor_count(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> int:
        """
        Get total count of supervisors, optionally filtered by hostel.

        Args:
            db: Database session
            hostel_id: Optional hostel ID to filter by

        Returns:
            int: Total count of supervisors

        Example:
            >>> total = service.get_supervisor_count(db)
            >>> hostel_total = service.get_supervisor_count(db, hostel_id=hostel_id)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        try:
            if hostel_id:
                return self.supervisor_repo.count_by_hostel(db, hostel_id)
            return self.supervisor_repo.count_all(db)
        except Exception as e:
            logger.error(f"Failed to get supervisor count: {str(e)}")
            return 0