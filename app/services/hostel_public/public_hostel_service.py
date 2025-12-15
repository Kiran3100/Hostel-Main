# app/services/hostel_public/public_hostel_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, RoomRepository
from app.repositories.content import ReviewRepository
from app.schemas.hostel import (
    PublicHostelProfile,
    PublicRoomType,
)
from app.services.common import UnitOfWork, errors


class PublicHostelService:
    """
    Public hostel profile service:

    - Get detailed public hostel profile by slug
    - Assembles room-type view and rating aggregates
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_review_repo(self, uow: UnitOfWork) -> ReviewRepository:
        return uow.get_repo(ReviewRepository)

    # ------------------------------------------------------------------ #
    # Public profile
    # ------------------------------------------------------------------ #
    def get_public_profile(self, slug: str) -> PublicHostelProfile:
        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)
            review_repo = self._get_review_repo(uow)

            hostel = hostel_repo.get_by_slug(slug)
            if hostel is None or not hostel.is_public or not hostel.is_active:
                raise errors.NotFoundError(f"Public hostel {slug!r} not found")

            rooms = room_repo.list_for_hostel(
                hostel_id=hostel.id,
                only_available=False,
                room_type=None,
            )

            # Room-type aggregation
            room_type_map: Dict[str, Dict[str, object]] = {}
            for r in rooms:
                rt = r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type)
                entry = room_type_map.setdefault(
                    rt,
                    {
                        "price_monthly": r.price_monthly,
                        "price_quarterly": r.price_quarterly,
                        "price_yearly": r.price_yearly,
                        "available_beds": 0,
                        "total_beds": 0,
                        "amenities": set(),
                        "room_images": set(),
                    },
                )
                entry["total_beds"] = int(entry["total_beds"]) + (r.total_beds or 0)
                # available beds: simple approximation
                entry["available_beds"] = int(entry["available_beds"]) + (r.total_beds or 0)
                for a in (r.amenities or []):
                    entry["amenities"].add(a)
                for img in (r.room_images or []):
                    entry["room_images"].add(img)

            public_room_types: List[PublicRoomType] = []
            for rt, data in room_type_map.items():
                public_room_types.append(
                    PublicRoomType(
                        room_type=rt,
                        price_monthly=data["price_monthly"],
                        price_quarterly=data["price_quarterly"],
                        price_yearly=data["price_yearly"],
                        available_beds=data["available_beds"],
                        total_beds=data["total_beds"],
                        room_amenities=sorted(list(data["amenities"])),
                        room_images=sorted(list(data["room_images"])),
                    )
                )

            # Ratings aggregate
            agg = review_repo.get_aggregates_for_hostel(hostel.id)
            average_rating = Decimal(str(agg["average_rating"]))
            total_reviews = agg["total_reviews"]

            available_beds = max(
                0,
                (hostel.total_beds or 0) - (hostel.occupied_beds or 0),
            )

            return PublicHostelProfile(
                id=hostel.id,
                name=hostel.name,
                slug=hostel.slug,
                description=hostel.description,
                hostel_type=hostel.hostel_type,
                contact_phone=hostel.contact_phone,
                contact_email=hostel.contact_email,
                website_url=hostel.website_url,
                address_line1=hostel.address_line1,
                address_line2=hostel.address_line2,
                city=hostel.city,
                state=hostel.state,
                pincode=hostel.pincode,
                latitude=None,
                longitude=None,
                starting_price_monthly=hostel.starting_price_monthly or Decimal("0"),
                currency=hostel.currency or "INR",
                available_beds=available_beds,
                average_rating=average_rating,
                total_reviews=total_reviews,
                rating_breakdown={},  # detailed distribution not available from repo
                amenities=hostel.amenities or [],
                facilities=hostel.facilities or [],
                security_features=hostel.security_features or [],
                rules=hostel.rules,
                check_in_time=hostel.check_in_time,
                check_out_time=hostel.check_out_time,
                visitor_policy=hostel.visitor_policy,
                nearby_landmarks=hostel.nearby_landmarks or [],
                connectivity_info=hostel.connectivity_info,
                cover_image_url=hostel.cover_image_url,
                gallery_images=hostel.gallery_images or [],
                virtual_tour_url=hostel.virtual_tour_url,
                room_types=public_room_types,
            )