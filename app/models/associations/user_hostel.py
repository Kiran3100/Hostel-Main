# app.models/associations/user_hostel.py
from datetime import date
from typing import Union
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseEntity


class UserHostel(BaseEntity):
    """
    Generic user-hostel association (e.g., last active hostel, favorite hostel, etc.).
    """
    __tablename__ = "assoc_user_hostel"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    association_type: Mapped[str] = mapped_column(String(50))  # e.g., 'favorite', 'recent', 'assigned'
    created_date: Mapped[date] = mapped_column(Date, default=date.today)

    metadata_json: Mapped[Union[dict, None]] = mapped_column(JSON, nullable=True)