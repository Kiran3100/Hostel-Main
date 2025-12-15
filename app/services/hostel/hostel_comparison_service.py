# app/services/hostel/hostel_comparison_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, RoomRepository
from app.repositories.transactions import FeeStructureRepository
from app.schemas.hostel import (
    HostelComparisonRequest,
    ComparisonResult,
    ComparisonItem,
)
from app.schemas.hostel.hostel_comparison import (
    RoomTypeComparison,
)
from app.services.common import UnitOfWork, errors


class HostelComparisonService:
    """
    Compare multiple hostels for admin/visitor UIs.

    Focuses on:
    - Capacity and pricing
    - Rating & reviews
    - Amenities/facilities/security
    - Available room types
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_fee_repo(self, uow: UnitOfWork) -> FeeStructureRepository:
        return uow.get_repo(FeeStructureRepository)

    # ------------------------------------------------------------------ #
    # Main API
    # ------------------------------------------------------------------ #
    def compare_hostels(self, req: HostelComparisonRequest) -> ComparisonResult:
        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)
            fee_repo = self._get_fee_repo(uow)

            hostels = []
            for hid in req.hostel_ids:
                h = hostel_repo.get(hid)
                if h is None:
                    raise errors.NotFoundError(f"Hostel {hid} not found")
                hostels.append(h)

            # Preload rooms & fees
            rooms_by_hostel: Dict[UUID, List] = {}
            fees_by_hostel: Dict[UUID, List] = {}
            for h in hostels:
                rooms_by_hostel[h.id] = room_repo.list_for_hostel(
                    hostel_id=h.id,
                    only_available=False,
                    room_type=None,
                )
                fees_by_hostel[h.id] = fee_repo.get_multi(
                    skip=0,
                    limit=None,  # type: ignore[arg-type]
                    filters={"hostel_id": h.id, "is_active": True},
                )

            comparison_items: List[ComparisonItem] = []

            for h in hostels:
                rooms = rooms_by_hostel[h.id]
                fees = fees_by_hostel[h.id]

                # Pricing
                if fees:
                    amounts = [fs.amount for fs in fees if fs.amount is not None]
                    if amounts:
                        min_price = min(amounts)
                        max_price = max(amounts)
                    else:
                        min_price = max_price = h.starting_price_monthly or Decimal("0")
                else:
                    min_price = max_price = h.starting_price_monthly or Decimal("0")

                price_range_str = f"₹{min_price:,.0f} - ₹{max_price:,.0f}"

                sec_deposits = [
                    fs.security_deposit for fs in fees if fs.security_deposit is not None
                ]
                security_deposit = min(sec_deposits) if sec_deposits else None

                # Room type details
                room_type_map: Dict[str, RoomTypeComparison] = {}
                for r in rooms:
                    rt = r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type)
                    existing = room_type_map.get(rt)
                    total_beds = r.total_beds or 0
                    available_beds = total_beds  # more detailed computation could use Student assignments

                    if existing:
                        existing.total_beds += total_beds
                        existing.available_beds += available_beds
                    else:
                        room_type_map[rt] = RoomTypeComparison(
                            room_type=rt,
                            price_monthly=r.price_monthly,
                            available_beds=available_beds,
                            total_beds=total_beds,
                            amenities=r.amenities or [],
                        )

                room_types_available = list(room_type_map.keys())
                room_type_details = list(room_type_map.values())

                # Ratings
                avg_rating = Decimal(str(h.average_rating or 0.0))
                total_reviews = h.total_reviews or 0

                # Rating breakdown not readily available; keep empty
                rating_breakdown: Dict[str, int] = {}

                # Capacity
                total_beds = h.total_beds or 0
                available_beds = max(0, total_beds - (h.occupied_beds or 0))

                comparison_items.append(
                    ComparisonItem(
                        id=h.id,
                        name=h.name,
                        slug=h.slug,
                        hostel_type=h.hostel_type,
                        city=h.city,
                        state=h.state,
                        address=h.address_line1,
                        distance_from_center_km=None,
                        starting_price_monthly=min_price,
                        price_range_monthly=price_range_str,
                        security_deposit=security_deposit,
                        total_beds=total_beds,
                        available_beds=available_beds,
                        average_rating=avg_rating,
                        total_reviews=total_reviews,
                        rating_breakdown=rating_breakdown,
                        amenities=h.amenities or [],
                        facilities=h.facilities or [],
                        security_features=h.security_features or [],
                        room_types_available=room_types_available,
                        room_type_details=room_type_details,
                        check_in_time=h.check_in_time.isoformat() if h.check_in_time else None,
                        check_out_time=h.check_out_time.isoformat() if h.check_out_time else None,
                        visitor_allowed=True if h.visitor_policy else False,
                        cover_image_url=h.cover_image_url,
                        total_images=len(h.gallery_images or []),
                        has_virtual_tour=bool(h.virtual_tour_url),
                        unique_features=[],
                        pros=[],
                        cons=[],
                    )
                )

        comparison_criteria = [
            "price",
            "rating",
            "availability",
            "amenities",
            "location",
        ]

        return ComparisonResult(
            hostels=comparison_items,
            comparison_criteria=comparison_criteria,
            generated_at=datetime.utcnow(),
        )