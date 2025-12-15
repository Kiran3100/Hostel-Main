# app.models/content/mess_menu.py
from __future__ import annotations

from datetime import date, time
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, Time, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity


class MessMenu(BaseEntity):
    """Daily mess menu per hostel."""
    __tablename__ = "content_mess_menu"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    menu_date: Mapped[date] = mapped_column(Date, index=True)
    day_of_week: Mapped[str] = mapped_column(String(20))

    breakfast_items: Mapped[List[str]] = mapped_column(JSON, default=list)
    lunch_items: Mapped[List[str]] = mapped_column(JSON, default=list)
    snacks_items: Mapped[List[str]] = mapped_column(JSON, default=list)
    dinner_items: Mapped[List[str]] = mapped_column(JSON, default=list)

    breakfast_time: Mapped[Optional[time]] = mapped_column(Time)
    lunch_time: Mapped[Optional[time]] = mapped_column(Time)
    snacks_time: Mapped[Optional[time]] = mapped_column(Time)
    dinner_time: Mapped[Optional[time]] = mapped_column(Time)

    is_special_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    special_occasion: Mapped[Optional[str]] = mapped_column(String(255))

    vegetarian_available: Mapped[bool] = mapped_column(Boolean, default=True)
    non_vegetarian_available: Mapped[bool] = mapped_column(Boolean, default=False)
    vegan_available: Mapped[bool] = mapped_column(Boolean, default=False)
    jain_available: Mapped[bool] = mapped_column(Boolean, default=False)

    hostel: Mapped["Hostel"] = relationship()