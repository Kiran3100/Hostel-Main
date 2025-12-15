# app/services/search/search_indexer_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository
from app.repositories.visitor import VisitorHostelRepository
from app.schemas.common.enums import HostelStatus
from app.services.common import UnitOfWork, errors


class SearchIndexBackend(Protocol):
    """
    Abstract search index backend.

    Implementations should wrap your actual search engine client
    (Elasticsearch, Meilisearch, OpenSearch, etc.).
    """

    def index_document(
        self,
        *,
        index: str,
        document_id: str,
        body: Dict,
    ) -> None: ...
    """
    Index (create or update) a document in the given index.
    """

    def delete_document(
        self,
        *,
        index: str,
        document_id: str,
    ) -> None: ...
    """
    Delete a document from the given index (no-op if not found).
    """

    def bulk_index(
        self,
        *,
        index: str,
        documents: List[Dict],
    ) -> None: ...
    """
    Bulk index documents.

    Each document dict is expected to include an 'id' key used as document_id.
    """


class SearchIndexerService:
    """
    Service responsible for (re)indexing hostels into a search backend.

    - Build a unified search document combining VisitorHostel + core Hostel
    - Index a single hostel
    - Bulk reindex all public/active hostels
    - Remove hostel from index

    This is optional infrastructure: your current SearchService works directly
    on the DB. Use this when you introduce a dedicated search engine.
    """

    INDEX_NAME = "hostels"

    def __init__(
        self,
        session_factory: Callable[[], Session],
        backend: SearchIndexBackend,
    ) -> None:
        self._session_factory = session_factory
        self._backend = backend

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_visitor_hostel_repo(self, uow: UnitOfWork) -> VisitorHostelRepository:
        return uow.get_repo(VisitorHostelRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Document builder
    # ------------------------------------------------------------------ #
    def _build_hostel_document(
        self,
        *,
        hostel,
        visitor_hostel: Optional[object],
    ) -> Dict:
        """
        Build a single search document from core_hostel + visitor_hostel.

        The resulting dict is what gets sent to the search engine.
        """
        # Base from core_hostel
        doc: Dict[str, object] = {
            "id": str(hostel.id),
            "hostel_id": str(hostel.id),
            "slug": hostel.slug,
            "name": hostel.name,
            "description": hostel.description or "",
            "hostel_type": hostel.hostel_type.value
            if hasattr(hostel.hostel_type, "value")
            else str(hostel.hostel_type),
            # Location
            "address_line1": hostel.address_line1,
            "address_line2": hostel.address_line2 or "",
            "city": hostel.city,
            "state": hostel.state,
            "pincode": hostel.pincode,
            "country": hostel.country,
            # Pricing
            "starting_price_monthly": float(hostel.starting_price_monthly or 0),
            "currency": hostel.currency or "INR",
            # Capacity
            "total_rooms": hostel.total_rooms or 0,
            "total_beds": hostel.total_beds or 0,
            "occupied_beds": hostel.occupied_beds or 0,
            "available_beds": max(
                0,
                (hostel.total_beds or 0) - (hostel.occupied_beds or 0),
            ),
            # Features
            "amenities": hostel.amenities or [],
            "facilities": hostel.facilities or [],
            "security_features": hostel.security_features or [],
            # Ratings
            "average_rating": float(hostel.average_rating or 0.0),
            "total_reviews": hostel.total_reviews or 0,
            # Status flags
            "is_public": hostel.is_public,
            "is_featured": hostel.is_featured,
            "is_verified": hostel.is_verified,
            "is_active": hostel.is_active,
            "status": hostel.status.value
            if hasattr(hostel.status, "value")
            else str(hostel.status),
            # Media
            "cover_image_url": hostel.cover_image_url or "",
            "gallery_images": hostel.gallery_images or [],
            "virtual_tour_url": hostel.virtual_tour_url or "",
            # Timestamps
            "created_at": hostel.created_at.isoformat()
            if getattr(hostel, "created_at", None)
            else None,
            "updated_at": hostel.updated_at.isoformat()
            if getattr(hostel, "updated_at", None)
            else None,
        }

        # Enrich from VisitorHostel if available
        if visitor_hostel is not None:
            vh = visitor_hostel
            # Price range / rating from visitor table may be more tailored
            if getattr(vh, "min_price", None) is not None:
                doc["starting_price_monthly"] = float(vh.min_price)
            doc["min_price"] = float(vh.min_price or 0)
            doc["max_price"] = float(vh.max_price or 0)
            doc["price_range"] = vh.price_range or ""
            doc["gender_type"] = vh.gender_type or ""
            doc["availability"] = vh.availability or 0
            doc["total_capacity"] = vh.total_capacity or 0
            doc["rating"] = float(vh.rating or hostel.average_rating or 0.0)
            doc["total_reviews"] = vh.total_reviews or hostel.total_reviews or 0
            doc["visitor_amenities"] = vh.amenities or []
            doc["photos"] = vh.photos or []
            doc["availability_status"] = vh.availability_status or ""
            doc["location"] = vh.location or ""
            doc["area"] = vh.area or ""
            doc["visitor_contact_number"] = vh.contact_number or ""
            doc["visitor_contact_email"] = vh.contact_email or ""

        return doc

    # ------------------------------------------------------------------ #
    # Single hostel indexing
    # ------------------------------------------------------------------ #
    def index_hostel(self, hostel_id: UUID) -> Dict:
        """
        Fetch a single hostel + visitor_hostel view and index it.

        Returns the document body that was indexed.
        """
        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            visitor_repo = self._get_visitor_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            # Only index public/active hostels
            if not hostel.is_public or not hostel.is_active or hostel.status != HostelStatus.ACTIVE:
                # If it's in index, we should remove it instead
                self.remove_hostel_from_index(hostel_id)
                raise errors.ValidationError(
                    "Only active & public hostels can be indexed"
                )

            vh = visitor_repo.get_by_id(hostel_id) if hasattr(visitor_repo, "get_by_id") else None

            doc = self._build_hostel_document(hostel=hostel, visitor_hostel=vh)

        self._backend.index_document(
            index=self.INDEX_NAME,
            document_id=str(hostel_id),
            body=doc,
        )
        return doc

    # ------------------------------------------------------------------ #
    # Bulk reindex
    # ------------------------------------------------------------------ #
    def reindex_all_hostels(self, batch_size: int = 200) -> int:
        """
        Bulk reindex all public & active hostels into the search index.

        Returns the total number of hostels indexed.
        """
        total_indexed = 0

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            visitor_repo = self._get_visitor_hostel_repo(uow)

            # Fetch all hostels that are public & active & HOSTEL_STATUS = ACTIVE
            filters = {
                "is_public": True,
                "is_active": True,
                "status": HostelStatus.ACTIVE,
            }
            all_hostels = hostel_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters,
            )

            # Index in batches
            batch_docs: List[Dict] = []
            for hostel in all_hostels:
                vh = None
                # Use visitor_hostel row if you have a get_by_hostel_id helper;
                # otherwise you can search via get_multi
                if hasattr(visitor_repo, "get_by_hostel_id"):
                    vh = visitor_repo.get_by_hostel_id(hostel.id)
                else:
                    cand = visitor_repo.get_multi(
                        skip=0,
                        limit=1,
                        filters={"hostel_id": hostel.id},
                    )
                    vh = cand[0] if cand else None

                doc = self._build_hostel_document(
                    hostel=hostel,
                    visitor_hostel=vh,
                )
                batch_docs.append(doc)

                if len(batch_docs) >= batch_size:
                    self._backend.bulk_index(
                        index=self.INDEX_NAME,
                        documents=batch_docs,
                    )
                    total_indexed += len(batch_docs)
                    batch_docs = []

            if batch_docs:
                self._backend.bulk_index(
                    index=self.INDEX_NAME,
                    documents=batch_docs,
                )
                total_indexed += len(batch_docs)

        return total_indexed

    # ------------------------------------------------------------------ #
    # Deletion
    # ------------------------------------------------------------------ #
    def remove_hostel_from_index(self, hostel_id: UUID) -> None:
        """
        Remove a hostel document from the search index.
        """
        self._backend.delete_document(
            index=self.INDEX_NAME,
            document_id=str(hostel_id),
        )