# app/services/hostel_public/hostel_search_service.py
from __future__ import annotations

from math import ceil
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorHostelRepository
from app.repositories.core import HostelRepository
from app.schemas.hostel import (
    HostelSearchRequest,
    HostelSearchResponse,
    HostelSearchFilters,
    PublicHostelCard,
)
from app.schemas.hostel.hostel_search import (
    SearchFacets,
    FacetItem,
    PriceRangeFacet,
    RatingFacet,
)
from app.services.common import UnitOfWork


class HostelSearchService:
    """
    Public hostel search:

    - Search hostels using VisitorHostel denormalized view + core_hostel
    - Apply filters/pagination
    - Build facets (cities, hostel types, basic price/rating buckets)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_visitor_hostel_repo(self, uow: UnitOfWork) -> VisitorHostelRepository:
        return uow.get_repo(VisitorHostelRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_public_card_from_pair(self, vh, h) -> PublicHostelCard:
        """
        vh: VisitorHostel row
        h:  core_hostel row (may be None)
        """
        starting_price = vh.min_price or h.starting_price_monthly or Decimal("0")
        avg_rating = Decimal(str(vh.rating or h.average_rating or 0.0))
        total_reviews = vh.total_reviews or h.total_reviews or 0
        available_beds = vh.availability or max(
            0,
            (h.total_beds or 0) - (h.occupied_beds or 0),
        )

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
            available_beds=available_beds,
            cover_image_url=h.cover_image_url if h else None,
            is_featured=h.is_featured if h else False,
            amenities=(vh.amenities or [])[:5],
            distance_km=None,
        )

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def search(self, req: HostelSearchRequest) -> HostelSearchResponse:
        """
        Execute a hostel search and return paginated results + facets.

        This uses VisitorHostelRepository.search for coarse filtering, then
        refines results in Python for other filters.
        """
        page = req.page
        page_size = req.page_size
        if page < 1 or page_size <= 0:
            page = 1
            page_size = 20

        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_hostel_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            # Map request filters into VisitorHostel.search where possible
            min_price = float(req.min_price) if req.min_price is not None else None
            max_price = float(req.max_price) if req.max_price is not None else None

            # Fetch a superset; VisitorHostelRepository.search has only limit (no offset)
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

            # Map hostel_id -> core_hostel (for slug, type, etc.)
            hostel_cache: Dict[UUID, object] = {}
            for vh in vh_list:
                if vh.hostel_id not in hostel_cache:
                    h = hostel_repo.get(vh.hostel_id)
                    hostel_cache[vh.hostel_id] = h

            # Apply remaining filters in Python
            def _match(vh, h) -> bool:
                # State
                if req.state and (not h or h.state != req.state):
                    return False
                # Pincode
                if req.pincode and getattr(vh, "pincode", None) != req.pincode:
                    return False
                # Room type
                if req.room_type and vh.room_types:
                    if req.room_type.value not in vh.room_types:
                        return False
                # Availability
                if req.available_beds_min is not None:
                    if vh.availability is None or vh.availability < req.available_beds_min:
                        return False
                # Rating
                if req.min_rating is not None:
                    rating_value = Decimal(str(vh.rating or h.average_rating or 0.0))
                    if rating_value < req.min_rating:
                        return False
                # Amenities
                if req.amenities:
                    amenities_set = set(vh.amenities or [])
                    for a in req.amenities:
                        if a not in amenities_set:
                            return False
                # Verified/featured only: requires core_hostel
                if req.verified_only and (not h or not h.is_verified):
                    return False
                if req.featured_only and (not h or not h.is_featured):
                    return False
                # Hostel type
                if req.hostel_type and h and h.hostel_type != req.hostel_type:
                    return False
                return True

            filtered: List[tuple] = []
            for vh in vh_list:
                h = hostel_cache.get(vh.hostel_id)
                if _match(vh, h):
                    filtered.append((vh, h))

            total_results = len(filtered)

            # Sorting
            def _sort_key(item):
                vh, h = item
                if req.sort_by == "price_low":
                    val = vh.min_price or h.starting_price_monthly or Decimal("0")
                    return (val, )
                if req.sort_by == "price_high":
                    val = vh.max_price or h.starting_price_monthly or Decimal("0")
                    return (-val, )
                if req.sort_by == "rating":
                    val = Decimal(str(vh.rating or h.average_rating or 0.0))
                    return (-val, )
                if req.sort_by == "newest":
                    # use hostel.created_at
                    created = getattr(h, "created_at", None)
                    return (created or datetime.min, )
                # relevance / distance not implemented; keep original order
                return (0, )

            if req.sort_by != "relevance":
                filtered.sort(key=_sort_key)

            # Pagination slice
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_items = filtered[start_idx:end_idx]

            results: List[PublicHostelCard] = [
                self._to_public_card_from_pair(vh, h) for vh, h in page_items
            ]

            total_pages = ceil(total_results / page_size) if page_size > 0 else 1

            # Facets
            facets = self._build_facets(filtered, hostel_cache)

            # Filters summary
            filters_applied: Dict[str, object] = {}
            for fname in [
                "city",
                "state",
                "pincode",
                "hostel_type",
                "min_price",
                "max_price",
                "room_type",
                "amenities",
                "available_beds_min",
                "min_rating",
                "verified_only",
                "featured_only",
            ]:
                val = getattr(req, fname, None)
                if val not in (None, [], {}):
                    filters_applied[fname] = val

        return HostelSearchResponse(
            results=results,
            total_results=total_results,
            total_pages=total_pages,
            current_page=page,
            filters_applied=filters_applied,
            facets=facets,
        )

    # ------------------------------------------------------------------ #
    # Facets
    # ------------------------------------------------------------------ #
    def _build_facets(
        self,
        filtered: List[tuple],
        hostel_cache: Dict[UUID, object],
    ) -> SearchFacets:
        # Cities
        city_counts: Dict[str, int] = {}
        # Hostel types
        type_counts: Dict[str, int] = {}
        # Amenities
        amenity_counts: Dict[str, int] = {}
        # Ratings
        rating_buckets: Dict[str, int] = {}
        # Price range
        min_price: Optional[Decimal] = None
        max_price: Optional[Decimal] = None

        for vh, h in filtered:
            city_counts[vh.city] = city_counts.get(vh.city, 0) + 1
            if h:
                t_val = h.hostel_type.value if hasattr(h.hostel_type, "value") else str(h.hostel_type)
                type_counts[t_val] = type_counts.get(t_val, 0) + 1

            # amenities
            for a in vh.amenities or []:
                amenity_counts[a] = amenity_counts.get(a, 0) + 1

            # rating bucket
            rating_val = Decimal(str(vh.rating or (h.average_rating if h else 0.0)))
            if rating_val >= Decimal("4.5"):
                bucket = "4.5+"
            elif rating_val >= Decimal("4.0"):
                bucket = "4.0-4.4"
            elif rating_val >= Decimal("3.0"):
                bucket = "3.0-3.9"
            else:
                bucket = "<3.0"
            rating_buckets[bucket] = rating_buckets.get(bucket, 0) + 1

            # price range from min_price field if available
            p_min = vh.min_price or (h.starting_price_monthly if h else None)
            if p_min is not None:
                if min_price is None or p_min < min_price:
                    min_price = p_min
                if max_price is None or p_min > max_price:
                    max_price = p_min

        cities_facet = [
            FacetItem(value=city, label=city, count=count)
            for city, count in sorted(city_counts.items(), key=lambda x: -x[1])
        ]
        hostel_types_facet = [
            FacetItem(value=v, label=v, count=c)
            for v, c in sorted(type_counts.items(), key=lambda x: -x[1])
        ]
        amenities_facet = [
            FacetItem(value=v, label=v, count=c)
            for v, c in sorted(amenity_counts.items(), key=lambda x: -x[1])
        ]
        ratings_facet = [
            RatingFacet(
                min_rating=Decimal("4.5") if bucket == "4.5+" else (
                    Decimal("4.0") if bucket == "4.0-4.4" else (
                        Decimal("3.0") if bucket == "3.0-3.9" else Decimal("0")
                    )
                ),
                label=bucket,
                count=count,
            )
            for bucket, count in sorted(rating_buckets.items(), key=lambda x: -x[1])
        ]

        price_ranges_facet: List[PriceRangeFacet] = []
        if min_price is not None and max_price is not None:
            price_ranges_facet.append(
                PriceRangeFacet(
                    min_price=min_price,
                    max_price=max_price,
                    label=f"₹{min_price:,.0f} - ₹{max_price:,.0f}",
                    count=len(filtered),
                )
            )

        return SearchFacets(
            cities=cities_facet,
            hostel_types=hostel_types_facet,
            price_ranges=price_ranges_facet,
            amenities=amenities_facet,
            ratings=ratings_facet,
        )