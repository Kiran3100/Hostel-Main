# app/services/search/autocomplete_service.py
from __future__ import annotations

from typing import Callable, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorHostelRepository
from app.schemas.search.search_autocomplete import (
    AutocompleteRequest,
    AutocompleteResponse,
    Suggestion,
)
from app.services.common import UnitOfWork


class AutocompleteService:
    """
    Autocomplete / suggestions for:

    - hostel names
    - city
    - area

    Uses VisitorHostel denormalized view for simple prefix-based suggestions.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_visitor_hostel_repo(self, uow: UnitOfWork) -> VisitorHostelRepository:
        return uow.get_repo(VisitorHostelRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_suggestions(self, req: AutocompleteRequest) -> AutocompleteResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_visitor_hostel_repo(uow)

            # Fetch a reasonable number of items; refine in Python
            candidates = repo.search(
                city=None,
                area=None,
                min_price=None,
                max_price=None,
                gender_type=None,
                search=req.prefix,
                limit=200,
            )

            suggestions: List[Suggestion] = []
            prefix = req.prefix.lower()

            if req.type == "hostel":
                # Suggest hostel names starting with prefix
                seen: Dict[str, bool] = {}
                for vh in candidates:
                    name = vh.hostel_name
                    if not name:
                        continue
                    if not name.lower().startswith(prefix):
                        continue
                    if name in seen:
                        continue
                    seen[name] = True
                    suggestions.append(
                        Suggestion(
                            value=name,
                            label=name,
                            type="hostel",
                            extra={
                                "hostel_id": str(vh.hostel_id),
                                "city": vh.city,
                            },
                        )
                    )
                    if len(suggestions) >= req.limit:
                        break

            elif req.type == "city":
                # Unique city names starting with prefix
                seen: Dict[str, int] = {}
                for vh in candidates:
                    city = vh.city
                    if not city:
                        continue
                    if not city.lower().startswith(prefix):
                        continue
                    seen[city] = seen.get(city, 0) + 1

                for city, count in sorted(seen.items(), key=lambda x: -x[1])[: req.limit]:
                    suggestions.append(
                        Suggestion(
                            value=city,
                            label=city,
                            type="city",
                            extra={"count": count},
                        )
                    )

            else:  # area
                # Use VisitorHostel.location or area field (if present)
                seen: Dict[str, int] = {}
                for vh in candidates:
                    area = getattr(vh, "area", None) or getattr(vh, "location", None)
                    if not area:
                        continue
                    if not area.lower().startswith(prefix):
                        continue
                    seen[area] = seen.get(area, 0) + 1

                for area, count in sorted(seen.items(), key=lambda x: -x[1])[: req.limit]:
                    suggestions.append(
                        Suggestion(
                            value=area,
                            label=area,
                            type="area",
                            extra={"count": count},
                        )
                    )

        return AutocompleteResponse(suggestions=suggestions)