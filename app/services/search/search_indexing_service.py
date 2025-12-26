"""
Search Indexing Service

Coordinates indexing operations for the search backend (SQL/ES/etc.).
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Set
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.search import SearchIndexRepository
from app.core.logging import LoggingContext, logger
from app.core.exceptions import ValidationException


class SearchIndexingService:
    """
    High-level service for indexing hostels/rooms into the search engine.

    Responsibilities:
    - Index single or multiple hostels
    - Remove hostels from index
    - Rebuild full index
    - Handle indexing errors gracefully
    - Track indexing progress and metrics
    """

    __slots__ = ('index_repo', 'default_batch_size', 'max_batch_size')

    def __init__(
        self,
        index_repo: SearchIndexRepository,
        default_batch_size: int = 100,
        max_batch_size: int = 1000,
    ) -> None:
        """
        Initialize SearchIndexingService.

        Args:
            index_repo: Repository for search indexing operations
            default_batch_size: Default batch size for bulk operations
            max_batch_size: Maximum allowed batch size
        """
        self.index_repo = index_repo
        self.default_batch_size = default_batch_size
        self.max_batch_size = max_batch_size

    def index_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> bool:
        """
        Index a single hostel by ID.

        Args:
            db: SQLAlchemy session
            hostel_id: UUID of the hostel to index

        Returns:
            True if indexing succeeded, False otherwise

        Raises:
            ValidationException: If hostel_id is invalid
        """
        self._validate_hostel_id(hostel_id)

        with LoggingContext(action="index_hostel", hostel_id=str(hostel_id)):
            try:
                self.index_repo.index_hostel(db, hostel_id)
                logger.info(f"Successfully indexed hostel: {hostel_id}")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to index hostel: {hostel_id}",
                    extra={"hostel_id": str(hostel_id), "error": str(e)}
                )
                return False

    def index_multiple_hostels(
        self,
        db: Session,
        hostel_ids: Iterable[UUID],
        batch_size: Optional[int] = None,
    ) -> dict:
        """
        Bulk index multiple hostels in batches.

        Args:
            db: SQLAlchemy session
            hostel_ids: Iterable of hostel UUIDs to index
            batch_size: Optional batch size (uses default if not specified)

        Returns:
            Dictionary with indexing results:
            - total: Total hostels to index
            - succeeded: Number of successfully indexed hostels
            - failed: Number of failed hostels
            - failed_ids: List of failed hostel IDs

        Raises:
            ValidationException: If batch_size is invalid
        """
        # Use default batch size if not specified
        if batch_size is None:
            batch_size = self.default_batch_size
        
        self._validate_batch_size(batch_size)

        # Convert to list and deduplicate
        ids: List[UUID] = list(set(hostel_ids))
        total_count = len(ids)

        if total_count == 0:
            logger.warning("No hostel IDs provided for indexing")
            return {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "failed_ids": [],
            }

        with LoggingContext(
            action="index_multiple_hostels",
            count=total_count,
            batch_size=batch_size,
        ):
            succeeded = 0
            failed = 0
            failed_ids: List[UUID] = []

            # Process in batches
            for i in range(0, total_count, batch_size):
                batch = ids[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                
                try:
                    self.index_repo.index_hostels_batch(db, batch)
                    succeeded += len(batch)
                    logger.info(
                        f"Indexed batch {batch_num}: {len(batch)} hostels",
                        extra={"batch_num": batch_num, "batch_size": len(batch)}
                    )
                except Exception as e:
                    failed += len(batch)
                    failed_ids.extend(batch)
                    logger.error(
                        f"Failed to index batch {batch_num}: {str(e)}",
                        extra={
                            "batch_num": batch_num,
                            "batch_size": len(batch),
                            "error": str(e),
                        }
                    )

            result = {
                "total": total_count,
                "succeeded": succeeded,
                "failed": failed,
                "failed_ids": [str(fid) for fid in failed_ids],
            }

            logger.info(
                f"Bulk indexing completed: {succeeded}/{total_count} succeeded",
                extra=result
            )

            return result

    def remove_hostel_from_index(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> bool:
        """
        Remove a hostel from the index.

        Args:
            db: SQLAlchemy session
            hostel_id: UUID of the hostel to remove

        Returns:
            True if removal succeeded, False otherwise

        Raises:
            ValidationException: If hostel_id is invalid
        """
        self._validate_hostel_id(hostel_id)

        with LoggingContext(action="remove_hostel", hostel_id=str(hostel_id)):
            try:
                self.index_repo.remove_hostel(db, hostel_id)
                logger.info(f"Successfully removed hostel from index: {hostel_id}")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to remove hostel from index: {hostel_id}",
                    extra={"hostel_id": str(hostel_id), "error": str(e)}
                )
                return False

    def remove_multiple_hostels(
        self,
        db: Session,
        hostel_ids: Iterable[UUID],
    ) -> dict:
        """
        Remove multiple hostels from the index.

        Args:
            db: SQLAlchemy session
            hostel_ids: Iterable of hostel UUIDs to remove

        Returns:
            Dictionary with removal results
        """
        ids: List[UUID] = list(set(hostel_ids))
        total_count = len(ids)

        if total_count == 0:
            return {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "failed_ids": [],
            }

        with LoggingContext(action="remove_multiple_hostels", count=total_count):
            succeeded = 0
            failed = 0
            failed_ids: List[UUID] = []

            for hostel_id in ids:
                try:
                    self.index_repo.remove_hostel(db, hostel_id)
                    succeeded += 1
                except Exception as e:
                    failed += 1
                    failed_ids.append(hostel_id)
                    logger.error(
                        f"Failed to remove hostel: {hostel_id}",
                        extra={"hostel_id": str(hostel_id), "error": str(e)}
                    )

            result = {
                "total": total_count,
                "succeeded": succeeded,
                "failed": failed,
                "failed_ids": [str(fid) for fid in failed_ids],
            }

            logger.info(
                f"Bulk removal completed: {succeeded}/{total_count} succeeded",
                extra=result
            )

            return result

    def rebuild_full_index(
        self,
        db: Session,
    ) -> bool:
        """
        Trigger a full index rebuild.

        Args:
            db: SQLAlchemy session

        Returns:
            True if rebuild succeeded, False otherwise
        """
        with LoggingContext(action="rebuild_full_index"):
            try:
                logger.info("Starting full index rebuild...")
                self.index_repo.rebuild_index(db)
                logger.info("Full index rebuild completed successfully")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to rebuild full index: {str(e)}",
                    extra={"error": str(e)}
                )
                return False

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_hostel_id(hostel_id: UUID) -> None:
        """
        Validate hostel ID.

        Args:
            hostel_id: UUID to validate

        Raises:
            ValidationException: If hostel_id is invalid
        """
        if hostel_id is None:
            raise ValidationException("Hostel ID cannot be None")

    def _validate_batch_size(self, batch_size: int) -> None:
        """
        Validate batch size.

        Args:
            batch_size: Batch size to validate

        Raises:
            ValidationException: If batch_size is invalid
        """
        if batch_size <= 0:
            raise ValidationException("Batch size must be positive")
        
        if batch_size > self.max_batch_size:
            raise ValidationException(
                f"Batch size cannot exceed {self.max_batch_size}"
            )