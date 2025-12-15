# app/services/search/search_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Callable, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorHostelRepository
from app.repositories.core import HostelRepository
from app.schemas.hostel.hostel_public import PublicHostelCard
from app.schemas.search.search_request import (
    AdvancedSearchRequest,
    BasicSearchRequest,
)
from app.schemas.search.search_response import (
    SearchResultItem,
    FacetBucket,
    FacetedSearchResponse,
)
from app.services.common import UnitOfWork


class SearchService:
    """
    Search service for hostels (public side), using:

    - AdvancedSearchRequest / BasicSearchRequest
    - FacetedSearchResponse, SearchResultItem

    It leverages VisitorHostel (denormalized search view) + core_hostel
    to provide reasonable search & facet behavior without a dedicated
    search engine.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_visitor_hostel_repo(self, uow: UnitOfWork) -> VisitorHostelRepository:
        return uow.get_repo(VisitorHostelRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def basic_search(self, req: BasicSearchRequest) -> FacetedSearchResponse:
        """
        Map BasicSearchRequest → AdvancedSearchRequest with only query filled.
        """
        adv = AdvancedSearchRequest(
            query=req.query,
            city=None,
            state=None,
            pincode=None,
            latitude=None,
            longitude=None,
            radius_km=None,
            hostel_type=None,
            room_type=None,
            min_price=None,
            max_price=None,
            amenities=None,
            min_rating=None,
            verified_only=False,
            available_only=False,
            sort_by="relevance",
            page=1,
            page_size=20,
        )
        return self.advanced_search(adv)

    def advanced_search(self, req: AdvancedSearchRequest) -> FacetedSearchResponse:
        """
        Execute an advanced hostel search and return faceted results.

        Implementation notes:
        - Uses VisitorHostelRepository.search for coarse filters (city/price/query).
        - Applies other filters (ratings, amenities, availability, etc.) in Python.
        - Computes simple facets (city, hostel_type, price, rating, amenities).
        """
        page = req.page
        page_size = req.page_size
        if page < 1:
            page = 1
        if page_size <= 0:
            page_size = 20

        start_time = datetime.utcnow()

        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_hostel_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            min_price = float(req.min_price) if req.min_price is not None else None
            max_price = float(req.max_price) if req.max_price is not None else None

            # "Rough" superset; adjust multiplier if needed
            rough_limit = page * page_size * 2

            vh_list = visitor_repo.search(
                city=req.city,
                area=None,
                min_price=min_price,
                max_price=max_price,
                gender_type=None,
                search=req.query,
                limit=rough_limit,
            )

            # Map hostel_id -> core_hostel
            hostel_cache: Dict[UUID, object] = {}
            for vh in vh_list:
                if vh.hostel_id not in hostel_cache:
                    hostel_cache[vh.hostel_id] = hostel_repo.get(vh.hostel_id)

            def _match(vh, h) -> bool:
                # State / pincode
                if req.state and (not h or h.state != req.state):
                    return False
                if req.pincode and getattr(vh, "pincode", None) != req.pincode:
                    return False

                # Room type
                if req.room_type and vh.room_types:
                    if req.room_type.value not in vh.room_types:
                        return False

                # Availability (available_only)
                if req.available_only:
                    if vh.availability is None or vh.availability <= 0:
                        return False

                # Min rating
                if req.min_rating is not None:
                    rating_val = Decimal(str(vh.rating or (h.average_rating if h else 0.0)))
                    if rating_val < req.min_rating:
                        return False

                # Amenities
                if req.amenities:
                    amenities_set = set(vh.amenities or [])
                    for a in req.amenities:
                        if a not in amenities_set:
                            return False

                # Verified_only requires core_hostel
                if req.verified_only and (not h or not h.is_verified):
                    return False

                # Hostel type
                if req.hostel_type and h and h.hostel_type != req.hostel_type:
                    return False

                # Radius_km / lat/long not implemented here; can be added if you store coords
                return True

            matched: List[tuple] = []
            for vh in vh_list:
                h = hostel_cache.get(vh.hostel_id)
                if _match(vh, h):
                    matched.append((vh, h))

            total_results = len(matched)

            # Sorting
            def _sort_key(item):
                vh, h = item
                if req.sort_by == "price_asc":
                    val = vh.min_price or (h.starting_price_monthly if h else Decimal("0"))
                    return (val,)
                if req.sort_by == "price_desc":
                    val = vh.max_price or (h.starting_price_monthly if h else Decimal("0"))
                    return (-val,)
                if req.sort_by == "rating_desc":
                    val = Decimal(str(vh.rating or (h.average_rating if h else 0.0)))
                    return (-val,)
                if req.sort_by == "newest":
                    created = getattr(h, "created_at", None)
                    return (created or datetime.min,)
                if req.sort_by == "distance_asc":
                    # Distance not implemented; treat as stable sort
                    return (0,)
                # "relevance": rely on original order
                return (0,)

            if req.sort_by != "relevance":
                matched.sort(key=_sort_key)

            # Pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_items = matched[start_idx:end_idx]

            # Map to SearchResultItem
            results: List[SearchResultItem] = []
            for vh, h in page_items:
                card = self._to_public_card(vh, h)
                # Simple score heuristic: rating + availability fraction
                rating_val = Decimal(str(vh.rating or (h.average_rating if h else 0.0)))
                avail = vh.availability or 0
                score = rating_val + Decimal(str(min(avail, 1)))
                results.append(
                    SearchResultItem(
                        hostel=card,
                        score=score,
                    )
                )

            total_pages = ceil(total_results / page_size) if page_size > 0 else 1

            facets = self._build_facets(matched, hostel_cache)
            raw_query: Dict[str, object] = {
                "request": req.model_dump(),
            }

        elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return FacetedSearchResponse(
            results=results,
            total_results=total_results,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            facets=facets,
            query_time_ms=elapsed_ms,
            raw_query=raw_query,
        )

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_public_card(self, vh, h) -> PublicHostelCard:
        starting_price = vh.min_price or (h.starting_price_monthly if h else Decimal("0"))
        available_beds = vh.availability
        if available_beds is None and h:
            total_beds = h.total_beds or 0
            occupied_beds = h.occupied_beds or 0
            available_beds = max(0, total_beds - occupied_beds)

        avg_rating = Decimal(str(vh.rating or (h.average_rating if h else 0.0)))
        total_reviews = vh.total_reviews or (h.total_reviews if h else 0) or 0

        return PublicHostelCard(
            id=vh.hostel_id,
            name=vh.hostel_name,
            slug=h.slug if h else "",
            hostel_type=h.hostel_type if h else None,  # type: ignore[arg-type]
            city=vh.city,
            state=h.state if h else "",
            starting_price_monthly=starting_price,
            currency="INR",
            average_rating=avg_rating,
            total_reviews=total_reviews,
            available_beds=available_beds or 0,
            cover_image_url=h.cover_image_url if h else None,
            is_featured=h.is_featured if h else False,
            amenities=(vh.amenities or [])[:5],
            distance_km=None,
        )

    # ------------------------------------------------------------------ #
    # Facets
    # ------------------------------------------------------------------ #
    def _build_facets(
        self,
        matched: List[tuple],
        hostel_cache: Dict[UUID, object],
    ) -> Dict[str, List[FacetBucket]]:
        """
        Build basic facets:
        - city
        - hostel_type
        - amenity
        - rating_bucket
        - price_range (single range across all matched)
        """
        city_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        amenity_counts: Dict[str, int] = {}
        rating_counts: Dict[str, int] = {}
        min_price: Optional[Decimal] = None
        max_price: Optional[Decimal] = None

        for vh, h in matched:
            # City
            city_counts[vh.city] = city_counts.get(vh.city, 0) + 1

            # Hostel type
            if h:
                type_val = (
                    h.hostel_type.value
                    if hasattr(h.hostel_type, "value")
                    else str(h.hostel_type)
                )
                type_counts[type_val] = type_counts.get(type_val, 0) + 1

            # Amenities
            for a in vh.amenities or []:
                amenity_counts[a] = amenity_counts.get(a, 0) + 1

            # Rating bucket
            rating_val = Decimal(str(vh.rating or (h.average_rating if h else 0.0)))
            if rating_val >= Decimal("4.5"):
                bucket = "4.5+"
            elif rating_val >= Decimal("4.0"):
                bucket = "4.0-4.4"
            elif rating_val >= Decimal("3.0"):
                bucket = "3.0-3.9"
            else:
                bucket = "<3.0"
            rating_counts[bucket] = rating_counts.get(bucket, 0) + 1

            # Price
            p = vh.min_price or (h.starting_price_monthly if h else None)
            if p is not None:
                if min_price is None or p < min_price:
                    min_price = p
                if max_price is None or p > max_price:
                    max_price = p

        facets: Dict[str, List[FacetBucket]] = {}

        facets["city"] = [
            FacetBucket(value=city, count=count, label=city)
            for city, count in sorted(city_counts.items(), key=lambda x: -x[1])
        ]

        facets["hostel_type"] = [
            FacetBucket(value=t, count=count, label=t)
            for t, count in sorted(type_counts.items(), key=lambda x: -x[1])
        ]

        facets["amenity"] = [
            FacetBucket(value=a, count=count, label=a)
            for a, count in sorted(amenity_counts.items(), key=lambda x: -x[1])
        ]

        facets["rating"] = [
            FacetBucket(value=bucket, count=count, label=bucket)
            for bucket, count in sorted(rating_counts.items(), key=lambda x: -x[1])
        ]

        if min_price is not None and max_price is not None:
            label = f"₹{min_price:,.0f} - ₹{max_price:,.0f}"
            facets["price_range"] = [
                FacetBucket(
                    value=label,
                    count=len(matched),
                    label=label,
                )
            ]

        return facets