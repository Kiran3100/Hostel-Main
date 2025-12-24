"""
Search Indexing Service

Coordinates indexing operations for the search backend (SQL/ES/etc.).
"""

from __future__ import annotations

from typing import Iterable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.search import SearchIndexRepository
from app.core.logging import LoggingContext


class SearchIndexingService:
    """
    High-level service for indexing hostels/rooms into the search engine.

    Responsibilities:
    - Index single or multiple hostels
    - Remove hostels from index
    - Rebuild full index
    """

    def __init__(
        self,
        index_repo: SearchIndexRepository,
    ) -> None:
        self.index_repo = index_repo

    def index_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> None:
        """
        Index a single hostel by ID.
        """
        with LoggingContext(action="index_hostel", hostel_id=str(hostel_id)):
            self.index_repo.index_hostel(db, hostel_id)

    def index_multiple_hostels(
        self,
        db: Session,
        hostel_ids: Iterable[UUID],
        batch_size: int = 100,
    ) -> None:
        """
        Bulk index multiple hostels in batches.
        """
        ids: List[UUID] = list(hostel_ids)

        with LoggingContext(action="index_multiple_hostels", count=len(ids)):
            for i in range(0, len(ids), batch_size):
                batch = ids[i : i + batch_size]
                self.index_repo.index_hostels_batch(db, batch)

    def remove_hostel_from_index(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> None:
        """
        Remove a hostel from the index.
        """
        with LoggingContext(action="remove_hostel", hostel_id=str(hostel_id)):
            self.index_repo.remove_hostel(db, hostel_id)

    def rebuild_full_index(
        self,
        db: Session,
    ) -> None:
        """
        Trigger a full index rebuild.
        """
        with LoggingContext(action="rebuild_full_index"):
            self.index_repo.rebuild_index(db)