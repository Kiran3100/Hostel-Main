# app/services/review/review_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import ReviewRepository
from app.repositories.core import HostelRepository, UserRepository, StudentRepository
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.review import (
    ReviewCreate,
    ReviewUpdate,
    ReviewResponse,
    ReviewDetail,
    ReviewListItem,
)

from app.schemas.review.review_filters import (
    ReviewFilterParams,
    ReviewSearchRequest,
    ReviewSortOptions,
)
from app.schemas.review.review_response import ReviewSummary
from app.services.common import UnitOfWork, errors


class ReviewService:
    """
    Core internal review service (content_review):

    - Create/update reviews
    - Get review detail
    - List & search reviews with filters + sorting
    - Summary per hostel
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_review_repo(self, uow: UnitOfWork) -> ReviewRepository:
        return uow.get_repo(ReviewRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        r,
        *,
        hostel_name: str,
        reviewer_name: str,
    ) -> ReviewResponse:
        return ReviewResponse(
            id=r.id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            hostel_id=r.hostel_id,
            hostel_name=hostel_name,
            reviewer_id=r.reviewer_id,
            reviewer_name=reviewer_name,
            overall_rating=r.overall_rating,
            title=r.title,
            review_text=r.review_text,
            is_verified_stay=r.is_verified_stay,
            verified_at=r.verified_at,
            is_approved=r.is_approved,
            helpful_count=r.helpful_count,
            not_helpful_count=r.not_helpful_count,
        )

    def _to_detail(
        self,
        r,
        *,
        hostel_name: str,
        reviewer_name: str,
        reviewer_profile_image: Optional[str],
        student_name: Optional[str],
    ) -> ReviewDetail:
        # Model does not hold moderation metadata / hostel response;
        # we return safe defaults here.
        is_published = bool(r.is_approved and not r.is_flagged)

        return ReviewDetail(
            id=r.id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            hostel_id=r.hostel_id,
            hostel_name=hostel_name,
            reviewer_id=r.reviewer_id,
            reviewer_name=reviewer_name,
            reviewer_profile_image=reviewer_profile_image,
            student_id=r.student_id,
            booking_id=r.booking_id,
            overall_rating=r.overall_rating,
            cleanliness_rating=r.cleanliness_rating,
            food_quality_rating=r.food_quality_rating,
            staff_behavior_rating=r.staff_behavior_rating,
            security_rating=r.security_rating,
            value_for_money_rating=r.value_for_money_rating,
            amenities_rating=r.amenities_rating,
            title=r.title,
            review_text=r.review_text,
            photos=r.photos or [],
            is_verified_stay=r.is_verified_stay,
            verified_at=r.verified_at,
            is_approved=r.is_approved,
            approved_by=None,
            approved_at=None,
            is_flagged=r.is_flagged,
            flag_reason=None,
            flagged_by=None,
            flagged_at=None,
            helpful_count=r.helpful_count,
            not_helpful_count=r.not_helpful_count,
            report_count=0,
            hostel_response=None,
            is_published=is_published,
        )

    def _to_list_item(
        self,
        r,
        *,
        reviewer_name: str,
    ) -> ReviewListItem:
        excerpt = (r.review_text or "")[:150]
        photos = getattr(r, "photos", None) or []
        return ReviewListItem(
            id=r.id,
            reviewer_name=reviewer_name,
            reviewer_image=None,  # or derive from user if you want
            overall_rating=r.overall_rating,
            title=r.title,
            review_excerpt=excerpt,
            is_verified_stay=r.is_verified_stay,
            helpful_count=r.helpful_count,
            has_photos=bool(photos),
            photo_count=len(photos),
            created_at=r.created_at,
            has_hostel_response=False,
        )

    # ------------------------------------------------------------------ #
    # Core read
    # ------------------------------------------------------------------ #
    def get_review(self, review_id: UUID) -> ReviewDetail:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            r = review_repo.get(review_id)
            if r is None:
                raise errors.NotFoundError(f"Review {review_id} not found")

            hostel = hostel_repo.get(r.hostel_id)
            hostel_name = hostel.name if hostel else ""

            reviewer = user_repo.get(r.reviewer_id)
            reviewer_name = reviewer.full_name if reviewer else ""
            reviewer_img = getattr(reviewer, "profile_image_url", None) if reviewer else None

            student_name = None
            if r.student_id:
                st = self._get_student_repo(uow).get(r.student_id)
                if st and getattr(st, "user", None):
                    student_name = st.user.full_name

            return self._to_detail(
                r,
                hostel_name=hostel_name,
                reviewer_name=reviewer_name,
                reviewer_profile_image=reviewer_img,
                student_name=student_name,
            )

    # ------------------------------------------------------------------ #
    # Create / update
    # ------------------------------------------------------------------ #
    def create_review(self, data: ReviewCreate) -> ReviewDetail:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            reviewer = user_repo.get(data.reviewer_id)
            if reviewer is None:
                raise errors.NotFoundError(f"User {data.reviewer_id} not found")

            payload = data.model_dump(exclude_unset=True)
            r = review_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            student_name = None
            if r.student_id:
                st = self._get_student_repo(uow).get(r.student_id)
                if st and getattr(st, "user", None):
                    student_name = st.user.full_name

            return self._to_detail(
                r,
                hostel_name=hostel.name,
                reviewer_name=reviewer.full_name,
                reviewer_profile_image=getattr(reviewer, "profile_image_url", None),
                student_name=student_name,
            )

    def update_review(self, review_id: UUID, data: ReviewUpdate) -> ReviewDetail:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)

            r = review_repo.get(review_id)
            if r is None:
                raise errors.NotFoundError(f"Review {review_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(r, field) and field != "id":
                    setattr(r, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self.get_review(review_id)

    # ------------------------------------------------------------------ #
    # Listing with filters/sorting
    # ------------------------------------------------------------------ #
    def list_reviews(
        self,
        params: PaginationParams,
        filters: Optional[ReviewFilterParams] = None,
        sort: Optional[SortOptions] = None,
    ) -> PaginatedResponse[ReviewListItem]:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            user_repo = self._get_user_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                elif filters.hostel_ids:
                    raw_filters["hostel_id"] = filters.hostel_ids
                if filters.approved_only:
                    raw_filters["is_approved"] = True

            records: Sequence = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
            )

            def _matches(r) -> bool:
                if not filters:
                    return True

                if filters.min_rating is not None and r.overall_rating < filters.min_rating:
                    return False
                if filters.max_rating is not None and r.overall_rating > filters.max_rating:
                    return False
                if filters.rating is not None and int(round(float(r.overall_rating))) != filters.rating:
                    return False

                if filters.verified_only and not r.is_verified_stay:
                    return False

                if filters.posted_date_from or filters.posted_date_to:
                    d = r.created_at.date()
                    if filters.posted_date_from and d < filters.posted_date_from:
                        return False
                    if filters.posted_date_to and d > filters.posted_date_to:
                        return False

                if filters.flagged_only is True and not r.is_flagged:
                    return False

                if filters.min_helpful_count is not None and r.helpful_count < filters.min_helpful_count:
                    return False

                if filters.with_photos_only and not r.photos:
                    return False

                return True

            filtered = [r for r in records if _matches(r)]

            # Sorting
            sort = sort or SortOptions()
            def _sort_key(r):
                base = []
                if sort.sort_by == "helpful":
                    base.append(-r.helpful_count)
                elif sort.sort_by == "recent":
                    base.append(-(r.created_at.timestamp()))
                elif sort.sort_by == "rating_high":
                    base.append(-float(r.overall_rating))
                elif sort.sort_by == "rating_low":
                    base.append(float(r.overall_rating))
                elif sort.sort_by == "verified":
                    base.append(0 if r.is_verified_stay else 1)

                # Secondary modifiers
                if sort.verified_first:
                    base.append(0 if r.is_verified_stay else 1)
                if sort.with_photos_first:
                    base.append(0 if r.photos else 1)

                # Always add created_at desc as tie breaker
                base.append(-r.created_at.timestamp())
                return tuple(base)

            sorted_records = sorted(filtered, key=_sort_key)

            # Pagination
            start = params.offset
            end = start + params.limit
            page_records = sorted_records[start:end]

            # Map to list items
            user_cache: Dict[UUID, str] = {}
            items: List[ReviewListItem] = []
            for r in page_records:
                if r.reviewer_id not in user_cache:
                    u = user_repo.get(r.reviewer_id)
                    user_cache[r.reviewer_id] = u.full_name if u else ""
                reviewer_name = user_cache[r.reviewer_id]
                items.append(self._to_list_item(r, reviewer_name=reviewer_name))

            return PaginatedResponse[ReviewListItem].create(
                items=items,
                total_items=len(sorted_records),
                page=params.page,
                page_size=params.page_size,
            )

    def search_reviews(
        self,
        params: PaginationParams,
        req: ReviewSearchRequest,
    ) -> PaginatedResponse[ReviewListItem]:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            user_repo = self._get_user_repo(uow)

            filters: Dict[str, object] = {}
            if req.hostel_id:
                filters["hostel_id"] = req.hostel_id

            records: Sequence = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            q = req.query.lower()
            user_cache: Dict[UUID, str] = {}

            def _matches(r) -> bool:
                if req.min_rating is not None and r.overall_rating < req.min_rating:
                    return False

                if r.reviewer_id not in user_cache:
                    u = user_repo.get(r.reviewer_id)
                    user_cache[r.reviewer_id] = u.full_name if u else ""
                reviewer_name = user_cache[r.reviewer_id]

                text_parts: List[str] = []
                if req.search_in_title:
                    text_parts.append(r.title or "")
                if req.search_in_content:
                    text_parts.append(r.review_text or "")
                text_parts.append(reviewer_name)

                haystack = " ".join(text_parts).lower()
                return q in haystack

            matched = [r for r in records if _matches(r)]

            matched_sorted = sorted(matched, key=lambda r: r.created_at, reverse=True)
            start = params.offset
            end = start + params.limit
            page_records = matched_sorted[start:end]

            items: List[ReviewListItem] = []
            for r in page_records:
                reviewer_name = user_cache[r.reviewer_id]
                items.append(self._to_list_item(r, reviewer_name=reviewer_name))

            return PaginatedResponse[ReviewListItem].create(
                items=items,
                total_items=len(matched_sorted),
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    def get_summary_for_hostel(self, hostel_id: UUID) -> ReviewSummary:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            reviews = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

            total_reviews = len(reviews)
            if total_reviews == 0:
                return ReviewSummary(
                    hostel_id=hostel_id,
                    hostel_name=hostel.name,
                    total_reviews=0,
                    average_rating=Decimal("0"),
                    rating_5_count=0,
                    rating_4_count=0,
                    rating_3_count=0,
                    rating_2_count=0,
                    rating_1_count=0,
                    verified_reviews_count=0,
                    verified_reviews_percentage=Decimal("0"),
                    recent_reviews=[],
                    would_recommend_percentage=Decimal("0"),
                )

            rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            total_rating = Decimal("0")
            verified_count = 0

            for r in reviews:
                val = int(round(float(r.overall_rating)))
                val = min(5, max(1, val))
                rating_counts[val] += 1
                total_rating += r.overall_rating
                if r.is_verified_stay:
                    verified_count += 1

            avg_rating = total_rating / Decimal(str(total_reviews))

            verified_pct = (
                Decimal(str(verified_count)) / Decimal(str(total_reviews)) * Decimal("100")
            )

            # Recent reviews (up to 5)
            user_cache: Dict[UUID, str] = {}
            sorted_reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)
            recent_items: List[ReviewListItem] = []
            for r in sorted_reviews[:5]:
                if r.reviewer_id not in user_cache:
                    u = user_repo.get(r.reviewer_id)
                    user_cache[r.reviewer_id] = u.full_name if u else ""
                reviewer_name = user_cache[r.reviewer_id]
                recent_items.append(self._to_list_item(r, reviewer_name=reviewer_name))

            # would_recommend_percentage not tracked -> 0
            return ReviewSummary(
                hostel_id=hostel_id,
                hostel_name=hostel.name,
                total_reviews=total_reviews,
                average_rating=avg_rating,
                rating_5_count=rating_counts[5],
                rating_4_count=rating_counts[4],
                rating_3_count=rating_counts[3],
                rating_2_count=rating_counts[2],
                rating_1_count=rating_counts[1],
                verified_reviews_count=verified_count,
                verified_reviews_percentage=verified_pct,
                recent_reviews=recent_items,
                would_recommend_percentage=Decimal("0"),
            )